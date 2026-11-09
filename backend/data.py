"""Read real saved outputs and derive exact class labels from their palette."""
from pathlib import Path
import csv, json, sys
import numpy as np
from PIL import Image
from scipy import ndimage
from backend.acquisition import public_sources
from backend.quality import review_months
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'engine'))
from common import COLORS, CLASSES
NAMES=['Water','Trees','Grass','Flooded vegetation','Crops','Shrub & scrub','Built-up land','Bare ground','Snow & ice']
DESCRIPTIONS=['Open water, including rivers and lakes.','Tree-dominated cover; not individual tree detection.','Low herbaceous vegetation.','Vegetation associated with inundation; a weak class in this model.','Cultivated land; seasonal appearance may vary.','Shrubs and sparse woody vegetation.','Urban or impervious land; not individual building footprints.','Exposed soil, sand and rock.','Persistent or seasonal snow and ice.']
CLASSES_UI=[dict(id=i,key=k,name=NAMES[i],color=COLORS[i],description=DESCRIPTIONS[i]) for i,k in enumerate(CLASSES)]
def read(p,default=None):
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default

def decode(path):
    rgb=np.asarray(Image.open(path).convert('RGB'))
    if rgb.shape!=(256,256,3): raise ValueError('Expected original 256 x 256 class map')
    labels=np.full((256,256),255,np.uint8)
    for i,c in enumerate(COLORS): labels[(rgb==np.array(tuple(bytes.fromhex(c[1:])))).all(-1)]=i
    recognized=(labels<9)|(rgb==[28,39,51]).all(-1)
    if not recognized.all(): raise ValueError('Map contains colours outside the frozen class palette')
    return labels

def annotations(labels):
    anchors=[]
    for k in range(9):
        regions,n=ndimage.label(labels==k)
        if not n: continue
        sizes=np.bincount(regions.ravel());sizes[0]=0
        component=regions==sizes.argmax()
        if int(component.sum())<12: continue
        # Anchor inside the largest connected region, never at an empty centroid.
        dist=ndimage.distance_transform_edt(np.pad(component,1))[1:-1,1:-1]
        y,x=np.unravel_index(dist.argmax(),dist.shape)
        anchors.append(dict(class_id=k,x=float(x+.5),y=float(y+.5),pixels=int(component.sum())))
    return sorted(anchors,key=lambda a:-a['pixels'])[:5]

def build_case(folder,identifier):
    spec=read(folder/'request.json');completion=read(folder/'completion.json',{})
    with (folder/'monthly_shares.csv').open(newline='',encoding='utf-8') as f: shares=list(csv.DictReader(f))
    with (folder/'changes.csv').open(newline='',encoding='utf-8') as f: changes=list(csv.DictReader(f))
    months=[]
    for m in spec['months']:
        labels=decode(folder/f'map_{m}.png')
        rows=[row for row in shares if row['month']==m]
        radar=(folder/f'radar_{m}.png').exists()
        months.append(dict(month=m,acquisition=public_sources(folder,m),coverage=100*float((labels<9).mean()),annotations=annotations(labels),
            labels=labels.ravel().tolist(),radar=radar,shares=[dict(class_id=int(x['class_id']),
            percent=float(x['percent_full_aoi']),area=float(x['area_km2']),pixels=int(x['pixels'])) for x in rows if x['class']!='unobserved']))
    for m,quality in zip(months,review_months(months,read(folder/'ambiguity.json',{}))):m['quality']=quality
    loc='Mannheim, Germany' if abs(spec['latitude']-49.4875)<.0001 and abs(spec['longitude']-8.466)<.0001 else ('Cairo, Egypt' if abs(spec['latitude']-30.0444)<.0001 and abs(spec['longitude']-31.2357)<.0001 else f"{spec['latitude']:.4f}°, {spec['longitude']:.4f}°")
    loc=read(folder/'case_name.json',{}).get('name',loc)
    return dict(id=identifier,name=loc,spec=spec,completion=completion,months=months,classes=CLASSES_UI,
        reference=read(folder/'worldcover_comparison.json',{}),ambiguity=read(folder/'ambiguity.json',{}),
        changes=[x for x in changes if x['comparison']=='first_to_last'],identity=read(folder/'model_identity.json',{}),
        sample=identifier=='mannheim',exports=[p.name for p in folder.iterdir() if p.suffix in ('.csv','.json','.html','.tif') or p.name=='case_export.zip'])

def create_radar(folder):
    """Display only: fixed VV dB contrast; prediction inputs are never modified."""
    spec=read(folder/'request.json')
    with np.load(folder/'processed_sar.npz',allow_pickle=False) as z: db=z['db'];observed=z['observed']
    for m,img,valid in zip(spec['months'],db[:,0],observed):
        gray=np.clip((np.nan_to_num(img.astype(float),nan=-30)+30)/35*255,0,255).astype('uint8')
        rgba=np.stack([gray,gray,gray,valid.astype('uint8')*255],-1)
        Image.fromarray(rgba).save(folder/f'radar_{m}.png')
