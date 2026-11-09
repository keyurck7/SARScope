"""One inference process; fixed model and persistent monthly cache."""
import sys,json,os,traceback,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'engine'))
from common import write,utc
from pipeline import run_case
from backend.data import create_radar

def main():
    request=Path(sys.argv[1]);args=json.loads(request.read_text());status=request.with_suffix('.status.json');messages=[];requested_at=utc()
    def progress(message):
        messages.append(str(message));print(message,flush=True)
        write(status,{'state':'running','messages':messages[-50:],'updated_at':utc()})
    try:
        progress(f"Window starts {args['start_month']}: 12 completed calendar months; not a live satellite feed.")
        progress('Checking the frozen checkpoint and preparing CPU inference…')
        folder=run_case(args['workspace'],args['latitude'],args['longitude'],args['start_month'],args['project'],progress)
        progress('Preparing radar underlays and map exports…');create_radar(folder)
        write(folder/'request_context.json',{'period_mode':args.get('period_mode','historical'),'resolved_start_month':args['start_month'],'requested_at':requested_at,'imagery_policy':'Download missing months; reuse only checksum-verified cached months. Not a real-time feed.','temporal_validation':'Model trained on 2021; other years are not separately validated.'})
        # The engine export precedes display generation; rebuild to include genuine radar underlays.
        with zipfile.ZipFile(folder/'case_export.zip','w',zipfile.ZIP_DEFLATED) as z:
            for f in sorted(folder.iterdir()):
                if f.is_file() and f.suffix in {'.csv','.json','.html','.png','.tif'}: z.write(f,f.name)
        write(status,{'state':'complete','case_id':folder.name,'messages':messages[-50:],'updated_at':utc()})
    except Exception as e:
        traceback.print_exc()
        write(status,{'state':'failed','error':str(e),'messages':messages[-50:],'updated_at':utc()})
        raise SystemExit(1)
if __name__=='__main__': main()
