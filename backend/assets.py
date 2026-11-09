"""Restore only the frozen checkpoint and normalization metadata, verified before use."""
from pathlib import Path
import hashlib,json,os,zipfile,shutil
ROOT=Path(__file__).resolve().parents[1]
WORK='sarscope-baseline-20261108'
CHECKPOINT=WORK+'/fp32_control_seed42/temporal/best.pt'
SHA='a52e9f4f69d4647dfad7b6b01fb3613070f91201aa4dceb004db410f6b79b2b5'
DATASET='6c3b62d7d71f22d4d098b9fbaf497daf45fe5c3c4e2198fa62cb1db17c4662cf'
def import_bundle(bundle,workspace):
    bundle=Path(bundle);workspace=Path(workspace)
    frozen=json.loads((ROOT/'engine/evidence/manifest.json').read_text())
    names=[CHECKPOINT,WORK+'/prepared/stats.json',WORK+'/prepared/manifest.json']
    with zipfile.ZipFile(bundle) as z:
        if z.namelist().count('RESTORE_MANIFEST.json')!=1: raise ValueError('Missing or duplicate restore manifest')
        meta=json.loads(z.read('RESTORE_MANIFEST.json'))
        if meta.get('dataset_id')!=DATASET or meta.get('checkpoint')!=CHECKPOINT: raise ValueError('Wrong backup identity')
        workspace.mkdir(parents=True,exist_ok=True)
        needed=sum(z.getinfo(n).file_size for n in names)
        if shutil.disk_usage(workspace).free<needed+200*1024**2: raise OSError('Insufficient disk space to restore inference assets')
        for n in names:
            if z.namelist().count(n)!=1: raise ValueError('Missing or duplicate member: '+n)
            record=meta['files'][n]
            if z.getinfo(n).file_size!=record['bytes']: raise ValueError('Member size mismatch: '+n)
            dest=workspace/'restored'/n;dest.parent.mkdir(parents=True,exist_ok=True)
            tmp=dest.with_suffix(dest.suffix+'.partial');digest=hashlib.sha256();size=0
            try:
                with z.open(n) as src,tmp.open('wb') as out:
                    while chunk:=src.read(1024*1024):
                        digest.update(chunk);size+=len(chunk);out.write(chunk)
                expected=SHA if n==CHECKPOINT else (frozen['arrays_and_metadata_sha256']['stats.json'] if n.endswith('stats.json') else record['sha256'])
                if digest.hexdigest()!=expected or digest.hexdigest()!=record['sha256'] or size!=record['bytes']: raise ValueError('Checksum mismatch: '+n)
                if n.endswith('manifest.json') and json.loads(tmp.read_text())!=frozen: raise ValueError('Dataset manifest mismatch')
                os.replace(tmp,dest)
                print('Verified: '+n,flush=True)
            finally: tmp.unlink(missing_ok=True)
    report={'status':'PASS','scope':'Three inference assets only; original backups unchanged','checkpoint_sha256':SHA,'dataset_id':DATASET,'training_launched':False}
    (workspace/'asset_import.json').write_text(json.dumps(report,indent=2));return report
