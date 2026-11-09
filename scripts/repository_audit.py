#!/usr/bin/env python3
"""Local pre-push checks. Does not require model weights or Earth Engine credentials."""
from pathlib import Path
import json,hashlib,sys,re,subprocess
ROOT=Path(__file__).resolve().parents[1]
checks=[];errors=[]
def check(name,condition,message=''):
  checks.append((name,bool(condition)))
  if not condition:errors.append(f'{name}: {message}')
# Tracked-ready tree must not include sensitive files, caches or actual weight blobs.
for d in ['backend','engine','frontend/src','frontend/dist','sample/cases','sample/mannheim','models','docs','research','tests','.github/workflows']:
  check('directory '+d,(ROOT/d).exists(),'missing')
check('pages entry',(ROOT/'docs/index.html').is_file(),'GitHub Pages static page missing')
check('frozen loader',(ROOT/'engine/model.py').is_file(),'model loader missing')
model=json.loads((ROOT/'models/model-manifest.json').read_text())
check('frozen digest',model['checkpoint_sha256']=='a52e9f4f69d4647dfad7b6b01fb3613070f91201aa4dceb004db410f6b79b2b5','unexpected checkpoint identity')
# Normal Python execution generates ignored __pycache__ directories; they are not Git content.
ignore_parts={"workspace",".venv","node_modules","__pycache__",".git",".pytest_cache"}
tracked=[]
if (ROOT/".git").exists():
  listed=subprocess.run(["git","ls-files","-z"],cwd=ROOT,capture_output=True)
  if listed.returncode==0:
    tracked=[ROOT/x.decode() for x in listed.stdout.split(b"\0") if x]
for fp in (tracked or ROOT.rglob('*')):
  if not fp.is_file():continue
  relative=fp.relative_to(ROOT)
  if any(x in relative.parts for x in ignore_parts):
    if tracked:check('tracked runtime cache '+str(relative),False,'remove from Git')
    continue
  if fp.suffix in {'.pt','.pth','.ckpt','.safetensors','.key','.pem'}:check('sensitive artifact '+str(relative),False,'store outside Git')
  if fp.name in ('.env','credentials.json'):check('credential file '+str(relative),False,'store outside Git')
  if fp.stat().st_size>95*1024*1024:check('large file '+str(relative),False,'too large for ordinary GitHub blobs')
for name in ['Cairo','Mauritania','Queens']:
  check('example '+name,any(name.lower() in f.read_text(encoding='utf-8').lower() for f in (ROOT/'sample/cases').glob('*/case_name.json')),'missing from saved cases')
for name,status in checks:
  print(('PASS' if status else 'FAIL')+'  '+name)
print(f'\n{len(checks)-len(errors)}/{len(checks)} checks passed')
if errors:
  print('Errors: '+', '.join(errors),file=sys.stderr);sys.exit(1)
