"""MODEL ONLY rejected stronger shelf candidate, never compiled as production."""
from pathlib import Path
import hashlib,json
import numpy as np
from PIL import Image,ImageDraw
import cartoon_v9_model as old,cartoon_v10_model as model,guide_v8_model as gm
from denoise_v8_model import filter_rgb
R=Path(__file__).resolve().parents[1];V=R/'validation/cartoon_v10';shelf25=model.shelf
source_before=hashlib.sha256((R/'user_source/hdl_source/isp/stylize_v5_96.v').read_bytes()).hexdigest()
def shelf50(value,period):
 v=np.asarray(value,dtype=np.int64);r=v%period;base=v-r
 return base+np.where(r<period//4,2*r,np.where(r<3*period//4,period//2,2*r-period))
def render(im,strong=False):
 model.shelf=shelf50 if strong else shelf25
 try:return model.render(im,1,gm.guide)
 finally:model.shelf=shelf25
rows=[];stats=[]
for name in ['test_photo','board_real_bakery','board_like_cast','board_like_lowcontrast']:
 im=np.fromfile(R.parent/'05_stylize_on_v5/sim'/f'{name}.raw',np.uint8).reshape(720,1280,3);im=np.asarray(Image.fromarray(im).resize((480,270),Image.Resampling.BILINEAR))
 a,_=old.render(im,1,gm.guide);q,f=render(im);z,fz=render(im,True);rows.append(np.concatenate([a,q,z],1))
 stats.append({'name':name,'production25_flat_rgb':float(np.all(np.diff(f['fill'],axis=1)==0,axis=-1).mean()),'rejected50_flat_rgb':float(np.all(np.diff(fz['fill'],axis=1)==0,axis=-1).mean())})
canvas=Image.new('RGB',(1440,270*len(rows)+36),'white');draw=ImageDraw.Draw(canvas)
for j,label in enumerate(['V9 model','V10 25% shelves - production','50% shelves - rejected model only']):draw.text((480*j+8,10),label,fill='black')
canvas.paste(Image.fromarray(np.concatenate(rows,0)),(0,36));canvas.save(V/'strength_models_only.png')
w,h,ht,vt=64,48,80,56;roi=(slice(12,-8),slice(20,-8));de=np.zeros((vt,ht),bool);de[:h,:w]=True;ov=np.zeros_like(de);control=np.full(de.size,40,np.uint8);rng=np.random.default_rng(620)
def display(im):
 a=np.zeros((vt,ht,3),np.uint8);a[:h,:w]=im
 return filter_rgb(a.reshape(-1,3),de.ravel(),ov.ravel(),control,h_total=ht,th_dark=32,max_correction=6).reshape(vt,ht,3)[:h,:w]
noise=[]
for block in [1,3,4]:
 for level in range(0,256,4):
  captures={k:[] for k in ['v9','v10_25','rejected50']}
  for f in range(6):
   ns=((h+block-1)//block,(w+block-1)//block,3);n=rng.integers(-20,21,ns);n=np.repeat(np.repeat(n,block,0),block,1)[:h,:w];im=np.clip(level+n,0,255).astype(np.uint8)
   a,_=old.render(im,1,gm.guide);q,_=render(im);z,_=render(im,True)
   for key,img in [('v9',a),('v10_25',q),('rejected50',z)]:captures[key].append(display(img)[roi].astype(float))
  s={k:float(np.asarray(v).std(0).mean()) for k,v in captures.items()};noise.append({'gray':level,'block':block,**s})
 print('STRENGTH_MODEL_NOISE',block,flush=True)
res={'scope':'Production 25% vs model-only rejected50, same inputs and cartoon postfilter32/6. No actual RTL implementation or board claim for rejected50.','production_style_sha256':source_before,'natural':stats,'noise_details':noise}
for key in ['v10_25','rejected50']:
 ratio=[a[key]/a['v9'] for a in noise];i=int(np.argmax(ratio));res[key]={'median_ratio':float(np.median(ratio)),'worst_ratio':ratio[i],'worst':noise[i]}
assert hashlib.sha256((R/'user_source/hdl_source/isp/stylize_v5_96.v').read_bytes()).hexdigest()==source_before
(V/'strength_model_comparison.json').write_text(json.dumps(res,indent=2),encoding='utf-8');print({k:res[k] for k in ['v10_25','rejected50']})
