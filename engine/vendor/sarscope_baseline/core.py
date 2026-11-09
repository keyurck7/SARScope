"""Shared, testable data and scoring contracts. No optical model inputs."""
import hashlib
import json
import os
from pathlib import Path
import warnings

import numpy as np

CLASSES = ["water", "trees", "grass", "flooded_vegetation", "crops",
           "shrub_and_scrub", "built", "bare", "snow_and_ice"]
FEATURES = ["VV", "VH", "VV_minus_VH", "VV_mean12", "VH_mean12", "VV_std12", "VH_std12"]
PROCESSOR = "legacy-linear-monthly-lee5-enl4.4-strict-support-v1"
IGNORE = 255


def write_json(path, value):
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    os.replace(tmp, path)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def validate_raw(raw, dw):
    if raw.ndim != 3 or raw.shape[0] != 36 or dw.shape != raw.shape:
        raise ValueError("Expected matching (36,H,W) S1 and DW arrays")
    if raw.dtype.kind != "f" or dw.dtype != np.uint8:
        raise ValueError("Expected floating S1 and uint8 Dynamic World")
    r, d = raw.reshape(12, 3, *raw.shape[1:]), dw.reshape(12, 3, *dw.shape[1:])
    counts = r[:, 2].astype(np.float32)
    if not np.isfinite(counts).all() or (counts < 0).any() or (counts != np.floor(counts)).any():
        raise ValueError("Invalid SAR scene counts")
    if ((d[:, 0] > 8) & (d[:, 0] != IGNORE)).any() or (d[:, 1] > 100).any():
        raise ValueError("Invalid Dynamic World class/confidence")
    return r, d


def preprocess(raw):
    """Frozen legacy filter for baseline comparability, with stricter support.

    ENL*count is an inherited approximation, not a validated physical noise model.
    This does not reverse the upstream mixing of orbit geometries.
    """
    from scipy.ndimage import uniform_filter
    r = raw.reshape(12, 3, *raw.shape[1:]).astype(np.float32)
    lin, counts = r[:, :2].copy(), r[:, 2]
    observed = np.isfinite(lin).all(1) & (lin > 0).all(1) & (counts > 0)
    lin = np.where(observed[:, None], lin, np.nan)
    for t in range(12):
        for b in range(2):
            img = lin[t, b]
            valid = np.isfinite(img)
            if not valid.any():
                continue
            filled = np.where(valid, img, np.nanmedian(img))
            mean = uniform_filter(filled, 5)
            var = np.maximum(uniform_filter(filled ** 2, 5) - mean ** 2, 0)
            cu2 = 1.0 / (4.4 * np.maximum(counts[t], 1))
            ci2 = var / np.maximum(mean ** 2, 1e-12)
            weight = np.clip(1 - cu2 / np.maximum(ci2, 1e-12), 0, 1)
            result = mean + weight * (filled - mean)
            lin[t, b] = np.where(valid, result, np.nan)
    db = (10 * np.log10(np.maximum(lin, 1e-6))).astype(np.float16)
    if not np.array_equal(np.isfinite(db).all(1), observed):
        raise ValueError("Preprocessing changed valid support")
    return db, observed


def strict_labels(dw, observed, confidence_min=0):
    if not 0 <= confidence_min <= 100:
        raise ValueError("Confidence threshold must be in [0,100]")
    d = dw.reshape(12, 3, *dw.shape[1:])
    valid = (d[:, 0] < 9) & (d[:, 2] > 0) & (d[:, 1] >= confidence_min) & observed
    return np.where(valid, d[:, 0], IGNORE).astype(np.uint8)


def context(db):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        d = db.astype(np.float32)
        return np.concatenate([np.nanmean(d, axis=0), np.nanstd(d, axis=0)]).astype(np.float16)


def features(db_t, ctx, variant):
    if variant not in ("single", "temporal"):
        raise ValueError("Unknown variant")
    d = db_t.astype(np.float32)
    valid = np.isfinite(d).all(0)
    f = [d[0], d[1], d[0] - d[1]]
    if variant == "temporal":
        f.extend(ctx.astype(np.float32))
    return np.stack(f), valid


def normalize(db_t, ctx, variant, stats):
    x, valid = features(db_t, ctx, variant)
    k = len(x)
    mean = np.asarray(stats["mean"][:k], np.float32)[:, None, None]
    std = np.asarray(stats["std"][:k], np.float32)[:, None, None]
    if not np.isfinite(mean).all() or not np.isfinite(std).all() or (std <= 0).any():
        raise ValueError("Invalid normalization statistics")
    x = np.nan_to_num((x - mean) / std, nan=0, posinf=0, neginf=0)
    return np.concatenate([x, valid[None].astype(np.float32)]), valid


def confusion(reference, prediction):
    if reference.shape != prediction.shape:
        raise ValueError("Shape mismatch")
    valid = reference != IGNORE
    r, p = reference[valid], prediction[valid]
    if ((r < 0) | (r >= 9)).any() or ((p < 0) | (p >= 9)).any():
        raise ValueError("Invalid class on a scored pixel")
    return np.bincount(r.astype(np.int64) * 9 + p, minlength=81).reshape(9, 9)


def scores(cm):
    cm = np.asarray(cm)
    if cm.shape != (9, 9) or (cm < 0).any():
        raise ValueError("Expected nonnegative 9x9 confusion matrix")
    tp, r, p = np.diag(cm), cm.sum(1), cm.sum(0)
    union = r + p - tp
    iou = np.divide(tp, union, out=np.full(9, np.nan), where=union > 0)
    f1 = np.divide(2 * tp, r + p, out=np.full(9, np.nan), where=(r + p) > 0)
    clean = lambda x: [float(v) if np.isfinite(v) else None for v in x]
    return {"OA": float(tp.sum() / cm.sum()) if cm.sum() else None,
            "mIoU": float(np.nanmean(iou)) if np.isfinite(iou).any() else None,
            "IoU": clean(iou), "F1": clean(f1), "classes": CLASSES,
            "reference_support": r.tolist(), "predicted_support": p.tolist(),
            "confusion_true_rows_predicted_columns": cm.tolist(),
            "absent_class_policy": "Absent in both: null; false-positive-only: IoU zero",
            "reference": "Dynamic World monthly weak labels; not independent ground truth"}
