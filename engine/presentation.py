"""Readable, offline result pages and figures built only from saved results."""
from common import *
import base64
import csv
import html
import numpy as np

STYLE = '''body{margin:0;background:#edf1f4;color:#172735;font:16px/1.6 system-ui,sans-serif}main{max-width:1160px;margin:auto;padding:40px 28px}header{background:#112b3d;color:white;padding:34px;border-radius:18px}h1{font-size:42px;letter-spacing:-1.5px;margin:8px 0}h2{margin-top:36px}small,.muted{color:#596b79}.tag{letter-spacing:3px;font-size:12px;color:#86d5c5}section,.card{background:white;border-radius:14px;padding:24px;margin:20px 0;border:1px solid #dce4ea}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}.grid article{background:white;border-radius:12px;overflow:hidden;border:1px solid #dce4ea}.grid img{width:100%;image-rendering:pixelated}.grid p{padding:0 12px;margin:6px 0 12px}.legend{display:flex;gap:14px;flex-wrap:wrap}.swatch{display:inline-block;width:12px;height:12px;margin-right:6px;border-radius:3px}table{width:100%;border-collapse:collapse;font-size:14px}td,th{border-bottom:1px solid #dce4ea;text-align:left;padding:9px}th{background:#f1f5f7}img.figure{width:100%;height:auto}a{color:#086e78}.notice{border-left:4px solid #c38e32;padding-left:18px}button{padding:8px 16px;border:0;background:#0b716e;color:white;border-radius:6px}input[type=range]{width:100%}@media(max-width:700px){.grid{grid-template-columns:repeat(2,1fr)}main{padding:14px}h1{font-size:32px}}@media print{body{background:white}main{padding:0}section{break-inside:avoid}.grid article{break-inside:avoid}header{color:#172735;background:#eef4f7}button,input{display:none}}'''

def embedded(path):
    return 'data:image/png;base64,'+base64.b64encode(Path(path).read_bytes()).decode()

def rgb_labels(labels):
    palette=np.array([tuple(bytes.fromhex(c[1:])) for c in COLORS],np.uint8)
    out=np.zeros((*labels.shape,3),np.uint8);out[:]=[28,39,51]
    valid=labels<9;out[valid]=palette[labels[valid]]
    return out

def legend():
    return '<div class="legend" style="display:flex;gap:14px;flex-wrap:wrap">'+''.join(f'<span><i class="swatch" style="background:{c};display:inline-block;width:12px;height:12px;margin-right:6px"></i>{n.replace("_"," ")}</span>' for n,c in zip(CLASSES+['unobserved'],COLORS+['#1c2733']))+'</div>'

def pct(value):
    return '—' if value is None else f'{value*100:.2f}%'

