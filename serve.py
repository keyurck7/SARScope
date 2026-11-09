from pathlib import Path
import sys,os,argparse,webbrowser,threading
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'engine'))
p=argparse.ArgumentParser();p.add_argument('--strictPort',action='store_true');p.add_argument('--preview',action='store_true');p.add_argument('--port',type=int,default=8765);p.add_argument('--host',default='127.0.0.1');p.add_argument('--open',action='store_true');a=p.parse_args()
if not a.preview and a.host not in ('127.0.0.1','localhost'): p.error('Local inference only binds to loopback')
if a.preview: os.environ['SARSCOPE_PREVIEW']='1'
if a.open: threading.Timer(2,lambda:webbrowser.open(f'http://127.0.0.1:{a.port}')).start()
import uvicorn
uvicorn.run('backend.server:app',host=a.host,port=a.port)
