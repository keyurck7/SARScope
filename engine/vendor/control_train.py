"""Derived from the frozen SARScope baseline: full-FP32 control only.
Original architecture, data, unweighted CE, optimizer and schedule preserved.
"""
import json
import os
import random
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset

from sarscope_baseline.core import CLASSES, PROCESSOR, canonical_hash, confusion, normalize, scores, write_json


@dataclass
class Config:
    variant: str = "single"
    encoder: str = "resnet34"
    encoder_weights: str | None = "imagenet"
    epochs: int = 30
    batch_size: int = 8
    lr: float = 3e-4
    weight_decay: float = 1e-4
    seed: int = 42
    limit_samples: int = 0  # Smoke only; zero means the complete split.
    device: str = "cuda"


class MonthlyDataset(Dataset):
    def __init__(self, prepared, split, variant, limit=0, seed=42):
        root = Path(prepared)
        self.db = np.load(root / f"{split}_db.npy", mmap_mode="r")
        self.ctx = np.load(root / f"{split}_ctx.npy", mmap_mode="r")
        self.lab = np.load(root / f"{split}_lab.npy", mmap_mode="r")
        self.index = np.argwhere(np.load(root / f"{split}_support.npy") > 0)
        if limit and len(self.index) > limit:
            choose = np.random.default_rng(seed).choice(len(self.index), limit, replace=False)
            self.index = self.index[np.sort(choose)]
        self.stats = json.loads((root / "stats.json").read_text())
        self.meta = json.loads((root / f"{split}_meta.json").read_text())
        self.variant = variant
        if not len(self.index):
            raise ValueError(f"No scored samples in {split}")

    def __len__(self):
        return len(self.index)

    def __getitem__(self, row):
        i, t = self.index[row]
        x, valid = normalize(self.db[i, t], self.ctx[i], self.variant, self.stats)
        y = np.array(self.lab[i, t], dtype=np.int64)
        if ((y != 255) & ~valid).any():
            raise ValueError("Label exists outside SAR support")
        return torch.from_numpy(x), torch.from_numpy(y), int(i), int(t)


def build_model(cfg, weights=None):
    import segmentation_models_pytorch as smp
    return smp.Unet(encoder_name=cfg.encoder, encoder_weights=weights,
                    in_channels=4 if cfg.variant == "single" else 8, classes=9)


def loader(data, cfg, shuffle=False, generator=None):
    # Server /dev/shm is 64MiB. No worker IPC and no full-dataset GPU allocation.
    return DataLoader(data, batch_size=cfg.batch_size, shuffle=shuffle,
                      num_workers=0, drop_last=False, pin_memory=cfg.device == "cuda", generator=generator)


def pixel_cross_entropy_sum(logits, target):
    """Unweighted CE sum with ignored pixels, avoiding CUDA's NLLLoss2d reduction.

    Same objective as cross_entropy(..., ignore_index=255, reduction='sum').
    Explicit log-softmax/gather/masked sum retains strict deterministic mode.
    """
    valid = target != 255
    safe_target = target.masked_fill(~valid, 0)
    logp = torch.nn.functional.log_softmax(logits.float(), dim=1)
    losses = -logp.gather(1, safe_target.unsqueeze(1)).squeeze(1)
    return losses.masked_fill(~valid, 0).sum()


def check_loss_runtime(device="cuda"):
    """Check actual device forward/backward repeatability before opening data."""
    torch.use_deterministic_algorithms(True)
    x = torch.linspace(-3, 3, 2 * 9 * 32 * 32, device=device).reshape(2, 9, 32, 32)
    y = (torch.arange(2 * 32 * 32, device=device) % 9).reshape(2, 32, 32)
    y[:, :4, :4] = 255
    outcomes = []
    for _ in range(2):
        v = x.clone().requires_grad_(True)
        loss = pixel_cross_entropy_sum(v, y)
        loss.backward()
        if not torch.isfinite(loss) or not torch.isfinite(v.grad).all():
            raise FloatingPointError("Device CE runtime check produced nonfinite values")
        outcomes.append((loss.detach(), v.grad.detach()))
    if not all(torch.equal(a, b) for a, b in zip(outcomes[0], outcomes[1])):
        raise RuntimeError("Device CE repeatability check failed")
    return {"device": device, "loss": "log_softmax_gather_masked_sum",
            "strict_determinism": torch.are_deterministic_algorithms_enabled(),
            "finite_forward_backward": True, "identical_repeated_outputs_and_gradients": True}