def render_case(folder):
    from PIL import Image
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    folder=Path(folder);spec=read(folder/'request.json');completion=read(folder/'completion.json')
    with np.load(folder/'predictions.npz') as z: labels=z['labels'];probs=z['probabilities']
    cards=[];images=[]
    for i,month in enumerate(spec['months']):
        p=folder/f'map_{month}.png';Image.fromarray(rgb_labels(labels[i])).save(p)
        images.append(embedded(p));coverage=float((labels[i]<9).mean())*100
        cards.append(f'<article><img src="{images[-1]}" alt="Predicted land cover {month}"><p><b>{month}</b><br><small>{coverage:.1f}% observed</small></p></article>')
    with (folder/'monthly_shares.csv').open() as f: rows=list(csv.DictReader(f))
    fig,ax=plt.subplots(figsize=(11,4.4),layout='constrained')
    for k,(name,color) in enumerate(zip(CLASSES,COLORS)):
        ax.plot(spec['months'],[float(r['percent_full_aoi']) for r in rows if r['class']==name],label=name.replace('_',' '),color=color,lw=2)
    ax.plot(spec['months'],[float(r['percent_full_aoi']) for r in rows if r['class']=='unobserved'],label='unobserved',color='#172735',ls='--')
    ax.set_ylabel('Percent of fixed AOI');ax.set_ylim(0,100);ax.tick_params(axis='x',labelrotation=40)
    ax.grid(alpha=.2);ax.legend(ncol=5,fontsize=8,loc='upper center',bbox_to_anchor=(.5,1.25))
    fig.savefig(folder/'monthly_shares.png',dpi=150);plt.close(fig)
    with (folder/'changes.csv').open() as f: changes=list(csv.DictReader(f))
    firstlast=[r for r in changes if r['comparison']=='first_to_last']
    table=''.join('<tr><td>'+r['class'].replace('_',' ')+'</td><td>'+ (f"{float(r['before_percent']):.2f}%" if r['before_percent'] else '—')+'</td><td>'+ (f"{float(r['after_percent']):.2f}%" if r['after_percent'] else '—')+'</td><td>'+ (f"{float(r['change_percentage_points']):+.2f}" if r['change_percentage_points'] else '—')+'</td></tr>' for r in firstlast)
    reference=read(folder/'worldcover_comparison.json')
    reftext='Reference comparison unavailable: '+html.escape(reference.get('reason',reference.get('error','pending')))
    if reference['status']=='COMPLETE':
        reftext=f'WorldCover 2021 agreement on {reference["comparable_aoi_percent"]:.1f}% of the AOI: OA {pct(reference["OA"])}, mIoU {pct(reference["mIoU"])}. This compares an annual external map with the unique modal prediction across all 12 observed months. It does not validate individual monthly changes.'
        with np.load(folder/'reference_maps.npz') as z:
            for key in ['reference','annual_mode']:
                Image.fromarray(rgb_labels(z[key])).save(folder/f'{key}.png')
        reftext+=f'<div class="grid"><article><img src="{embedded(folder/"reference.png")}"><p>WorldCover crosswalk</p></article><article><img src="{embedded(folder/"annual_mode.png")}"><p>Annual modal prediction</p></article></div>'
    ambiguity=[]
    for p in probs:
        valid=np.isfinite(p).all(0)
        entropy=-(np.nan_to_num(p)*np.log(np.clip(np.nan_to_num(p),1e-9,1))).sum(0)/np.log(9)
        ambiguity.append(float(entropy[valid].mean()) if valid.any() else None)
    write(folder/'ambiguity.json',{'measure':'Mean normalized predictive entropy over observed pixels; uncalibrated model ambiguity, not error probability',
                                 'months':spec['months'],'values':ambiguity})
    body=f'''<header><div class="tag">SARSCOPE · RESEARCH PROTOTYPE</div><h1>A year of land cover</h1><p>{spec['latitude']:.4f}° latitude · {spec['longitude']:.4f}° longitude<br>{spec['months'][0]} — {spec['months'][-1]} · 2.56 × 2.56 km · 10 m grid</p></header>
    <section><b>Sentinel-1 radar inputs. Nine predicted land-cover classes.</b><p class="notice">These are model predictions, with known class errors. Annual context makes this a retrospective analysis. Seasonal variation and classification error can look like change. Optical data are used only for external comparison, never as inference features.</p>{legend()}</section>
    <section><h2 style="margin-top:0">Explore the months</h2><label id="monthlabel">{spec['months'][0]}</label><input id="month" type="range" min="0" max="11" value="0"><img id="active" style="max-width:512px;width:100%;image-rendering:pixelated" src="{images[0]}" alt="Selected monthly prediction"><p class="muted">North up; each square is the same fixed UTM tile. Dark pixels have no valid observation.</p></section>
    <h2>Twelve monthly predictions</h2><div class="grid">{''.join(cards)}</div>
    <section><h2 style="margin-top:0">Area composition</h2><img class="figure" src="{embedded(folder/'monthly_shares.png')}"><p>Percentages use the full fixed AOI, including unobserved pixels. Areas use projected 10 × 10 m pixels; they are not geodesic measurements.</p></section>
    <section><h2 style="margin-top:0">First-to-last change</h2><p>Change in <b>percentage points</b>, on pixels observed in both months. Common coverage: {float(firstlast[0]['common_coverage_percent']):.1f}%.</p><table><tr><th>Class</th><th>{spec['months'][0]}</th><th>{spec['months'][-1]}</th><th>Change (pp)</th></tr>{table}</table><p>Consecutive-month comparisons and transition matrices are included in the CSV/JSON export. A net change can hide opposing transitions.</p></section>
    <section><h2 style="margin-top:0">External annual sanity check</h2><p>{reftext}</p><p class="muted">Mangrove, moss/lichen and no-data reference classes are excluded. Wetland/flooded-vegetation definitions differ. This is reference-map agreement, not verified ground truth.</p></section>
    <section><b>Reproducible case</b><p>GeoTIFFs, class-share CSV, change CSV, source receipts, model identity and request geometry accompany this page. The selected model's earlier validation mIoU was 36.40%; final held-out test results are reported separately.</p><button onclick="window.print()">Print / save PDF</button></section>'''
    script='const images='+json.dumps(images)+'; const months='+json.dumps(spec['months'])+'; document.getElementById("month").oninput=function(){document.getElementById("active").src=images[this.value];document.getElementById("monthlabel").textContent=months[this.value];};'
    (folder/'case_report.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SARScope | Monthly land cover</title><style>'+STYLE+'</style><main>'+body+'</main><script>'+script+'</script></html>',encoding='utf-8')

