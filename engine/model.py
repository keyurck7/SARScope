"""Load the fixed model; evaluate held-out pixels with the reviewed FP32 implementation."""
from common import *
import numpy as np

def load(vault):
    identity = verify_restored(vault)
    import torch
    from control_train import Config, build_model
    device = 'cpu'  # Portable local reference: no university GPU required.
    torch.set_num_threads(min(4, os.cpu_count() or 1))
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.use_deterministic_algorithms(True)
    _, prepared, checkpoint, _ = locate(vault)
    # The checkpoint was created by this project and its backup checksum was verified above.
    ckpt = torch.load(checkpoint, map_location='cpu', weights_only=False)
    if (ckpt['classes'] != CLASSES or ckpt['processor'] != PROCESSOR
            or ckpt['dataset_id'] != DATASET_ID or ckpt['epoch'] != 13
            or ckpt['config'] != read(ROOT / 'evidence/config.json')
            or ckpt['stats'] != read(prepared / 'stats.json')):
        raise ValueError('Checkpoint metadata differs from frozen selection')
    cfg = Config(**ckpt['config']); cfg.device = device; cfg.batch_size = 1
    net = build_model(cfg, weights=None).float().to(device).eval()
    net.load_state_dict(ckpt['model'], strict=True)
    identity['device'] = device
    identity['execution_note'] = 'Local CPU FP32 inference. GPU bitwise equivalence is not claimed.'
    identity['torch'] = torch.__version__
    return net, cfg, ckpt['stats'], identity

def predict(net, stats, db):
    import torch
    from sarscope_baseline.core import normalize, context
    ctx = context(db)
    xs, valid = zip(*(normalize(d, ctx, 'temporal', stats) for d in db))
    probs = []
    with torch.inference_mode():
        for start in range(0, 12):
            logits = net(torch.from_numpy(np.stack(xs[start:start+1])).to(next(net.parameters()).device))
            if not torch.isfinite(logits).all(): raise FloatingPointError('Nonfinite inference logits')
            probs.append(logits.softmax(1).cpu().numpy())
    probs = np.concatenate(probs)
    valid = np.stack(valid)
    labels = probs.argmax(1).astype(np.uint8)
    labels[~valid] = 255
    probs = np.where(valid[:,None], probs, np.nan)
    return labels, probs

def evaluate_submission(vault):
    import torch
    from collections import defaultdict
    from control_train import MonthlyDataset, loader, pixel_cross_entropy_sum
    from sarscope_baseline.core import confusion, scores
    net, cfg, stats, identity = load(vault)
    _, prepared, _, output = locate(vault)
    target = output / 'evaluation'; target.mkdir(parents=True, exist_ok=True)
    protocol = dict(identity, frozen_at=utc(), batch_size=8,
                    decision='Frozen reference before accessing held-out test labels; no further model selection using test metrics')
    if (target / 'protocol.json').exists():
        old = read(target / 'protocol.json')
        for key in identity:
            if key in ('device','torch'): continue
            if old.get(key) != identity[key]: raise ValueError('Evaluation identity changed; do not overwrite final evaluation')
    else: write(target / 'protocol.json', protocol)
    manifest = read(prepared / 'manifest.json')
    for split in ['val', 'test']:
        result_file = target / f'{split}_metrics.json'
        if result_file.exists():
            result = read(result_file)
            if result.get('checkpoint_sha256') != identity['checkpoint_sha256']: raise ValueError('Cached evaluation identity mismatch')
            print(f'Reusing saved {split} evaluation; no repeated test selection.', flush=True)
            continue
        if split == 'test' and not read(target / 'validation_replay.json')['exact_confusion_match']:
            raise RuntimeError('Validation replay mismatch; test remains unopened')
        print(f'Verifying {split} data checksums...', flush=True)
        for name, digest in manifest['arrays_and_metadata_sha256'].items():
            if name.startswith(split + '_') and sha256(prepared / name) != digest:
                raise ValueError('Dataset checksum mismatch: ' + name)
        ds = MonthlyDataset(prepared, split, 'temporal')
        total = np.zeros((9,9), np.int64); regions = defaultdict(lambda: np.zeros((9,9),np.int64))
        months = np.zeros((12,9,9), np.int64); loss_sum=0.; pixels=0
        with torch.inference_mode():
            for step, (x,y,ids,times) in enumerate(loader(ds,cfg), 1):
                x,y = x.to('cuda'),y.to('cuda'); logits=net(x)
                if not torch.isfinite(logits).all(): raise FloatingPointError(f'Nonfinite {split} logits at batch {step}')
                loss=pixel_cross_entropy_sum(logits,y)
                if not torch.isfinite(loss): raise FloatingPointError(f'Nonfinite {split} loss')
                loss_sum+=float(loss); pixels+=int((y!=255).sum())
                pred,ref=logits.argmax(1).cpu().numpy(),y.cpu().numpy()
                for j,(i,t) in enumerate(zip(ids.tolist(), times.tolist())):
                    cm=confusion(ref[j],pred[j]); total+=cm; regions[ds.meta[i]['region']]+=cm; months[t]+=cm
                if step%25==0: print(f'{split}: evaluated {step}/{len(loader(ds,cfg))} batches',flush=True)
        result=scores(total)
        result.update(loss=loss_sum/pixels, scored_pixels=pixels, samples=len(ds), checkpoint_sha256=identity['checkpoint_sha256'],
                      per_region={r:scores(c) for r,c in sorted(regions.items())},
                      per_month={str(t+1):scores(c) for t,c in enumerate(months)}, completed_at=utc())
        write(result_file,result)
        if split=='val':
            baseline=read(ROOT/'evidence/best_validation.json')
            match=np.array_equal(total,baseline['confusion_true_rows_predicted_columns'])
            write(target/'validation_replay.json',{'exact_confusion_match':bool(match),
                'mIoU_difference':result['mIoU']-baseline['mIoU'], 'OA_difference':result['OA']-baseline['OA']})
            if not match: raise RuntimeError('FP32 replay differs from reference; diagnostic saved; test remains unopened')
        print(f'{split}: OA={result["OA"]:.4f}; mIoU={result["mIoU"]:.4f}',flush=True)
    write(target/'completion.json',{'status':'COMPLETE','test_evaluated':True,'training_launched':False,'checkpoint_sha256':identity['checkpoint_sha256']})
    return target
