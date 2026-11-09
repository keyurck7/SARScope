import unittest,sys,tempfile,json,zipfile,hashlib
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'engine'))
from backend.data import build_case,decode,annotations,create_radar,COLORS
from backend.assets import import_bundle,CHECKPOINT,WORK,DATASET
from backend import server
from pipeline import request_spec
from fastapi.testclient import TestClient
class LocalTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.data=build_case(ROOT/'sample/mannheim','mannheim');cls.client=TestClient(server.app)
 def test_monthly_maps_match_saved_area_counts(self):
  for m in self.data['months']:
   lab=np.array(m['labels']).reshape(256,256)
   for row in m['shares']:
    self.assertEqual(int((lab==row['class_id']).sum()),row['pixels'])
    self.assertAlmostEqual(row['area'],row['pixels']*.0001)
   self.assertAlmostEqual(sum(r['percent'] for r in m['shares']),m['coverage'])
 def test_annotations_are_in_predicted_regions(self):
  for m in self.data['months']:
   lab=np.array(m['labels']).reshape(256,256)
   for a in m['annotations']: self.assertEqual(lab[int(a['y']),int(a['x'])],a['class_id'])
 def test_unobserved_map_has_no_labels(self):
  self.assertEqual(annotations(np.full((256,256),255)),[])
 def test_unknown_palette_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'wrong.png';Image.new('RGB',(256,256),(1,2,3)).save(p)
   with self.assertRaises(ValueError):decode(p)
 def test_radar_display_keeps_mask_and_inputs(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'request.json').write_text(json.dumps({'months':['2021-01']}))
   db=np.full((1,2,256,256),-12,np.float16);obs=np.ones((1,256,256),bool);obs[0,0,0]=False
   np.savez(p/'processed_sar.npz',db=db,observed=obs);before=(p/'processed_sar.npz').read_bytes();create_radar(p)
   rgba=np.asarray(Image.open(p/'radar_2021-01.png'));self.assertEqual(rgba[0,0,3],0);self.assertEqual(rgba[1,1,3],255);self.assertEqual(before,(p/'processed_sar.npz').read_bytes())
 def test_request_boundaries(self):
  for args in [(91,0,'2021-01'),(0,180,'2021-01'),(float('nan'),0,'2021-01'),(0,0,'2099-01'),(0,0,'2021-13'),(0,0,'2014-01')]:
   with self.assertRaises(ValueError):request_spec(*args)
  c=request_spec(30.0444,31.2357,'2021-01');self.assertEqual(len(c['months']),12);self.assertEqual(c['grid']['dimensions'],{'width':256,'height':256})
 def test_review_routes(self):
  for path in ['/','/api/status','/api/cases','/api/evidence','/api/cases/mannheim','/api/cases/mannheim/files/map_2021-01.png','/api/cases/mannheim/files/monthly_shares.csv']:
   self.assertEqual(self.client.get(path).status_code,200,path)
 def test_private_files_not_served(self):
  for path in ['/api/cases/nope','/api/cases/mannheim/files/credentials','/api/cases/mannheim/files/predictions.npz','/api/jobs/invalid']:
   self.assertEqual(self.client.get(path).status_code,404)
 def test_post_origin_protection(self):
  body={'latitude':30,'longitude':31,'start_month':'2021-01','project':'example-project'}
  self.assertEqual(self.client.post('/api/analyze',json=body).status_code,403)
  self.assertEqual(self.client.post('/api/analyze',json=body,headers={'X-SARScope-Local':'1','Origin':'https://evil.invalid'}).status_code,403)
 def test_missing_assets_does_not_launch_job(self):
  with patch.object(server,'WORKSPACE',Path('/does/not/exist')),patch.object(server,'PREVIEW',False),patch.object(server.subprocess,'Popen') as spawn:
   r=self.client.post('/api/analyze',json={'latitude':30,'longitude':31,'start_month':'2021-01','project':'example-project'},headers={'X-SARScope-Local':'1'})
   self.assertEqual(r.status_code,409);spawn.assert_not_called()
 def test_bad_dates_do_not_launch_job(self):
  with patch.object(server,'PREVIEW',False),patch.object(server.subprocess,'Popen') as spawn:
   r=self.client.post('/api/analyze',json={'latitude':30,'longitude':31,'start_month':'2099-01','project':'example-project'},headers={'X-SARScope-Local':'1'})
   self.assertEqual(r.status_code,422);spawn.assert_not_called()
 def test_import_rejects_wrong_dataset(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'bad.zip'
   with zipfile.ZipFile(p,'w') as z:z.writestr('RESTORE_MANIFEST.json',json.dumps({'dataset_id':'wrong','checkpoint':CHECKPOINT}))
   with self.assertRaises(ValueError):import_bundle(p,Path(d)/'work')
 def test_import_rejects_checkpoint_tampering(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'bad.zip';frozen=(ROOT/'engine/evidence/manifest.json').read_bytes()
   payloads={CHECKPOINT:b'fake checkpoint',WORK+'/prepared/stats.json':b'{}',WORK+'/prepared/manifest.json':frozen}
   meta={'dataset_id':DATASET,'checkpoint':CHECKPOINT,'files':{k:{'bytes':len(v),'sha256':hashlib.sha256(v).hexdigest()} for k,v in payloads.items()}}
   with zipfile.ZipFile(p,'w') as z:
    z.writestr('RESTORE_MANIFEST.json',json.dumps(meta))
    for k,v in payloads.items():z.writestr(k,v)
   with self.assertRaisesRegex(ValueError,'Checksum mismatch'):import_bundle(p,Path(d)/'work')
   self.assertFalse((Path(d)/'work/restored'/CHECKPOINT).exists())
 def test_selective_restore_extracts_only_verified_assets(self):
  from backend import assets
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);evidence=root/'engine/evidence';evidence.mkdir(parents=True)
   stats=b'{"vv": 1}';checkpoint=b'synthetic-import-fixture-not-a-model'
   manifest={'complete':True,'arrays_and_metadata_sha256':{'stats.json':hashlib.sha256(stats).hexdigest()}}
   (evidence/'manifest.json').write_text(json.dumps(manifest))
   payloads={CHECKPOINT:checkpoint,WORK+'/prepared/stats.json':stats,WORK+'/prepared/manifest.json':json.dumps(manifest).encode()}
   meta={'dataset_id':DATASET,'checkpoint':CHECKPOINT,'files':{k:{'bytes':len(v),'sha256':hashlib.sha256(v).hexdigest()} for k,v in payloads.items()}}
   archive=root/'fixture.zip'
   with zipfile.ZipFile(archive,'w') as z:
    z.writestr('RESTORE_MANIFEST.json',json.dumps(meta))
    for k,v in payloads.items():z.writestr(k,v)
    z.writestr('../outside.txt','must not extract')
    z.writestr('unneeded.dat','must not extract')
   with patch.object(assets,'ROOT',root),patch.object(assets,'SHA',hashlib.sha256(checkpoint).hexdigest()):
    result=import_bundle(archive,root/'workspace')
   self.assertEqual(result['status'],'PASS')
   self.assertEqual((root/'workspace/restored'/CHECKPOINT).read_bytes(),checkpoint)
   self.assertFalse((root/'outside.txt').exists());self.assertFalse((root/'workspace/restored/unneeded.dat').exists())
 def test_host_header_protection(self):
  self.assertEqual(self.client.get('/api/cases',headers={'Host':'attacker.invalid'}).status_code,400)

 def test_latest_window_rollover_and_leap_year(self):
  from datetime import date
  from backend.acquisition import latest_start
  for today,expected in [(date(2026,11,9),'2025-11'),(date(2026,1,1),'2025-01'),(date(2024,3,1),'2023-03')]:
   self.assertEqual(latest_start(today),expected)
 def test_latest_request_is_resolved_on_server(self):
  from unittest.mock import MagicMock
  with tempfile.TemporaryDirectory() as d, patch.object(server,'WORKSPACE',Path(d)), patch.object(server,'PREVIEW',False), patch.object(server,'process',None), patch.object(server,'active',None), patch.object(server,'status',return_value={'ready':True}), patch.object(server,'latest_start',return_value='2025-01'), patch.object(server.subprocess,'Popen',return_value=MagicMock()) as spawn:
   r=self.client.post('/api/analyze',json={'latitude':30.0444,'longitude':31.2357,'start_month':'2021-01','period_mode':'latest_completed','project':'example-project'},headers={'X-SARScope-Local':'1'})
   self.assertEqual(r.status_code,200)
   stored=json.loads((Path(d)/'jobs'/f"{r.json()['job_id']}.json").read_text())
   self.assertEqual(stored['start_month'],'2025-01');self.assertEqual(stored['latitude'],30.0444)
   self.assertEqual(stored['period_mode'],'latest_completed');spawn.assert_called_once()
 def test_acquisition_dates_are_observation_dates_not_download_dates(self):
  from backend.acquisition import public_sources
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)
   self.assertFalse(public_sources(p,'2021-01')['available'])
   receipt={'identity':{'month':'2021-01'},'source_indices':['a','b'],'source_timestamps_ms':[1609459200000,1612051200000],'retrieved_at':'2026-11-09T00:00:00Z'}
   (p/'acquisition_receipts.json').write_text(json.dumps([receipt]))
   result=public_sources(p,'2021-01')
   self.assertEqual(result['source_count'],2);self.assertEqual(result['earliest_acquisition'],'2021-01-01T00:00:00Z');self.assertEqual(result['latest_acquisition'],'2021-01-31T00:00:00Z')
   self.assertEqual(result['retrieved_at'],'2026-11-09T00:00:00Z')
   self.assertFalse(public_sources(p,'2021-02')['available'])
   del receipt['source_timestamps_ms'];(p/'acquisition_receipts.json').write_text(json.dumps([receipt]))
   self.assertIsNone(public_sources(p,'2021-01')['latest_acquisition'])
 def test_worker_runs_requested_case_and_exports_real_underlay(self):
  from backend import worker
  from unittest.mock import MagicMock
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);case=p/'abc';case.mkdir()
   (case/'map_2021-01.png').write_bytes(b'prediction fixture')
   (case/'processed_sar.npz').write_bytes(b'private fixture')
   request=p/'job.json';request.write_text(json.dumps({'workspace':str(p),'latitude':30.0444,'longitude':31.2357,'start_month':'2021-01','project':'example-project'}))
   def radar(folder): (folder/'radar_2021-01.png').write_bytes(b'underlay fixture')
   with patch.object(worker,'run_case',return_value=case) as run, patch.object(worker,'create_radar',side_effect=radar), patch.object(sys,'argv',['worker.py',str(request)]):worker.main()
   self.assertEqual(run.call_args.args[:5],(str(p),30.0444,31.2357,'2021-01','example-project'))
   self.assertEqual(json.loads(request.with_suffix('.status.json').read_text())['state'],'complete')
   with zipfile.ZipFile(case/'case_export.zip') as z:
    self.assertIn('radar_2021-01.png',z.namelist());self.assertIn('request_context.json',z.namelist());self.assertNotIn('processed_sar.npz',z.namelist())

if __name__=='__main__':unittest.main(verbosity=2)
