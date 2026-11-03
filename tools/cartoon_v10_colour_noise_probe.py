"""MODEL ONLY coloured-shadow noise validation of promotion alternatives."""
from pathlib import Path
import json,hashlib
import numpy as np
import cartoon_v9_model as old,cartoon_v10_model as new,guide_v8_model as gm
from denoise_v8_model import filter_rgb
R=Path(__file__).resolve().parents[1];V=R/'validation/cartoon_v10'
def hybrid(pixel,half=False):
 _,f=new.colour(pixel);y=f['y'];r=y%64;delta=np.where(r<16,r//2,np.where(r<48,(32-r)//2,(r-64)//2));delta=np.where(y<32,0,delta)
 q50=y-r+np.where(r<16,2*r,np.where(r<48,32,2*r-64));q50=np.where(y>=224,y,q50)
 yq=np.where(y<64,y+delta,q50 if half else f['yq'])
 coq=np.where(np.abs(f['co'])<16,f['co'],f['coq']);cgq=np.where(np.abs(f['cg'])<16,f['cg'],f['cgq'])
 t=yq-cgq//2;g=t+cgq;b=t-coq//2;r=b+coq
 return np.clip(np.stack([r,g,b],-1),0,255)
w,h,ht,vt=64,48,80,56;roi=(slice(12,-8),slice(20,-8));de=np.zeros((vt,ht),bool);de[:h,:w]=True;ov=np.zeros_like(de);ctrl=np.full(de.size,40,np.uint8)
def display(im):
 a=np.zeros((vt,ht,3),np.uint8);a[:h,:w]=im
 return filter_rgb(a.reshape(-1,3),de.ravel(),ov.ravel(),ctrl,h_total=ht,th_dark=32,max_correction=6).reshape(vt,ht,3)[:h,:w]
rng=np.random.default_rng(59);cases=[]
for name,c in [('deep_blue',[18,32,70]),('brown',[86,52,29]),('skin',[210,160,130]),('dark_red',[60,20,16]),('green',[28,74,32]),('purple',[62,28,70]),('cyan',[20,65,80]),('neutral',[80,80,80])]:
 for factor in [1,0.6,0.35]:
  center=np.floor(np.asarray(c)*factor).astype(np.int64)
  for block in [1,3,4]:
   for amp in [8,20]:
    captures={k:[] for k in ['v9','frozen','hybrid25','hybrid50']}
    for frame in range(8):
     ns=((h+block-1)//block,(w+block-1)//block,3);noise=rng.integers(-amp,amp+1,ns);noise=np.repeat(np.repeat(noise,block,0),block,1)[:h,:w];im=np.clip(center+noise,0,255).astype(np.uint8)
     a,_=old.render(im,1,gm.guide);z,f=new.render(im,1,gm.guide)
     for key,out in [('v9',a),('frozen',z)]:captures[key].append(display(out)[roi].astype(float))
     for key,half in [('hybrid25',False),('hybrid50',True)]:
      flat=hybrid(f['smoothed'],half);out=np.zeros_like(im);out[6:,12:]=new.ink(flat,f['mag'],f['edge']).astype(np.uint8);captures[key].append(display(out)[roi].astype(float))
    std={key:float(np.asarray(v).std(0).mean()) for key,v in captures.items()};means={key:np.asarray(v).mean((0,1,2)).tolist() for key,v in captures.items()}
    cases.append({'name':name,'factor':factor,'center':center.tolist(),'block':block,'amplitude':amp,**std,'mean_rgb':means})
 print('COLOUR_NOISE',name,flush=True)
summary={}
for key in ['frozen','hybrid25','hybrid50']:
 ratio=[c[key]/c['v9'] if c['v9'] else 0 for c in cases];extra=[c[key]-c['v9'] for c in cases];i=int(np.argmax(ratio));j=int(np.argmax(extra));summary[key]={'cases':len(cases),'improved_or_equal':sum(r<=1 for r in ratio),'median_ratio':float(np.median(ratio)),'worst_ratio':ratio[i],'worst_ratio_case':cases[i],'max_extra_std':extra[j],'max_extra_case':cases[j]}
res={'scope':'MODEL ONLY whole-route flat-colour noise; 8 colours*3 brightness*3 blocks*2 amplitudes*8frames. Hybrids use weak Co/Cg<16 unchanged and V9 shadow luma.','summary':summary,'details':cases,'production_sha256':hashlib.sha256((R/'user_source/hdl_source/isp/stylize_v5_96.v').read_bytes()).hexdigest()};(V/'coloured_noise_model_results.json').write_text(json.dumps(res,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2))
