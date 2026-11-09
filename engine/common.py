"""Submission paths, frozen identity and portable JSON utilities."""
import os
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'vendor'))
import json
import hashlib
import zipfile
from datetime import datetime, timezone
from sarscope_baseline.core import CLASSES, PROCESSOR, sha256, canonical_hash

DATASET_ID = '6c3b62d7d71f22d4d098b9fbaf497daf45fe5c3c4e2198fa62cb1db17c4662cf'
WORK_NAME = 'sarscope-baseline-20261108'
CHECKPOINT = WORK_NAME + '/fp32_control_seed42/temporal/best.pt'
DEFAULT_VAULT = Path.home() / 'vault/SARScope_Work'
COLORS = ['#419BDF','#397D49','#88B053','#7A87C6','#E49635','#DFC35A','#C4281B','#A59B8F','#B39FE1']

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def write(path, obj):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    os.replace(tmp, path)

def utc():
    return datetime.now(timezone.utc).isoformat()

def code_identity():
    return canonical_hash({str(p.relative_to(ROOT)): sha256(p) for p in sorted(ROOT.rglob('*.py'))
                           if '__pycache__' not in p.parts})

def locate(vault):
    vault = Path(vault).expanduser().resolve()
    restored = vault / 'restored'
    return restored, restored / WORK_NAME / 'prepared', restored / CHECKPOINT, vault / 'submission_v1'

def verify_restored(vault):
    restored, prepared, checkpoint, output = locate(vault)
    if not checkpoint.is_file():
        raise FileNotFoundError(f'Restored reference checkpoint missing: {checkpoint}')
    digest = sha256(checkpoint)
    if digest != 'a52e9f4f69d4647dfad7b6b01fb3613070f91201aa4dceb004db410f6b79b2b5':
        raise ValueError('Checkpoint differs from frozen reference')
    manifest = read(prepared / 'manifest.json')
    if manifest != read(ROOT / 'evidence/manifest.json') or not manifest['complete']:
        raise ValueError('Prepared dataset manifest differs from reviewed baseline')
    if sha256(prepared / 'stats.json') != manifest['arrays_and_metadata_sha256']['stats.json']:
        raise ValueError('Normalization statistics checksum mismatch')
    output.mkdir(parents=True, exist_ok=True)
    return {'checkpoint_sha256': digest, 'dataset_id': DATASET_ID,
            'checkpoint_relative_path': CHECKPOINT, 'selection': 'Unweighted FP32 temporal control; seed 42; best validation mIoU; epoch 13',
            'test_used_for_selection': False, 'code_id': code_identity(), 'processor': PROCESSOR,
            'classes': CLASSES, 'precision': 'FP32; TF32 disabled; AMP disabled'}

def review_archive(output):
    """Return compact results, never credentials, environments, weights or raw pixels."""
    output = Path(output)
    archive = output / 'submission_review.zip'
    allowed = {'.json', '.csv', '.md', '.png', '.html', '.ipynb', '.txt'}
    with zipfile.ZipFile(archive.with_suffix('.tmp'), 'w', zipfile.ZIP_DEFLATED) as z:
        for p in sorted(output.rglob('*')):
            if (p.is_file() and p.suffix in allowed and 'cache' not in p.relative_to(output).parts
                    and p.stat().st_size < 20 * 1024**2):
                z.write(p, str(p.relative_to(output)))
    os.replace(archive.with_suffix('.tmp'), archive)
    return archive
