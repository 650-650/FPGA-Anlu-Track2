"""MODEL ONLY optional categorical impulse cleanup using shared radius2 median.

Parent owns display RTL. No production source is changed. Replacement is an
existing RGB neighbour vector, never a channel-wise invented colour average.
"""
from pathlib import Path
import time,json,hashlib
import numpy as np
from PIL import Image,ImageDraw
import cartoon_v11_model as style,model_baseline as b,guide_v8_model as gm
R=Path(__file__).resolve().parents[1];V=R/'validation/cartoon_v11';start=time.time()
def cleanup(image,return_features=False):
 a=np.asarray(image,dtype=np.int64);h,w=a.shape[:2]
 n=np.stack([a[2+dy:h-2+dy,2+dx:w-2+dx] for dy in [-2,0,2] for dx in [-2,0,2]],0)
 ys=b.gray(n);order=np.argsort(ys,axis=0,kind='stable');index=order[4];median=np.zeros_like(n[4])
 for k in range(9):median=np.where((index==k)[...,None],n[k],median)
 dist=np.max(np.abs(n-median),axis=-1);coherent=np.sum(dist<=24,axis=0)-(dist[4]<=24)
 changed=(np.abs(ys[4]-b.gray(median))>=32)&(coherent>=7)
 out=a.copy();out[2:-2,2:-2]=np.where(changed[...,None],median,n[4]);out=out.astype(np.uint8)
 if return_features:return out,dict(changed=changed,median=median,index=index,coherent=coherent,neighbours=n)
 return out
# Full native renderer before any preview downsampling, neutral color gains,
# exact categorical finish with optional shared cleanup.
rows=[];natural=[]
for name in ['test_photo','board_real_bakery','board_like_cast','video1_21.10s','video1_28.13s']:
 im=np.asarray(Image.open(R/'validation/supplied_videos'/f'{name}.jpg').convert('RGB')) if name.startswith('video') else np.fromfile(R.parent/'05_stylize_on_v5/sim'/f'{name}.raw',np.uint8).reshape(720,1280,3)
 hard,f=style.render(im,1,gm.guide);z,features=cleanup(hard,True);Image.fromarray(z).save(V/(name+'_despeckle_model_native.png'))
 n=features['neighbours'];c=features['changed'];new_pixels=z[2:-2,2:-2][c];assert np.all(np.any(np.all(n[:,c,:]==new_pixels,axis=-1),axis=0))
 # Local 4-neighbour RGB/category impulse indicator is diagnostic, not a
 # photographic perceptual score or a claim to preserve real isolated points.
 natural.append({'name':name,'pixels':1280*720,'changed':int(c.sum()),'changed_fraction':float(c.mean())})
 row=Image.new('RGB',(384*3,244),'white');d=ImageDraw.Draw(row)
 for j,(q,label) in enumerate([(im,'input'),(hard,'hard6 labelmedian'),(z,'+ categorical impulse cleanup')]):row.paste(Image.fromarray(q).resize((384,216),Image.Resampling.BILINEAR),(384*j,28));d.text((384*j+8,8),name+' '+label,fill='black')
 rows.append(row)
 if name in ['test_photo','video1_21.10s']:
  crop=(300,180,940,500);cimg=Image.new('RGB',(1280,348),'white');d=ImageDraw.Draw(cimg)
  for j,(q,label) in enumerate([(hard,'hard6 native100%'),(z,'cleanup native100%')]):cimg.paste(Image.fromarray(q).crop(crop),(640*j,28));d.text((640*j+8,7),label,fill='black')
  cimg.save(V/(name+'_cleanup100pct.png'))
canvas=Image.new('RGB',(1152,244*len(rows)),'white')
for j,row in enumerate(rows):canvas.paste(row,(0,j*244))
canvas.save(V/'categorical_cleanup_native_comparison.png')
# Real points/lines: explicitly retain false legitimate-point removals.
synthetic=[]
for name,bg,fg in [('gray_dark',0,255),('gray_bright',255,0),('blue_on_gray',[60,60,60],[10,30,180]),('skin_on_gray',[70,70,70],[220,160,120])]:
 for kind in ['point','square2','square3','square5','line1','line2','diag1','edge']:
  im=np.empty((96,160,3),np.uint8);im[:]=bg
  if kind=='point':im[48,80]=fg
  elif kind.startswith('square'):
   k=int(kind[-1]);im[48:48+k,80:80+k]=fg
  elif kind.startswith('line'):im[:,80:80+int(kind[-1])]=fg
  elif kind=='diag1':
   for y in range(96):im[y,32+y]=fg
  else:im[:,80:]=fg
  direct=cleanup(im);out,_=style.render(im,1,gm.guide);after=cleanup(out)
  synthetic.append({'colour':name,'kind':kind,'direct_vector_filter_changed':int(np.any(direct!=im,axis=-1).sum()),'whole_style_chain_changed':int(np.any(after!=out,axis=-1).sum())})
# Same physical-pixel threshold/noise fixtures as prior guard study, now the
# all-grey sweep tests true whole production-style route plus optional DPC.
w,h=96,72;rng=np.random.default_rng(661);cases=[]
for level in range(256):
 for block in [1,3,4]:
  frames0=[];frames1=[];changes=[]
  for frame in range(8):
   ns=((h+block-1)//block,(w+block-1)//block,3);noise=rng.integers(-12,13,ns);noise=np.repeat(np.repeat(noise,block,0),block,1)[:h,:w];im=np.clip(level+noise,0,255).astype(np.uint8)
   out,_=style.render(im,1,gm.guide);z,ff=cleanup(out,True);frames0.append(out[18:-12,36:-24].astype(float));frames1.append(z[18:-12,36:-24].astype(float));changes.append(ff['changed'][16:-10,34:-22])
  a,z=[float(np.asarray(v).std(0).mean()) for v in [frames0,frames1]];cases.append({'gray':level,'block':block,'hard_std':a,'cleaned_std':z,'changed_fraction':float(np.asarray(changes).mean()),'extra_std':z-a})
 if level%32==31:print('CLEANUP_ALL_GREYS',level,flush=True)
summary={'cases':len(cases),'improved_or_equal':sum(c['cleaned_std']<=c['hard_std'] for c in cases),'mean_hard_std':float(np.mean([c['hard_std'] for c in cases])),'mean_cleaned_std':float(np.mean([c['cleaned_std'] for c in cases])),'worst_extra':max(cases,key=lambda c:c['extra_std']),'worst_hard':max(cases,key=lambda c:c['hard_std']),'worst_cleaned':max(cases,key=lambda c:c['cleaned_std'])}
res={'scope':'MODEL ONLY optional radius2 actual-vector median replacement: |Ycenter-Ymedian|>=32 and >=7/8 outer RGB neighbours within24. No temporal state or production display edit. Tiny real isolated objects may be removed; direct and style-chain detail costs included. Native1280x720 samples before preview resize, neutral color gains4096/4096. All256gray*3blocks*8frames noise±12 physicalpixel fixtures96x72 no resizing.','natural':natural,'synthetic_details':synthetic,'summary':summary,'noise_details':cases,'style_source_sha256':hashlib.sha256((R/'user_source/hdl_source/isp/stylize_v5_96.v').read_bytes()).hexdigest(),'model_sha256':hashlib.sha256((R/'tools/cartoon_v11_model.py').read_bytes()).hexdigest(),'probe_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'seconds':round(time.time()-start,2)}
(V/'categorical_cleanup_probe_results.json').write_text(json.dumps(res,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2),flush=True);print('DETAILS',synthetic,flush=True)
