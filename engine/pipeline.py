"""Historical 12-month Sentinel-1 retrieval, frozen preprocessing and inference."""
from common import *
import datetime as dt
import re
import time
import numpy as np
from s1lulc.geo import make_grid
from sarscope_baseline.core import preprocess, confusion, scores

def request_spec(lat, lon, start):
    if not np.isfinite([lat,lon]).all() or not -79 <= lat <= 83 or not -179 <= lon <= 179:
        raise ValueError('Use latitude −79…83 and longitude −179…179; polar/antimeridian AOIs are outside this prototype')
    if not re.fullmatch(r'\d{4}-\d{2}', start): raise ValueError('Start month must be YYYY-MM')
    first=dt.date.fromisoformat(start+'-01')
    if first < dt.date(2015,1,1): raise ValueError('Choose January 2015 or later')
    windows=[]; y,m=first.year,first.month
    for _ in range(12):
        ny,nm=(y+1,1) if m==12 else (y,m+1)
        windows.append([f'{y:04d}-{m:02d}-01',f'{ny:04d}-{nm:02d}-01',f'{y:04d}-{m:02d}'])
        y,m=ny,nm
    if dt.date.fromisoformat(windows[-1][1]) > dt.datetime.now(dt.timezone.utc).date():
        raise ValueError('All 12 calendar months must have ended; this is a retrospective model')
    grid,bbox=make_grid(lat,lon)
    return {'latitude':lat,'longitude':lon,'start_month':start,'months':[w[2] for w in windows],
            'windows':windows,'grid':grid,'bbox':bbox,'recipe':'frozen-upstream-RTC-linear-mean_then_Lee5-dB',
            'retrospective_context':True,'tile_width_m':2560}

def fetch_pixels(image, grid, bands):
    import ee
    for attempt in range(3):
        try:
            array=ee.data.computePixels({'expression':image,'fileFormat':'NUMPY_NDARRAY','grid':grid,'bandIds':bands})
            if set(array.dtype.names or []) != set(bands): raise ValueError('Unexpected Earth Engine bands')
            result=np.stack([array[b] for b in bands])
            if result.shape != (len(bands),256,256): raise ValueError('Unexpected raster dimensions')
            return result
        except Exception as exc:
            transient=any(s in str(exc).lower() for s in ('429','500','502','503','504','timed out','timeout','temporarily','too many concurrent'))
            if not transient or attempt==2: raise
            time.sleep(2*(attempt+1))

def save_npz(path, **arrays):
    path=Path(path); tmp=path.with_suffix('.tmp')
    with tmp.open('wb') as f: np.savez_compressed(f,**arrays)
    os.replace(tmp,path)

def read_cached(path, identity):
    receipt=path.with_suffix('.json')
    if not path.exists() or not receipt.exists(): return None
    saved=read(receipt)
    if saved.get('identity') != identity or saved.get('sha256') != sha256(path):
        raise ValueError('Cached acquisition identity/checksum mismatch: '+str(path))
    with np.load(path,allow_pickle=False) as z: return z['pixels']

def retrieve(spec, folder, project, progress=print):
    import ee
    from s1lulc import gee
    cache=folder/'cache';cache.mkdir(parents=True,exist_ok=True)
    geom=None; elevation=None
    raw=[]
    for start,end,month in spec['windows']:
        identity={'spec':spec,'month':month,'source_code_sha256':sha256(ROOT/'vendor/s1lulc/gee.py')}
        path=cache/f's1_{month}.npz'
        pixels=read_cached(path,identity)
        if pixels is None:
            progress(f'Retrieving Sentinel-1: {month} (terrain correction + linear monthly mean)')
            if geom is None:
                gee.init(project); ee.data.setDeadline(120000)
                geom=ee.Geometry.Rectangle(spec['bbox'])
            if elevation is None: elevation=gee.dem()
            col=gee.s1_collection(geom,start,end)
            indices=col.aggregate_array('system:index').getInfo()
            source_times=col.aggregate_array('system:time_start').getInfo()
            image=gee.s1_month(geom,geom.centroid().buffer(20000),start,end,elevation,flatten=True)
            pixels=fetch_pixels(image,spec['grid'],['VV','VH','n']).astype(np.float32)
            counts=pixels[2]
            if not np.isfinite(counts).all() or (counts<0).any() or (counts!=np.floor(counts)).any():
                raise ValueError('Invalid observation counts in '+month)
            save_npz(path,pixels=pixels)
            write(path.with_suffix('.json'),{'identity':identity,'sha256':sha256(path),
                'collection':'COPERNICUS/S1_GRD_FLOAT','source_indices':indices,
                'source_timestamps_ms':source_times,
                'retrieved_at':utc(),'orbit_policy':'Both ascending and descending, as in training',
                'valid_pixels':int(((pixels[:2]>0).all(0)&(counts>0)).sum())})
        else: progress('Reusing verified monthly cache: '+month)
        raw.append(pixels)
    return np.concatenate(raw)

def geotiff(path, array, grid, nodata=255):
    import rasterio
    from affine import Affine
    a=grid['affineTransform']; array=np.asarray(array)
    if array.ndim==2: array=array[None]
    transform=Affine(a['scaleX'],a['shearX'],a['translateX'],a['shearY'],a['scaleY'],a['translateY'])
    with rasterio.open(path,'w',driver='GTiff',height=array.shape[-2],width=array.shape[-1],
        count=len(array),dtype=array.dtype,crs=grid['crsCode'],transform=transform,nodata=nodata,compress='deflate') as dst:
        dst.write(array)
        if array.dtype==np.uint8:
            dst.write_colormap(1,{**{i:tuple(bytes.fromhex(c[1:]))+(255,) for i,c in enumerate(COLORS)},255:(20,28,39,0)})

