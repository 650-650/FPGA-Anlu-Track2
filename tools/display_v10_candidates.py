"""Known-truth candidate comparison for clear-only V10; does not edit RTL."""
from pathlib import Path
import hashlib,json,sys
import numpy as np
from display_v9_model import filter_rgb as cross
from denoise_v8_model import filter_rgb as wide
R=Path(__file__).resolve().parents[1];V=R/'validation/display_v10';V.mkdir(exist_ok=True)
W,H,HT,VT=192,128,208,160;y,x=np.indices((VT,HT));de=(y<H)&(x<W)
roi=(x>=12)&(x<W-12)&(y>=12)&(y<H-12);zero=np.zeros(de.size,np.uint8)
configs={'v8':None,'v9':(32,6),'cross36cap6':(36,6),'cross40cap6':(40,6),'cross40cap7':(40,7),'cross40cap8':(40,8),'flat_boost':'boost','box8t32cap6':'box32','box8t40cap6':'box40','gaussian4t32cap6':'gaussian32'}
def apply(name,image):
 c=image.astype(np.int16)
 if name=='v8':q=wide(image.reshape(-1,3),de.ravel(),zero.astype(bool),zero,HT)
 elif isinstance(configs[name],tuple):q=cross(image.reshape(-1,3),de.ravel(),zero.astype(bool),zero,HT,configs[name][0],16,configs[name][1])
 elif configs[name]=='boost':
  n=np.stack([np.roll(c,a,axis=ax) for ax,a in [(0,-1),(0,1),(1,-1),(1,1)]])
  distance=np.abs(n-c).max(3);lum=(c[:,:,0]+2*c[:,:,1]+c[:,:,2])//4
  threshold=np.maximum(16,32-np.maximum(lum-64,0)//8)
  accepted=distance<=threshold
  chosen=np.where(accepted[:,:,:,None],n,c)
  keep_axis=((distance[0]<=4)&(distance[1]<=4))|((distance[2]<=4)&(distance[3]<=4))
  keep_point=(np.abs(n[0]-n[1]).max(2)<=4)&(np.abs(n[2]-n[3]).max(2)<=4)
  boost=accepted.all(0)&~keep_axis&~keep_point
  old=(4*c+chosen.sum(0)+4)//8
  stronger=(chosen.sum(0)+2)//4
  target=np.where(boost[:,:,None],stronger,old)
  return c+np.clip(target-c,-6,6)
 else:
  diagonal=[np.roll(np.roll(c,a,axis=0),b,axis=1) for a,b in [(-1,-1),(-1,1),(1,-1),(1,1)]]
  cardinal=[np.roll(c,a,axis=ax) for ax,a in [(0,-1),(0,1),(1,-1),(1,1)]]
  gaussian=configs[name].startswith('gaussian');dark=32 if configs[name].endswith('32') else 40
  lum=(c[:,:,0]+2*c[:,:,1]+c[:,:,2])//4;threshold=np.maximum(16,dark-np.maximum(lum-64,0)//8)
  s=(4 if gaussian else 8)*c
  for n,weight in [(a,2 if gaussian else 1) for a in cardinal]+[(a,1) for a in diagonal]:
   accept=np.abs(n-c).max(2)<=threshold;s+=weight*np.where(accept[:,:,None],n,c)
  q=c+np.clip((s+8)//16-c,-6,6)
  return q
 return q.reshape(VT,HT,3).astype(np.int16)
noise=[];texture=[];edges=[];features=[]
for block in [1,2,4]:
 for sigma in [4,8,16]:
  for mean in [32,64,128,192]:
   for seed in range(3):
    rng=np.random.default_rng(20261031+seed)
    g=rng.normal(0,sigma,((VT+block-1)//block,(HT+block-1)//block,1));ch=rng.normal(0,2,g.shape[:2]+(3,))
    z=np.repeat(np.repeat(g+ch,block,0),block,1)[:VT,:HT]
    image=np.clip(mean+z,0,255).round().astype(np.uint8)
    row={'block':block,'sigma':sigma,'mean':mean,'seed':seed,'input_std':float(image[roi].std())}
    for name in configs:row[name]=float(apply(name,image)[roi].std()/row['input_std'])
    noise.append(row)
for period in [3,4,5,6,8,12,16]:
 for amplitude in [4,12,24]:
  for mean in [48,112,192]:
   gray=np.rint(mean+amplitude*np.sin(2*np.pi*x/period)+amplitude/4*np.sin(2*np.pi*y/7))
   image=np.repeat(gray[:,:,None],3,2).astype(np.uint8);row={'period':period,'amplitude':amplitude,'mean':mean}
   for name in configs:
    q=apply(name,image);row[name]={'retained':float(q[roi].std()/image[roi].std()),'mae':float(np.abs(q-image)[roi].mean())}
   texture.append(row)
for delta in [8,16,24,32,48,64]:
 for mean in [32,64,128,192]:
  gray=mean+delta*(x>=88)+(x+y)%3;image=np.repeat(gray[:,:,None],3,2).clip(0,255).astype(np.uint8)
  band=roi&(x>=83)&(x<=93);row={'delta':delta,'mean':mean}
  for name in configs:
   residual=apply(name,image)[...,0]-image[...,0];row[name]={'min':int(residual[band].min()),'max':int(residual[band].max()),'mae':float(np.abs(residual[band]).mean())}
  edges.append(row)
for orient in ['horizontal','vertical','diag+','diag-','diag2+','diag2-','point']:
 for delta in [8,16,24,32,48]:
  mask=(y==60) if orient=='horizontal' else (x==88) if orient=='vertical' else (x-y==28) if orient=='diag+' else (x+y==148) if orient=='diag-' else ((x-y>=28)&(x-y<=29)) if orient=='diag2+' else ((x+y>=148)&(x+y<=149)) if orient=='diag2-' else ((x==88)&(y==60))
  # A chromatic feature exercises max-RGB gating, not just neutral grey.
  image=np.empty((VT,HT,3),np.uint8);image[:]=[48,56,64];image[mask]=[48+delta,56+delta//2,64]
  row={'orientation':orient,'delta':delta}
  for name in configs:
   q=apply(name,image);row[name]=float((q[...,0][mask&roi].mean()-48)/delta)
  features.append(row)
isotropic=[]
for period in [3,4,6,8,12]:
 for amplitude in [4,8,12]:
  g=np.rint(96+amplitude*np.sin(2*np.pi*x/period)+amplitude*np.sin(2*np.pi*y/period))
  image=np.repeat(g[:,:,None],3,2).astype(np.uint8);row={'period':period,'amplitude':amplitude}
  for name in configs:row[name]=float(apply(name,image)[roi].std()/image[roi].std())
  isotropic.append(row)
result={'scope':'Known synthetic flat/noise truth, clean multi-amplitude/multi-luma textures and colored thin features. All figures precede tone. Not captured board evidence. Candidate kernel expansion may exceed near-full Slice budget.',
 'noise':noise,'texture':texture,'isotropic':isotropic,'edge':edges,'features':features,'configs':configs}
BASE=R.parent/'07_stylize_flame_fusion_v9_detail_motion_compact'
manifest=json.loads((BASE/'output/build_manifest.json').read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(BASE/'user_source/hdl_source/display_denoise_v9.v')==sha(R/'user_source/hdl_source/display_denoise_v9.v')
result['decision']='retain V9 clear-only 32/16 threshold, correction cap6, centered cross; no production RTL edits'
result['baseline_resources']=manifest['resources']
result['baseline_timing_ns']=manifest['timing_ns']
result['source_sha256']={'user_source/hdl_source/display_denoise_v9.v':sha(R/'user_source/hdl_source/display_denoise_v9.v')}
result['oracle_sha256']={p.relative_to(R).as_posix():sha(p) for p in [Path(__file__),R/'tools/display_v9_model.py',R/'tools/denoise_v8_model.py']}
result['compact_v9_baseline']={'project':BASE.as_posix(),'manifest_sha256':sha(BASE/'output/build_manifest.json'),'display_source_sha256':sha(BASE/'user_source/hdl_source/display_denoise_v9.v')}
(V/'candidates.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
lines=['# V10 clear candidate comparison','',result['scope'],'', '| Name | sigma8 mean64 IID | 2x2 | 4x4 | period8 amp12 mean112 | RGB diag16 | RGB vertical16 | edge32 mean64 min/max |', '|---|---:|---:|---:|---:|---:|---:|---:|']
for name in configs:
 n=[np.mean([a[name] for a in noise if a['block']==b and a['sigma']==8 and a['mean']==64]) for b in [1,2,4]]
 t=next(a[name]['retained'] for a in texture if a['period']==8 and a['amplitude']==12 and a['mean']==112)
 f=[next(a[name] for a in features if a['orientation']==o and a['delta']==16) for o in ['diag+','vertical']]
 e=next(a[name] for a in edges if a['delta']==32 and a['mean']==64)
 lines.append(f"|{name}|{n[0]:.4f}|{n[1]:.4f}|{n[2]:.4f}|{t:.4f}|{f[0]:.4f}|{f[1]:.4f}|{e['min']}/{e['max']}|")
lines += ['', 'Decision: retain V9 clear-only threshold32/16, cap6, centered cross, with identical production RTL.', '',
          'Threshold widening gains little noise reduction but deepens the one-pixel dark edge. Wider 3x3 kernels reduce noise at the cost of vertical-line and genuine texture contrast and additional RGB gate logic.', '',
          'The guarded flat_boost looks favorable on the common anisotropic sine fixture and single-pixel colored lines, but fails held-out two-pixel diagonals: 8-level colored diagonal contrast retained falls 0.75 to 0.50; 16-level falls 0.75 to 0.625. Equal-amplitude two-dimensional period-6, amplitude-8 sine retention falls 0.8571 to 0.7389. Rejecting this candidate avoids optimizing only the favorable fixtures.', '',
          'Verified compact V9 budget: Slice20977/21216 (239 remaining), LUT20121/21216, ERAM100/108, DSP32/40; setup/hold WNS +0.090/+0.020ns. This clear module remains byte-identical, adding zero line RAM, DSP, arithmetic or registers. Overall V10 placement/timing remain the parent build responsibility. No future capacity recovered by other agents is assumed.', '',
          'This decision does not claim V10 clear noise is lower than V9 or that V8-level correlated-block suppression has been retained. It preserves the clear-image improvement the user accepted.']
(V/'candidates.md').write_text('\n'.join(lines)+'\n',encoding='utf-8');print('\n'.join(lines))