def render_evaluation(output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    output=Path(output);target=output/'evaluation';target.mkdir(parents=True,exist_ok=True)
    history=read(ROOT/'evidence/history.json')
    fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    epochs=[r['epoch'] for r in history]
    for key,label in [('train_CE','Training'),('validation_CE','Validation')]: axes[0].plot(epochs,[r[key] for r in history],label=label)
    axes[0].set(xlabel='Epoch',ylabel='Cross entropy');axes[0].legend();axes[0].grid(alpha=.2)
    axes[1].plot(epochs,[r['validation_mIoU']*100 for r in history],color='#117b77')
    axes[1].axvline(13,color='#ad6b21',ls='--',label='Selected epoch 13');axes[1].legend()
    axes[1].set(xlabel='Epoch',ylabel='Validation mIoU (%)');axes[1].grid(alpha=.2)
    fig.savefig(target/'training_curves.png',dpi=150);plt.close(fig)
    val=read(ROOT/'evidence/best_validation.json')
    test=read(target/'test_metrics.json') if (target/'test_metrics.json').exists() else None
    rows=[]
    for k,name in enumerate(CLASSES):
        rows.append({'class':name,'validation_IoU':val['IoU'][k],'validation_F1':val['F1'][k],
                     'test_IoU':test['IoU'][k] if test else None,'test_F1':test['F1'][k] if test else None,
                     'test_reference_pixels':test['reference_support'][k] if test else None})
    with (target/'per_class.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    if test:
        cm=np.asarray(test['confusion_true_rows_predicted_columns'],float)
        normalized=np.divide(cm,cm.sum(1,keepdims=True),out=np.zeros_like(cm),where=cm.sum(1,keepdims=True)>0)
        fig,ax=plt.subplots(figsize=(9,7),layout='constrained');im=ax.imshow(normalized,cmap='Blues',vmin=0,vmax=1)
        ax.set_xticks(range(9),[n.replace('_',' ') for n in CLASSES],rotation=60,ha='right')
        ax.set_yticks(range(9),[n.replace('_',' ') for n in CLASSES]);ax.set(xlabel='Predicted class',ylabel='Dynamic World weak-label class',title='Held-out test confusion · normalized by reference class')
        for i in range(9):
            for j in range(9): ax.text(j,i,f'{normalized[i,j]:.2f}',ha='center',va='center',fontsize=8,color='white' if normalized[i,j]>.55 else 'black')
        fig.colorbar(im,ax=ax);fig.savefig(target/'test_confusion.png',dpi=150);plt.close(fig)
    table=''.join('<tr><td>'+r['class'].replace('_',' ')+'</td>'+''.join('<td>'+pct(r[k])+'</td>' for k in ['validation_IoU','validation_F1','test_IoU','test_F1'])+'</tr>' for r in rows)
    body=f'<header><div class="tag">SARSCOPE · MODEL EVALUATION</div><h1>Evidence before claims</h1><p>Frozen U-Net / ResNet34 · FP32 · annual-context features · nine classes</p></header><section><h2>Selected checkpoint</h2><p>Seed 42, epoch 13. Validation OA {pct(val["OA"])}, mIoU {pct(val["mIoU"])}. Selected without test metrics.</p><p>Held-out test: '+(f'OA {pct(test["OA"])}, mIoU {pct(test["mIoU"])}.' if test else 'Not evaluated yet.')+'</p><p>Reference labels are monthly Dynamic World labels; these scores measure agreement with weak labels, not independently surveyed truth.</p></section><section><img class="figure" src="'+embedded(target/'training_curves.png')+'"></section><section><h2>Per-class performance</h2><table><tr><th>Class</th><th>Val IoU</th><th>Val F1</th><th>Test IoU</th><th>Test F1</th></tr>'+table+'</table></section>'
    if test: body+='<section><img class="figure" src="'+embedded(target/'test_confusion.png')+'"></section>'
    body+='<section><p>Classes absent in both reference and prediction have null IoU/F1 and are excluded from mIoU. False-positive-only classes receive zero IoU. Per-region and per-month results are in the JSON. The class-balanced experiment was inconclusive over three seeds and was not selected.</p></section>'
    (target/'evaluation_report.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><title>SARScope evaluation</title><style>'+STYLE+'</style><main>'+body+'</main></html>',encoding='utf-8')
