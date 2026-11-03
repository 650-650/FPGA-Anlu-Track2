"""MODEL ONLY V10 shadow-preserving 50% alternatives; frozen production unchanged."""
from pathlib import Path
import json,hashlib,time
import numpy as np
from PIL import Image,ImageDraw
import cartoon_v9_model as old,cartoon_v10_model as new,guide_v8_model as gm
from denoise_v8_model import filter_rgb
R=Path(__file__).resolve().parents[1];V=R/'validation/cartoon_v10';start=time.time()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
source=sha(R/'user_source/hdl_source/isp/stylize_v5_96.v')
def colour_hybrid(pixel,keep_chroma=False):
 p=np.asarray(pixel,dtype=np.int64);_,f=new.colour(p);y=f['y'];r=y%64
 delta=np.where(r<16,r//2,np.where(r<48,(32-r)//2,(r-64)//2));delta=np.where(y<32,0,delta)
 s64=y-r+np.where(r<16,2*r,np.where(r<48,32,2*r-64));s64=np.where(y>=224,y,s64)
 yq=np.where(y<64,y+delta,s64)
 co,cg=f['co'],f['cg']
 coq=co if keep_chroma else np.where(np.abs(co)<16,co,f['coq']);cgq=cg if keep_chroma else np.where(np.abs(cg)<16,cg,f['cgq'])
 middle=yq-cgq//2;green=middle+cgq;blue=middle-coq//2;red=blue+coq
 return np.clip(np.stack([red,green,blue],-1),0,255),dict(y=y,yq=yq,co=co,cg=cg,coq=coq,cgq=cgq)
def hybrid_from(im,features,keep_chroma=False):
 c,_=colour_hybrid(features['smoothed'],keep_chroma);fill=new.ink(c,features['mag'],features['edge']);out=np.zeros_like(im);out[6:,12:]=fill.astype(np.uint8)
 return out,c
w,h,ht,vt=64,48,80,56;roi=(slice(12,-8),slice(20,-8));de=np.zeros((vt,ht),bool);de[:h,:w]=True;ov=np.zeros_like(de);control=np.full(de.size,40,np.uint8)
def display(im):
 a=np.zeros((vt,ht,3),np.uint8);a[:h,:w]=im
 return filter_rgb(a.reshape(-1,3),de.ravel(),ov.ravel(),control,h_total=ht,th_dark=32,max_correction=6).reshape(vt,ht,3)[:h,:w]
rng=np.random.default_rng(20261030)
def compare(level,block,amplitude):
 samples={key:[] for key in ['v9','frozen','hybrid50_chroma16','hybrid50_original_chroma']}
 for frame in range(8):
  ns=((h+block-1)//block,(w+block-1)//block,3);noise=rng.integers(-amplitude,amplitude+1,ns);noise=np.repeat(np.repeat(noise,block,0),block,1)[:h,:w];im=np.clip(level+noise,0,255).astype(np.uint8)
  a,_=old.render(im,1,gm.guide);z,f=new.render(im,1,gm.guide);h16,_=hybrid_from(im,f);hc,_=hybrid_from(im,f,True)
  for key,img in [('v9',a),('frozen',z),('hybrid50_chroma16',h16),('hybrid50_original_chroma',hc)]:samples[key].append(display(img)[roi].astype(float))
 stats={key:float(np.asarray(values).std(0).mean()) for key,values in samples.items()}
 return {'gray':level,'block':block,'amplitude':amplitude,**stats}
strong=[]
for block in [1,2,3,4]:
 for level in range(256):strong.append(compare(level,block,20))
 print('SHADOW50_STRONG',block,flush=True)
weak=[]
for amp in [4,8,12]:
 for block in [1,2,3,4]:
  for level in [0,8,16,32,48,56,60,63,64,65,68,96,128,192,224,253]:weak.append(compare(level,block,amp))
 print('SHADOW50_WEAK',amp,flush=True)
def summarise(cases,key):
 ratios=[c[key]/c['v9'] if c['v9'] else 0 for c in cases];extra=[c[key]-c['v9'] for c in cases];i=int(np.argmax(ratios));j=int(np.argmax(extra))
 return {'cases':len(cases),'improved_or_equal':sum(r<=1 for r in ratios),'median_ratio':float(np.median(ratios)),'worst_ratio':ratios[i],'worst_ratio_case':cases[i],'max_absolute_extra_std':extra[j],'worst_extra_case':cases[j]}
summary={}
for key in ['frozen','hybrid50_chroma16','hybrid50_original_chroma']:
 summary[key]={'strong_all':summarise(strong,key),'strong_below64':summarise([c for c in strong if c['gray']<64],key),'strong_ge64':summarise([c for c in strong if c['gray']>=64],key),'weak_all':summarise(weak,key)}
rows=[];natural=[]
for name in ['test_photo','board_real_bakery','board_like_cast','board_like_lowcontrast']:
 im=np.fromfile(R.parent/'05_stylize_on_v5/sim'/f'{name}.raw',np.uint8).reshape(720,1280,3);im=np.asarray(Image.fromarray(im).resize((384,216),Image.Resampling.BILINEAR))
 for dark in [False,True]:
  image=np.clip(im.astype(float)*(0.35 if dark else 1),0,255).astype(np.uint8);a,fa=old.render(image,1,gm.guide);z,f=new.render(image,1,gm.guide);h16,flat16=hybrid_from(image,f);hc,flatc=hybrid_from(image,f,True)
  vals={}
  for key,flat in [('v9',fa['fill']),('frozen',f['fill']),('hybrid50_chroma16',flat16),('hybrid50_original_chroma',flatc)]:
   vals[key]={'flat_horizontal':float(np.all(np.diff(flat,axis=1)==0,axis=-1).mean()),'distinct_colours':len(np.unique(flat.reshape(-1,3),axis=0))}
  natural.append({'name':name,'darkened_0p35':dark,**vals});rows.append(np.concatenate([a,z,h16,hc],1))
canvas=Image.new('RGB',(1536,216*len(rows)+36),'white');draw=ImageDraw.Draw(canvas)
for j,label in enumerate(['V9 model','V10 frozen model','SHADOW50 + chroma16','SHADOW50 + orig chroma']):draw.text((j*384+8,10),label,fill='black')
canvas.paste(Image.fromarray(np.concatenate(rows,0)),(0,36));canvas.save(V/'shadow50_hybrid_models_only.png')
assert source==sha(R/'user_source/hdl_source/isp/stylize_v5_96.v')
res={'scope':'MODEL ONLY alternatives, no production edit or RTL validation of hybrids. Same 1024+192 fixtures as quality.py, same RNG and displayfilter32/6.','production_style_sha256':source,'probe_sha256':sha(Path(__file__)),'summary':summary,'natural':natural,'strong_details':strong,'weak_details':weak,'seconds':round(time.time()-start,2)}
(V/'shadow50_hybrid_model_results.json').write_text(json.dumps(res,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2),flush=True)
