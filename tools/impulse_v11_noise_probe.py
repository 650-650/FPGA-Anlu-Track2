"""High-contrast impulse decision rates on independently noisy display taps."""
from pathlib import Path
import hashlib,json
import numpy as np
from impulse_v11_model import repair
R=Path(__file__).resolve().parents[1];V=R/'validation/impulse_v11';V.mkdir(exist_ok=True)
w,h,ht,vt=128,96,160,128;y,x=np.indices((vt,ht));de=(x<w)&(y<h)
zero=np.zeros(de.size,np.uint8);sites=de&(x>=8)&(x<w-8)&(y>=8)&(y<h-8)&(x%8==0)&(y%8==0)
relative=dict(policy='both',coherence=16,min_distance=64,min_peak=160,min_colour=48,
              min_colour_y=64,min_white_y=160,min_white_delta=64)
profiles={'strict224_coh8':dict(policy='both'),
          'strict224_coh16':dict(policy='both',coherence=16),
          'relative160_coh16':relative}
rng=np.random.default_rng(20261102);rows=[]
for mean in [64,128,192]:
 for sigma in [2,4,8,16]:
  sums={p:dict(hot_events=0,background_events=0,sites=0,background_samples=0) for p in profiles}
  for seed in range(10):
   image=np.clip(mean+rng.normal(0,sigma,(*de.shape,1))+rng.normal(0,1,(*de.shape,3)),0,255).round().astype(np.uint8)
   image[sites]=[255,255,0]
   for name,params in profiles.items():
    q,e,_=repair(image.reshape(-1,3),de.ravel(),zero.astype(bool),zero,ht,**params);e=e.reshape(de.shape)
    sums[name]['hot_events']+=int((e&sites).sum());sums[name]['sites']+=int(sites.sum())
    sums[name]['background_events']+=int((e&de&~sites).sum());sums[name]['background_samples']+=int((de&~sites).sum())
  for name,a in sums.items():rows.append(dict(mean=mean,sigma=sigma,profile=name,**a,hot_repair_rate=a['hot_events']/a['sites']))
# Profiled filmed-like point is only a numeric robustness fixture. It is not an
# estimate of the original FPGA RGB, which filming can blur/expose/compress.
im=np.empty((*de.shape,3),np.uint8);im[:]=[80,80,100];single=(x==64)&(y==48);im[single]=[166,179,172]
filmed=[]
for name,params in profiles.items():
 q,e,_=repair(im.reshape(-1,3),de.ravel(),zero.astype(bool),zero,ht,**params)
 filmed.append(dict(profile=name,events=int(e.sum())))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
result={'scope':'Display-input synthetic taps, not an inference from photographed RGB. Actual ROI gating would further restrict event locations.',
 'profiles':profiles,'results':rows,'filmed_like_numeric_singleton':filmed,
 'oracle_sha256':{p.relative_to(R).as_posix():sha(p) for p in [Path(__file__),R/'tools/impulse_v11_model.py',R/'tools/display_v9_model.py']}}
(V/'noise_probe.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
for a in rows:
 if a['mean']==64:print(a['sigma'],a['profile'],round(a['hot_repair_rate'],4),a['background_events'])
print('numeric single point',filmed)