@torch.inference_mode()
def evaluate(model, data, cfg):
    model.eval()
    matrix = np.zeros((9, 9), np.int64)
    regions = defaultdict(lambda: np.zeros((9, 9), np.int64))
    months = np.zeros((12, 9, 9), np.int64)
    loss_sum, pixels = 0., 0
    for x, y, ids, times in loader(data, cfg):
        x, y = x.to(cfg.device), y.to(cfg.device)
        with torch.autocast(device_type=cfg.device, dtype=torch.float16, enabled=False):
            logits = model(x)
        if not torch.isfinite(logits).all():
            raise FloatingPointError("Nonfinite FP32 validation logits")
        loss = pixel_cross_entropy_sum(logits, y)
        if not torch.isfinite(loss):
            raise FloatingPointError("Nonfinite validation loss")
        loss_sum += float(loss)
        pixels += int((y != 255).sum())
        pred, ref = logits.argmax(1).cpu().numpy(), y.cpu().numpy()
        for j, (i, t) in enumerate(zip(ids.tolist(), times.tolist())):
            cm = confusion(ref[j], pred[j])
            matrix += cm
            regions[data.meta[i]["region"]] += cm
            months[t] += cm
    result = scores(matrix)
    result.update(loss=loss_sum / pixels, scored_pixels=pixels,
                  per_region={k: scores(v) for k, v in sorted(regions.items())},
                  per_month={str(t + 1): scores(cm) for t, cm in enumerate(months)})
    return result


def atomic_checkpoint(path, checkpoint):
    path = Path(path)
    tmp = path.with_suffix(".tmp")
    torch.save(checkpoint, tmp)
    os.replace(tmp, path)