def reference_check(spec, folder, labels, project='gae-application-308005'):
    """Annual reference comparison, never a model input or a monthly truth claim."""
    if spec['start_month']!='2021-01':
        info={'status':'NOT_APPLICABLE','reason':'WorldCover 2021 comparison requires the January–December 2021 case'}
        write(folder/'worldcover_comparison.json',info);return info
    from s1lulc import gee
    path=folder/'cache/worldcover2021.npz'
    identity={'collection':'ESA/WorldCover/v200','grid':spec['grid'],'resampling':'nearest'}
    raw=read_cached(path,identity)
    if raw is None:
        gee.init(project)
        raw=fetch_pixels(gee.worldcover().unmask(0),spec['grid'],['Map'])
        save_npz(path,pixels=raw)
        write(path.with_suffix('.json'),{'identity':identity,'sha256':sha256(path),'retrieved_at':utc()})
    reference=np.full(raw.shape[1:],255,np.uint8)
    mapping={80:0,10:1,30:2,90:3,40:4,20:5,50:6,60:7,70:8}
    for wc,k in mapping.items(): reference[raw[0]==wc]=k
    count=np.stack([(labels==k).sum(0) for k in range(9)])
    majority=count.argmax(0).astype(np.uint8)
    maxima=count.max(0); unique=(count==maxima[None]).sum(0)==1
    observed=(labels<9).sum(0)
    # Require all twelve observations and a unique modal class for an annual comparison.
    valid=(reference<9)&(observed==12)&unique
    masked=np.where(valid,reference,255).astype(np.uint8)
    metrics=scores(confusion(masked,majority))
    metrics.update(status='COMPLETE' if valid.any() else 'INSUFFICIENT_SUPPORT', reference='ESA WorldCover 2021 v200; external annual map, not monthly ground truth',
        taxonomy_mapping={str(k):CLASSES[v] for k,v in mapping.items()}, excluded_codes=[0,95,100],
        annual_prediction='Unique modal class across 12 predictions; require all 12 valid observations; ties excluded',
        comparable_pixels=int(valid.sum()), comparable_aoi_percent=100*float(valid.mean()),
        caveat='Broad crosswalk only: herbaceous wetland is not identical to flooded vegetation. Both products have errors and share sensor families; agreement is not independent ground-truth accuracy.')
    if not valid.any():metrics['reason']='No comparable pixels with all twelve observations and a unique annual modal class'
    write(folder/'worldcover_comparison.json',metrics)
    geotiff(folder/'worldcover_2021_mapped.tif',reference,spec['grid'])
    majority[~((observed==12)&unique)]=255
    geotiff(folder/'annual_mode.tif',majority,spec['grid'])
    save_npz(folder/'reference_maps.npz',reference=reference,annual_mode=majority,comparison_mask=valid)
    return metrics

def run_case(vault, lat=49.4875, lon=8.4660, start='2021-01', project='gae-application-308005', progress=print):
    from model import load,predict
    from accounting import save_tables
    from presentation import render_case
    spec=request_spec(lat,lon,start)
    net,cfg,stats,identity=load(vault)
    _,_,_,output=locate(vault)
    folder=output/'cases'/canonical_hash(spec)[:16];folder.mkdir(parents=True,exist_ok=True)
    write(folder/'request.json',spec)
    write(folder/'model_identity.json',identity)
    progress('Retrieving/reusing twelve historical months. No optical input enters the model.')
    raw=retrieve(spec,folder,project,progress)
    db,observed=preprocess(raw)
    if not observed.any(): raise ValueError('No valid SAR observations anywhere in the requested window')
    progress('Running fixed FP32 checkpoint on all twelve months...')
    labels,probabilities=predict(net,stats,db)
    save_npz(folder/'predictions.npz',labels=labels,probabilities=probabilities)
    save_npz(folder/'processed_sar.npz',db=db,observed=observed)
    for month,lab in zip(spec['months'],labels): geotiff(folder/f'landcover_{month}.tif',lab,spec['grid'])
    save_tables(folder,labels,spec['months'])
    reference_status='PENDING'
    try:
        progress('Comparing annual map with WorldCover 2021, separately from model inference...')
        info=reference_check(spec,folder,labels,project);reference_status=info['status']
    except Exception as exc:
        write(folder/'worldcover_comparison.json',{'status':'FAILED','error':str(exc),
            'reference':'ESA WorldCover 2021; case predictions were saved and are available'})
        reference_status='FAILED';progress('Case maps saved; external reference check needs retry: '+str(exc))
    write(folder/'completion.json',{'status':'COMPLETE' if reference_status in ('COMPLETE','NOT_APPLICABLE') else 'PARTIAL',
        'inference_complete':True,'reference_status':reference_status,'completed_at':utc(),
        'checkpoint_sha256':identity['checkpoint_sha256'],'training_launched':False,
        'observed_pixel_months':int(observed.sum()),'total_pixel_months':int(observed.size)})
    # Public acquisition receipts contain source IDs and checksums, never authentication material.
    write(folder/'acquisition_receipts.json',[read(p) for p in sorted((folder/'cache').glob('*.json'))])
    render_case(folder)
    with zipfile.ZipFile(folder/'case_export.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(folder.iterdir()):
            if p.is_file() and p.suffix in {'.csv','.json','.html','.png','.tif'}: z.write(p,p.name)
    progress('Case ready: '+str(folder/'case_report.html'))
    return folder
