"""Portable Windows setup. Prebuilt React UI: no Node.js required."""
from pathlib import Path
import os,sys,subprocess,venv,struct,argparse
ROOT=Path(__file__).resolve().parent
PY=ROOT/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')

def call(args): subprocess.run([str(a) for a in args],cwd=ROOT,check=True)
def base():
    if not PY.exists():
        if sys.version_info[:2]!=(3,12) or struct.calcsize('P')!=8:
            raise RuntimeError('Use 64-bit Python 3.12. Install from python.org and run: py -3.12 bootstrap.py viewer')
        print('Creating a dedicated Python environment...',flush=True)
        venv.EnvBuilder(with_pip=True).create(ROOT/'.venv')
    stamp=ROOT/'.venv/viewer-ready'
    if not stamp.exists():
        call([PY,'-m','pip','install','--upgrade','pip'])
        call([PY,'-m','pip','install','-r','requirements-viewer.txt'])
        stamp.write_text('1')

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['viewer','inference','auth','import']);p.add_argument('--bundle',default=r'C:\SARPres\SARScope_selected_restore.zip');p.add_argument('--project',default='gae-application-308005');a=p.parse_args()
    base()
    if a.command=='viewer':
        call([PY,'serve.py','--open'])
    elif a.command=='inference':
        print('Installing CPU PyTorch. The first download may be several hundred MB.',flush=True)
        call([PY,'-m','pip','install','torch==2.9.0','torchvision==0.24.0','--index-url','https://download.pytorch.org/whl/cpu'])
        call([PY,'-m','pip','install','-r','requirements-inference.txt'])
        call([PY,'-m','pip','check'])
        call([PY,'local_tools.py','import','--bundle',a.bundle])
        call([PY,'local_tools.py','smoke'])
        print('\nInference setup complete. Next: 03_SIGN_IN.cmd. Refresh Local setup in the UI.',flush=True)
    elif a.command=='import': call([PY,'local_tools.py','import','--bundle',a.bundle])
    else: call([PY,'local_tools.py','auth','--project',a.project])
if __name__=='__main__':
    try: main()
    except (Exception,KeyboardInterrupt) as e:
        print('\nStopped: '+str(e),file=sys.stderr);raise SystemExit(1)
