"""Native pixel label stability and double-median prototype, model only."""
from pathlib import Path
import time,json
import numpy as np
from PIL import Image,ImageDraw
import cartoon_v11_model as new,cartoon_v10_model as old,guide_v8_model as gm
R=Path(__file__).resolve().parents[1];V=R/'validation/cartoon_v11';start=time.time();rows=[]
for name in ['test_photo','board_like_cast','video1_21.10s']:
 im=np.asarray(Image.open(R/'validation/supplied_videos'/f'{name}.jpg').convert('RGB')) if name.startswith('video') else np.fromfile(R.parent/'05_stylize_on_v5/sim'/f'{name}.raw',np.uint8).reshape(720,1280,3)
 a,f1=new.render(im,1,gm.guide,stages=1);z,f2=new.render(im,1,gm.guide,stages=1,guard=True,confidence=9)
 c=Image.new('RGB',(1280,748*2),'white');d=ImageDraw.Draw(c);d.text((8,8),name+' NATIVE 1280: single median (top), strict9-confidence guarded single median (bottom)',fill='black');c.paste(Image.fromarray(a),(0,28));c.paste(Image.fromarray(z),(0,776));c.save(V/(name+'_guard9_native.png'))
 row=Image.new('RGB',(384*3,244),'white');d=ImageDraw.Draw(row)
 for j,(img,label) in enumerate([(im,'input'),(a,'one label median'),(z,'CONFIDENCE guarded median')]):row.paste(Image.fromarray(img).resize((384,216),Image.Resampling.BILINEAR),(384*j,28));d.text((384*j+8,8),name+' '+label,fill='black')
 rows.append(row)
canvas=Image.new('RGB',(1152,244*len(rows)),'white')
for j,row in enumerate(rows):canvas.paste(row,(0,244*j))
canvas.save(V/'label_guard9_native_comparison.png')
# No resampling: every synthetic sample is a hardware pixel, dimensions only
# constrain compute cost. Buffers/4pixel boundaries separately use actual RTL.
rng=np.random.default_rng(611);w,h=192,96;roi=(slice(12,-12),slice(24,-24));cases=[]
for level in [10,20,24,25,26,27,32,38,50,64,74,75,76,77,78,100,125,126,127,128,129,153,176,177,178,179,180,204,227,228,229,230,231,245]:
 for block in [1,3,4]:
  labels={k:[] for k in ['none','one','guard']};imgs={k:[] for k in ['v10','one','guard']}
  for frame in range(8):
   ns=((h+block-1)//block,(w+block-1)//block,3);noise=rng.integers(-12,13,ns);noise=np.repeat(np.repeat(noise,block,0),block,1)[:h,:w];im=np.clip(level+noise,0,255).astype(np.uint8)
   a,f0=new.render(im,1,gm.guide,label_median=False);z,f1=new.render(im,1,gm.guide,stages=1);t,f2=new.render(im,1,gm.guide,stages=1,guard=True,confidence=9);o,_=old.render(im,1,gm.guide)
   for key,f in [('none',f0),('one',f1),('guard',f2)]:labels[key].append(f['median'][roi])
   for key,img in [('v10',o),('one',z),('guard',t)]:imgs[key].append(img[18:-12,36:-24].astype(float))
  d={'gray':level,'block':block,'guard_fallback_fraction':float(f2['fallback'][roi].mean())}
  for key,value in labels.items():
   x=np.asarray(value);d[key+'_label_temporal_std']=float(x.std(0).mean());d[key+'_label_transition_fraction']=float(np.mean(x[1:]!=x[:-1]));
   # spatial two-neighbour isolated sites (four-neighbour test, each frame).
   c=x[:,1:-1,1:-1];sur=np.stack([x[:,:-2,1:-1],x[:,2:,1:-1],x[:,1:-1,:-2],x[:,1:-1,2:]],0);isolated=np.all(sur!=c,axis=0);d[key+'_isolated_fraction']=float(isolated.mean())
  for key,value in imgs.items():d[key+'_rgb_std']=float(np.asarray(value).std(0).mean())
  cases.append(d)
 print('LABEL_NOISE',level,flush=True)
res={'scope':'Native synthetic hardware-pixel fixtures192x96, 34 grey levels including every six-band cut +/-2, correlated/no independent noise ±12,8frames. Does not claim temporal flicker removal at exact class thresholds. Current planned finish is exact4clock bypass. Natural comparisons rendered1280x720 before display resize.','cases':cases,'seconds':round(time.time()-start,2)}
for key in ['one','guard']:
 res[key]={'median_isolated_ratio_vs_none':float(np.median([(d[key+'_isolated_fraction']+1e-12)/(d['none_isolated_fraction']+1e-12) for d in cases])),'mean_label_transitions':float(np.mean([d[key+'_label_transition_fraction'] for d in cases])),'mean_isolated_fraction':float(np.mean([d[key+'_isolated_fraction'] for d in cases])),'mean_rgb_std':float(np.mean([d[key+'_rgb_std'] for d in cases]))}
(V/'label_guard9_probe_results.json').write_text(json.dumps(res,indent=2),encoding='utf-8');print({k:res[k] for k in ['one','guard']},flush=True)
