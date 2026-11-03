"""MODEL ONLY continuous-join uncertainty guards over categorical labels."""
from pathlib import Path
import json,time,hashlib
import numpy as np
from PIL import Image,ImageDraw
import cartoon_v11_model as new,cartoon_v10_model as old,guide_v8_model as gm
R=Path(__file__).resolve().parents[1];V=R/'validation/cartoon_v11';start=time.time();options={'hard':None,'smooth6_4':(6,4),'smooth8_4':(8,4),'smooth6_8':(6,8)}
def variant(im,f,key):
 if options[key] is None:return new.ink(f['fill'],f['mag'],f['edge']),f['tones'],np.zeros_like(f['tones'],bool)
 dead,blend=options[key];target,fallback=new.smooth_guard_target(f['tones'],f['center_y'],f['span'],f['support'],dead=dead,blend=blend)
 fill=new.tint(f['rgb'],target,0);return new.ink(fill,f['mag'],f['edge']),target,fallback
rows=[];natural=[]
for name in ['test_photo','board_like_cast','video1_21.10s','video1_28.13s']:
 im=np.asarray(Image.open(R/'validation/supplied_videos'/f'{name}.jpg').convert('RGB')) if name.startswith('video') else np.fromfile(R.parent/'05_stylize_on_v5/sim'/f'{name}.raw',np.uint8).reshape(720,1280,3)
 out,f=new.render(im,1,gm.guide);tiles=[('input',im)];metrics={}
 for key in options:
  fill,target,fb=variant(im,f,key);q=np.zeros_like(im);q[6:,12:]=fill.astype(np.uint8);tiles.append((key,q));Image.fromarray(q).save(V/(name+'_'+key+'_native.png'))
  metrics[key]={'palette_target_fraction':float(np.mean(target==f['tones'])),'fallback_fraction':float(fb.mean()),'flat_rgb_horizontal':float(np.mean(np.all(np.diff(fill,axis=1)==0,axis=-1))),'unique_colours':len(np.unique(fill.reshape(-1,3),axis=0))}
 row=Image.new('RGB',(384*len(tiles),244),'white');d=ImageDraw.Draw(row)
 for j,(key,q) in enumerate(tiles):row.paste(Image.fromarray(q).resize((384,216),Image.Resampling.BILINEAR),(384*j,28));d.text((384*j+8,7),name+' '+key,fill='black')
 rows.append(row);natural.append({'name':name,**metrics})
canvas=Image.new('RGB',(rows[0].width,sum(r.height for r in rows)),'white')
for j,row in enumerate(rows):canvas.paste(row,(0,j*244))
canvas.save(V/'continuous_guard_native_candidates.png')
# Native pixel fixtures, no spatial downsampling; ALL256 greys detect guards
# merely moving the noise hotspot away from the original palette threshold.
w,h=128,80;rng=np.random.default_rng(651);cases=[]
for level in range(256):
 for block in [1,3,4]:
  captures={key:[] for key in ['v10']+list(options)};fallback={key:[] for key in options}
  for frame in range(8):
   ns=((h+block-1)//block,(w+block-1)//block,3);noise=rng.integers(-12,13,ns);noise=np.repeat(np.repeat(noise,block,0),block,1)[:h,:w];im=np.clip(level+noise,0,255).astype(np.uint8)
   out,f=new.render(im,1,gm.guide);o,_=old.render(im,1,gm.guide);captures['v10'].append(o[18:-12,36:-24].astype(float))
   for key in options:
    fill,target,fb=variant(im,f,key);captures[key].append(fill[12:-12,24:-24].astype(float));fallback[key].append(fb[12:-12,24:-24])
  d={'gray':level,'block':block}
  for key,values in captures.items():d[key+'_std']=float(np.asarray(values).std(0).mean())
  for key,values in fallback.items():d[key+'_fallback']=float(np.asarray(values).mean())
  cases.append(d)
 if level%32==31:print('ALL_GREYS',level,flush=True)
summary={}
for key in options:
 worst=max(cases,key=lambda a:a[key+'_std']);ratios=[c[key+'_std']/c['hard_std'] if c['hard_std'] else 0 for c in cases]
 summary[key]={'mean_std':float(np.mean([c[key+'_std'] for c in cases])),'median_ratio_to_hard':float(np.median(ratios)),'worst_std':worst[key+'_std'],'worst_case':worst,'improved_vs_hard':sum(c[key+'_std']<=c['hard_std'] for c in cases)}
res={'scope':'Native full-resolution1280x720 previews before display resize; neutral calibration4096 and exact-finish. ALL256 grey*3noise block*8frames ±12 physical hardwarepixel fixtures128x80, no resizing. No sensor/monitor model; guard smooth joins avoid binary raw-vs-palette jumps but still have amplified slopes.','natural':natural,'summary':summary,'cases':cases,'model_sha256':hashlib.sha256((R/'tools/cartoon_v11_model.py').read_bytes()).hexdigest(),'seconds':round(time.time()-start,2)}
(V/'continuous_guard_results.json').write_text(json.dumps(res,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2),flush=True)
