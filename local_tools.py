from pathlib import Path
import os,sys,argparse,json,time
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'engine'))
WORKSPACE=Path(os.environ.get('SARSCOPE_WORKSPACE',str(ROOT/'workspace')))
p=argparse.ArgumentParser();p.add_argument('command',choices=['import','smoke','auth']);p.add_argument('--bundle',default=r'C:\SARPres\SARScope_selected_restore.zip');p.add_argument('--project',default='gae-application-308005');a=p.parse_args()
if a.command=='import':
    from backend.assets import import_bundle
    print(json.dumps(import_bundle(a.bundle,WORKSPACE),indent=2))
elif a.command=='auth':
    import ee
    ee.Authenticate(auth_mode='localhost')
    ee.Initialize(project=a.project)
    print('Earth Engine access verified for '+a.project)
else:
    from model import load,predict
    import numpy as np,torch
    started=time.perf_counter();net,cfg,stats,identity=load(WORKSPACE)
    # Synthetic input ONLY for runtime validation. Never displayed as a location result.
    raw=np.empty((12,2,256,256),np.float16);raw[:,0]=-12;raw[:,1]=-20
    labels,probs=predict(net,stats,raw)
    assert labels.shape==(12,256,256) and probs.shape==(12,9,256,256)
    assert np.isfinite(probs).all() and np.allclose(probs.sum(1),1,atol=1e-5)
    report={'status':'PASS','test':'Synthetic constant-input CPU runtime check; not geographic evaluation','device':identity['device'],'checkpoint_sha256':identity['checkpoint_sha256'],'seconds':time.perf_counter()-started,'torch':torch.__version__}
    WORKSPACE.mkdir(parents=True,exist_ok=True);(WORKSPACE/'cpu_runtime_check.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
