from pathlib import Path
import os,json,sys,uuid,subprocess,importlib.util,re,threading
from typing import Literal
from backend.acquisition import latest_start
from fastapi import FastAPI,HTTPException,Request
from fastapi.responses import FileResponse,JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.gzip import GZipMiddleware
from pydantic import BaseModel,Field,ConfigDict
from backend.data import ROOT,build_case,read,CLASSES_UI
from backend.assets import CHECKPOINT,SHA
WORKSPACE=Path(os.environ.get('SARSCOPE_WORKSPACE',str(ROOT/'workspace'))).expanduser().resolve()
PREVIEW=os.environ.get('SARSCOPE_PREVIEW')=='1'
app=FastAPI(title='SARScope Local',docs_url=None,redoc_url=None)
app.add_middleware(TrustedHostMiddleware,allowed_hosts=['*'] if PREVIEW else ['localhost','127.0.0.1','testserver'])
app.add_middleware(GZipMiddleware,minimum_size=1000)
lock=threading.Lock();active=None;process=None

def case_folder(cid):
    if cid=='mannheim': return ROOT/'sample/mannheim'
    if not re.fullmatch('[0-9a-f]{16}',cid): raise HTTPException(404,'Case not found')
    packaged=ROOT/'sample/cases'/cid
    folder=packaged if packaged.is_dir() else WORKSPACE/'submission_v1/cases'/cid
    if not (folder/'completion.json').exists() or not (folder/'map_2021-01.png').exists() and not list(folder.glob('map_*.png')): raise HTTPException(404,'Completed case not found')
    return folder

@app.middleware('http')
async def local_only(request:Request,call_next):
    if request.method in ('POST','PUT','DELETE','PATCH'):
        if PREVIEW: return JSONResponse({'detail':'Preview is read-only. Run the downloaded app for local analysis.'},403)
        if request.headers.get('x-sarscope-local')!='1': return JSONResponse({'detail':'Local app header required'},403)
        origin=request.headers.get('origin')
        if origin and origin not in ('http://127.0.0.1:8765','http://localhost:8765'): return JSONResponse({'detail':'Untrusted origin'},403)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Cache-Control']='no-store' if request.url.path.startswith('/api') else 'no-cache'
    return response

@app.get('/api/status')
def status():
    ck=WORKSPACE/'restored'/CHECKPOINT
    deps=all(importlib.util.find_spec(x) is not None for x in ['torch','segmentation_models_pytorch','ee','rasterio'])
    credentials=(Path.home()/'.config/earthengine/credentials').is_file()
    runtime=read(WORKSPACE/'cpu_runtime_check.json',{})
    runtime_ok=runtime.get('status')=='PASS' and runtime.get('checkpoint_sha256')==SHA
    return {'runtime_checked':runtime_ok,'preview':PREVIEW,'model_present':ck.exists(),'dependencies':deps,'credentials_present':credentials,
        'ready':ck.exists() and deps and credentials and runtime_ok and not PREVIEW,'device':'CPU','workspace':None if PREVIEW else str(WORKSPACE),'active_job':active,
        'checkpoint_sha256':SHA,'classes':CLASSES_UI,'earliest_start_month':'2015-01','latest_start_month':latest_start()}
@app.get('/api/cases')
def cases():
    result=[{'id':'mannheim','name':'Mannheim, Germany','period':'2021-01','source':'Reviewed server result'}]
    for p in sorted(list((ROOT/'sample/cases').glob('*'))+list((WORKSPACE/'submission_v1/cases').glob('*'))):
        if (p/'completion.json').exists() and list(p.glob('map_*.png')):
            s=read(p/'request.json',{});meta=read(p/'case_name.json',{});result.append({'id':p.name,'name':meta.get('name',f"{s.get('latitude',0):.4f}°, {s.get('longitude',0):.4f}°"),'period':s.get('start_month'),'source':'Packaged saved case' if p.parent==ROOT/'sample/cases' else 'Local CPU result'})
    return result
@app.get('/api/cases/{cid}')
def case(cid:str): return build_case(case_folder(cid),cid)
@app.get('/api/cases/{cid}/files/{filename}')
def files(cid:str,filename:str):
    folder=case_folder(cid)
    allowed={p.name for p in folder.iterdir() if p.is_file() and (p.suffix in ('.png','.csv','.json','.tif','.html') or p.name=='case_export.zip')}
    if filename not in allowed: raise HTTPException(404,'Export not available')
    return FileResponse(folder/filename,filename=filename if not filename.endswith(('.png','.html')) else None)
@app.get('/quality', include_in_schema=False)
def quality_review():
    return FileResponse(ROOT/'docs/index.html', media_type='text/html')

@app.get('/api/evidence')
def evidence():
    return {'test':read(ROOT/'evidence/test_metrics.json'),'validation':read(ROOT/'evidence/val_metrics.json'),'replay':read(ROOT/'evidence/validation_replay.json')}

class Analyze(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    latitude:float=Field(ge=-79,le=83)
    longitude:float=Field(ge=-179,le=179)
    start_month:str=Field(pattern=r'^\d{4}-\d{2}$')
    period_mode:Literal['historical','latest_completed']='historical'
    project:str=Field(min_length=3,max_length=100,pattern=r'^[a-zA-Z0-9][a-zA-Z0-9:._-]+$')
@app.post('/api/analyze')
def analyze(args:Analyze):
    global active,process
    from pipeline import request_spec
    resolved_start=latest_start() if args.period_mode=='latest_completed' else args.start_month
    try: request_spec(args.latitude,args.longitude,resolved_start)
    except ValueError as e: raise HTTPException(422,str(e))
    with lock:
        if process and process.poll() is None: raise HTTPException(409,'An analysis is already running. Wait for it to finish.')
        if not status()['ready']: raise HTTPException(409,'Complete 02_ENABLE_INFERENCE.cmd (including the runtime check) and 03_SIGN_IN.cmd first. Saved results remain available.')
        active=uuid.uuid4().hex;folder=WORKSPACE/'jobs';folder.mkdir(parents=True,exist_ok=True)
        request=folder/f'{active}.json';request.write_text(json.dumps({**args.model_dump(),'start_month':resolved_start,'workspace':str(WORKSPACE)}))
        request.with_suffix('.status.json').write_text(json.dumps({'state':'queued','messages':['Starting local analysis…']}))
        with (folder/f'{active}.log').open('w',encoding='utf-8') as log:
            process=subprocess.Popen([sys.executable,'-u',str(ROOT/'backend/worker.py'),str(request)],cwd=str(ROOT),stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'PYTHONUTF8':'1','MPLBACKEND':'Agg'})
        return {'job_id':active}
@app.get('/api/jobs/{jid}')
def job(jid:str):
    if not re.fullmatch('[0-9a-f]{32}',jid): raise HTTPException(404,'Job not found')
    path=WORKSPACE/'jobs'/f'{jid}.status.json'
    if not path.exists(): raise HTTPException(404,'Job not found')
    data=read(path)
    if jid==active and process and process.poll() is not None and data['state'] in ('queued','running'):
        data={'state':'failed','error':'The local worker stopped unexpectedly. See workspace/jobs for its log.','messages':data.get('messages',[])}
    return data

DIST=ROOT/'frontend/dist'
if DIST.exists(): app.mount('/',StaticFiles(directory=str(DIST),html=True),name='frontend')