def train(prepared, output, cfg, resume=False, stop_after_epoch=None, model_factory=build_model):
    if cfg.variant not in ("single", "temporal") or cfg.epochs < 1 or cfg.batch_size < 1:
        raise ValueError("Invalid training configuration")
    if cfg.lr <= 0 or cfg.weight_decay < 0 or cfg.limit_samples < 0:
        raise ValueError("Invalid optimizer/sample settings")
    if cfg.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable in this interpreter; no silent CPU training")
    out, prepared = Path(output), Path(prepared)
    manifest = json.loads((prepared / "manifest.json").read_text())
    if not manifest.get("complete"):
        raise ValueError("Prepared data incomplete")
    if out.exists() and not resume:
        raise FileExistsError(f"Run exists: {out}; explicitly resume or choose another name")
    if resume and not (out / "last.pt").exists():
        raise FileNotFoundError("No last.pt to resume")
    out.mkdir(parents=True, exist_ok=True)
    random.seed(cfg.seed); np.random.seed(cfg.seed); torch.manual_seed(cfg.seed)
    # Deterministic algorithms requested where available. GPU reproducibility is
    # checked by recorded environment; not promised across hardware/libraries.
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.use_deterministic_algorithms(True)
    tr = MonthlyDataset(prepared, "train", cfg.variant, cfg.limit_samples, cfg.seed)
    va = MonthlyDataset(prepared, "val", cfg.variant, cfg.limit_samples, cfg.seed)
    state = torch.load(out / "last.pt", map_location="cpu", weights_only=False) if resume else None
    code_id = canonical_hash({p.name: __import__("hashlib").sha256(p.read_bytes()).hexdigest()
                              for p in sorted(Path(__file__).parent.glob("*.py"))})
    if state and (state["config"] != asdict(cfg) or state["dataset_id"] != manifest["dataset_id"] or state["code_id"] != code_id):
        raise ValueError("Resume requires identical config, prepared dataset and code")
    model = model_factory(cfg, None if resume else cfg.encoder_weights).to(cfg.device)
    opt = torch.optim.AdamW(model.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=cfg.epochs)
    scaler = torch.amp.GradScaler("cuda", enabled=False)
    gen = torch.Generator().manual_seed(cfg.seed)
    start, best, history = 0, -1., []
    if state:
        model.load_state_dict(state["model"]); opt.load_state_dict(state["optimizer"])
        sched.load_state_dict(state["scheduler"]); scaler.load_state_dict(state["scaler"])
        start, best, history = state["epoch"], state["best_mIoU"], state["history"]
        random.setstate(state["python_rng"]); np.random.set_state(state["numpy_rng"])
        torch.set_rng_state(state["torch_rng"]); gen.set_state(state["loader_rng"])
        if cfg.device == "cuda":
            torch.cuda.set_rng_state_all(state["cuda_rng"])
    write_json(out / "config.json", asdict(cfg))

    def checkpoint(epoch):
        return {"model": model.state_dict(), "optimizer": opt.state_dict(),
                "scheduler": sched.state_dict(), "scaler": scaler.state_dict(),
                "config": asdict(cfg), "epoch": epoch, "best_mIoU": best,
                "history": history, "stats": tr.stats, "classes": CLASSES,
                "processor": PROCESSOR, "dataset_id": manifest["dataset_id"], "code_id": code_id,
                "precision_policy": "FP32 training and evaluation; TF32 disabled; no AMP",
                "python_rng": random.getstate(), "numpy_rng": np.random.get_state(),
                "torch_rng": torch.get_rng_state(), "loader_rng": gen.get_state(),
                "cuda_rng": torch.cuda.get_rng_state_all() if cfg.device == "cuda" else []}

    if not resume:
        atomic_checkpoint(out / "initial.pt", checkpoint(0))
        atomic_checkpoint(out / "last.pt", checkpoint(0))
    train_loader = loader(tr, cfg, shuffle=True, generator=gen)
    for epoch in range(start + 1, cfg.epochs + 1):
        model.train()
        t0, loss_sum, pixels = time.perf_counter(), 0., 0
        skipped_updates = 0
        for step, (x, y, _, _) in enumerate(train_loader, 1):
            x, y = x.to(cfg.device), y.to(cfg.device)
            n = int((y != 255).sum())
            opt.zero_grad(set_to_none=True)
            with torch.autocast(device_type=cfg.device, dtype=torch.float16, enabled=False):
                logits = model(x)
            if not torch.isfinite(logits).all():
                raise FloatingPointError(f"Nonfinite FP32 training logits at epoch {epoch} step {step}")
            loss = pixel_cross_entropy_sum(logits, y) / n
            if not torch.isfinite(loss):
                raise FloatingPointError(f"Nonfinite training loss at epoch {epoch} step {step}")
            scaler.scale(loss).backward()
            gradients = [p.grad for p in model.parameters() if p.grad is not None]
            if not gradients or not bool(torch.stack([torch.isfinite(g).all() for g in gradients]).all()):
                raise FloatingPointError(f"Nonfinite FP32 gradient at epoch {epoch} step {step}")
            old_scale = scaler.get_scale()
            scaler.step(opt); scaler.update()
            skipped_updates += int(scaler.get_scale() < old_scale)
            loss_sum += float(loss.detach()) * n
            pixels += n
            if step == 1 or step % 25 == 0 or step == len(train_loader):
                progress = {"epoch": epoch, "step": step, "steps": len(train_loader),
                            "train_CE": loss_sum / pixels, "elapsed_s": time.perf_counter() - t0}
                write_json(out / "progress.json", progress)
                print(f"{cfg.variant}: epoch {epoch}/{cfg.epochs} step {step}/{len(train_loader)} CE={loss_sum/pixels:.4f}", flush=True)
        if skipped_updates == len(train_loader):
            raise FloatingPointError("AMP skipped every optimizer update; smoke/training did not succeed")
        result = evaluate(model, va, cfg)
        improved = result["mIoU"] > best
        if improved:
            best = result["mIoU"]
        row = {"epoch": epoch, "train_CE": loss_sum / pixels, "validation_CE": result["loss"],
               "validation_OA": result["OA"], "validation_mIoU": result["mIoU"],
               "lr": opt.param_groups[0]["lr"], "seconds": time.perf_counter() - t0,
               "amp_skipped_updates": skipped_updates}
        history.append(row)
        sched.step()
        saved = checkpoint(epoch)
        if improved:
            atomic_checkpoint(out / "best.pt", saved)
            write_json(out / "best_validation.json", result)
        write_json(out / "history.json", history)
        write_json(out / "last_validation.json", result)
        atomic_checkpoint(out / "last.pt", saved)  # Commit the epoch after its reports.
        print(json.dumps(row), flush=True)
        if stop_after_epoch is not None and epoch >= stop_after_epoch:
            break
    summary = {"completed_epochs": history[-1]["epoch"] if history else 0,
               "best_validation_mIoU": best, "dataset_id": manifest["dataset_id"],
               "smoke_only": cfg.limit_samples > 0, "train_samples": len(tr), "validation_samples": len(va),
               "test_evaluated": False, "resume_boundary": "Last fully checkpointed epoch",
               "peak_cuda_allocated_bytes": torch.cuda.max_memory_allocated() if cfg.device == "cuda" else None}
    write_json(out / "summary.json", summary)
    return summary
