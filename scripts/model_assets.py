#!/usr/bin/env python3
"""Verify and restore the frozen SARScope checkpoint without committing private assets."""
from __future__ import annotations
import argparse,hashlib,json,os,sys,urllib.request,urllib.parse
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.assets import CHECKPOINT,SHA,import_bundle

WORKSPACE=Path(os.environ.get('SARSCOPE_WORKSPACE',str(ROOT/'workspace'))).expanduser().resolve()

def hash_file(p:Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for piece in iter(lambda:f.read(4*1024*1024),b''): h.update(piece)
    return h.hexdigest()

def status()->dict:
    ck=WORKSPACE/'restored'/CHECKPOINT
    st=WORKSPACE/'restored'/'sarscope-baseline-20261108'/'prepared'/'stats.json'
    mf=st.parent/'manifest.json'
    result={'workspace':str(WORKSPACE),'weights_present':ck.is_file(),'stats_present':st.is_file(),'manifest_present':mf.is_file(),'expected_sha256':SHA}
    if ck.is_file():
        result['weights_sha256']=hash_file(ck)
        result['weights_verified']=result['weights_sha256']==SHA
    return result

def fetch_archive(url:str,archive_sha256:str|None)->Path:
    parsed=urllib.parse.urlparse(url)
    if parsed.scheme!='https' or not parsed.hostname: raise ValueError('Only HTTPS artifact URLs are accepted')
    token=os.environ.get('SARSCOPE_ASSET_TOKEN','').strip()
    # A short-lived scoped token is optional. Never print it or place it in the URL.
    request=urllib.request.Request(url,headers=({'Authorization':'Bearer '+token} if token else {}))
    target=WORKSPACE/'downloads'/'SARScope_selected_restore.zip'
    target.parent.mkdir(parents=True,exist_ok=True)
    partial=target.with_name(target.name+'.partial')
    h=hashlib.sha256()
    try:
        with urllib.request.urlopen(request,timeout=120) as source:
            if urllib.parse.urlparse(source.geturl()).scheme!='https': raise ValueError('Artifact URL redirected to non-HTTPS')
            with partial.open('wb') as dest:
                while data:=source.read(4*1024*1024):
                    dest.write(data); h.update(data)
        digest=h.hexdigest()
        if archive_sha256 and digest.lower()!=archive_sha256.lower(): raise ValueError('Archive SHA-256 verification failed')
        os.replace(partial,target)
        print('Downloaded archive SHA-256:',digest)
        return target
    finally:
        partial.unlink(missing_ok=True)

def main():
    cli=argparse.ArgumentParser(description=__doc__)
    sub=cli.add_subparsers(dest='command',required=True)
    sub.add_parser('status')
    imp=sub.add_parser('import-archive');imp.add_argument('--archive',required=True,type=Path)
    dl=sub.add_parser('download');dl.add_argument('--url',default=os.environ.get('SARSCOPE_BUNDLE_URL'));dl.add_argument('--sha256',default=os.environ.get('SARSCOPE_BUNDLE_SHA256'))
    args=cli.parse_args()
    if args.command=='status':print(json.dumps(status(),indent=2));return
    if args.command=='import-archive':
        if not args.archive.is_file():cli.error('Cannot find original restore archive: '+str(args.archive))
        print(json.dumps(import_bundle(args.archive,WORKSPACE),indent=2))
    else:
        if not args.url:cli.error('Pass --url or set SARSCOPE_BUNDLE_URL')
        p=fetch_archive(args.url,args.sha256)
        print(json.dumps(import_bundle(p,WORKSPACE),indent=2))
    if not status().get('weights_verified'):raise RuntimeError('Weights are not verified')
    print('Frozen checkpoint installed and SHA-256 verified; run local_tools.py smoke after inference dependencies are installed.')
if __name__=='__main__':main()
