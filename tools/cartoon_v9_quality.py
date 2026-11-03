"""Whole-grey-range, colour-detail and moving-boundary quality experiments.

The V8 baseline includes its real causal STRIDE4 display filter. Both proposed
V9 cartoon-only display-filter parameter sets are compared without pretending
that a pre-DDR style comparison proves an entire HDMI improvement.
"""
from pathlib import Path
import hashlib,json,sys,time
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import model_baseline as b,guide_v8_model as gm
import cartoon_v8_model as old,cartoon_v9_model as new
from denoise_v8_model import filter_rgb
R=Path(__file__).resolve().parents[1];V=R/'validation/cartoon_v9';V.mkdir(exist_ok=True)
H=R/'user_source/hdl_source';start=time.time()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
source={p.relative_to(R).as_posix():sha(p) for p in [H/'isp/stylize_v5_96.v',H/'isp/style_guide_v8.v',H/'display_denoise_v8.v']}
oracles={p.relative_to(R).as_posix():sha(p) for p in [R/'tools/cartoon_v9_model.py',R/'tools/cartoon_v8_model.py',R/'tools/guide_v8_model.py',R/'tools/denoise_v8_model.py',Path(__file__)]}
tests={};metrics=[];comparisons={};rng=np.random.default_rng(20261030)
w,h,ht,vt=64,48,80,56
de=np.zeros((vt,ht),bool);de[:h,:w]=True;ov=np.zeros_like(de);control=np.full(de.size,40,np.uint8)
def display(im,threshold=40,cap=12):
 a=np.zeros((vt,ht,3),np.uint8);a[:h,:w]=im
 return filter_rgb(a.reshape(-1,3),de.ravel(),ov.ravel(),control,h_total=ht,th_dark=threshold,max_correction=cap).reshape(vt,ht,3)[:h,:w]
roi=(slice(12,-8),slice(20,-8))
for block in [1,2,3,4]:
 for level in range(256):
  captures={k:[] for k in ['v8_complete','v9_pre_display','v9_40_12','v9_32_6']}
  for frame in range(8):
   ns=((h+block-1)//block,(w+block-1)//block,3)
   noise=rng.integers(-20,21,ns);noise=np.repeat(np.repeat(noise,block,0),block,1)[:h,:w]
   image=np.clip(level+noise,0,255).astype(np.uint8)
   before,_=old.render(image,1,gm.guide);after,f=new.render(image,1,gm.guide)
   # Common delta cannot change either RGB channel difference before ink.
   assert np.array_equal(f['fill'][...,0]-f['fill'][...,1],f['smoothed'][...,0]-f['smoothed'][...,1])
   assert np.array_equal(f['fill'][...,1]-f['fill'][...,2],f['smoothed'][...,1]-f['smoothed'][...,2])
   for k,a in [('v8_complete',display(before)),('v9_pre_display',after),('v9_40_12',display(after)),('v9_32_6',display(after,32,6))]:captures[k].append(a[roi].astype(float))
  std={k:float(np.asarray(a).std(0).mean()) for k,a in captures.items()}
  metrics.append({'block':block,'gray':level,**{k+'_std':a for k,a in std.items()},**{k+'_ratio':std[k]/std['v8_complete'] for k in std if k!='v8_complete'}})
 print('GRAY_SWEEP',block,'cases',len(metrics),flush=True)
for key in ['v9_pre_display','v9_40_12','v9_32_6']:
 worst=max(metrics,key=lambda a:a[key+'_ratio'])
 target=tests if key=='v9_32_6' else comparisons
 target[key+'_noise']={'pass':all(a[key+'_ratio']<=1.0 for a in metrics),'cases':len(metrics),'worst':worst,'median_std_ratio':float(np.median([a[key+'_ratio'] for a in metrics]))}
# Weak-noise transition cases are deliberately retained even when their small
# denominator makes the STD ratio look large. No universal denoising claim.
weak=[]
for amplitude in [4,8,12]:
 for block in [1,2,3,4]:
  for level in [0,8,16,32,48,56,60,63,64,65,68,96,128,192,224,253]:
   a=[];z=[]
   for frame in range(8):
    ns=((h+block-1)//block,(w+block-1)//block,3);noise=rng.integers(-amplitude,amplitude+1,ns)
    noise=np.repeat(np.repeat(noise,block,0),block,1)[:h,:w];image=np.clip(level+noise,0,255).astype(np.uint8)
    before,_=old.render(image,1,gm.guide);after,_=new.render(image,1,gm.guide)
    a.append(display(before)[roi].astype(float));z.append(display(after,32,6)[roi].astype(float))
   aa=float(np.asarray(a).std(0).mean());zz=float(np.asarray(z).std(0).mean())
   weak.append({'amplitude':amplitude,'block':block,'gray':level,'v8_std':aa,'v9_std':zz,'ratio':zz/aa if aa else 0,'absolute_std_increase':zz-aa})
comparisons['weak_noise_transition']={'scope':'Diagnostic, not an all-noise-lower pass claim. Accepted cost of stronger painterly tone plateaus. Statistics in RGB code values; small V8 denominator can enlarge ratios.','cases':len(weak),'worst_ratio':max(weak,key=lambda a:a['ratio']),'worst_absolute_increase':max(weak,key=lambda a:a['absolute_std_increase']),'details':weak}
worst_weak=max(weak,key=lambda a:a['absolute_std_increase'])
tests['weak_noise_absolute_extra_std']={'pass':worst_weak['absolute_std_increase']<=0.2,'accepted_upper_bound_rgb_codes':0.2,'cases':len(weak),'worst':worst_weak,'scope':'An explicit small absolute tradeoff bound, not an assertion that every noise STD decreases.'}
# Deterministic local neighbourhoods: tolerance-based line protection and
# strong chromatic boundaries, including colours with the same luma.
local=[];direction_pairs=[(1,7,3,5),(3,5,1,7),(0,8,2,6),(2,6,0,8)]
for center,bg in [([40,80,40],[60,60,60]),([20,32,90],[43,43,43]),([100,72,44],[72,72,72])]:
 for direction,(a,z,c,d) in enumerate(direction_pairs):
  ns=np.tile(np.array(bg),(9,1,1,1));ns[4,0,0]=center;ns[a,0,0]=np.array(center)+1;ns[z,0,0]=np.array(center)-1
  flat,f=new.colour_fill(ns)
  assert f['line'][0,0] and np.array_equal(flat[0,0],center)
  local.append({'center':center,'background':bg,'direction':direction,'pass':True})
tests['tolerant_chromatic_line_protection']={'pass':True,'cases':len(local),'details':local}
# Bounded outlines cannot turn a positive channel into zero and their maximum
# per-channel removal is floor(c/4)+floor(c/8), with no Y96 discontinuity.
fill=np.repeat(np.arange(1,256)[:,None,None],3,-1)
for mag in [23,24,31,32,47,48,95,96,128,255]:
 q=new.ink(fill,np.full(fill.shape[:2],mag),np.ones(fill.shape[:2],bool))
 assert np.all(q>0) and np.all(fill-q<=fill//4+fill//8)
tests['bounded_ink']={'pass':True,'positive_rgb_codes':255,'guide_magnitudes':10}
# Actual moving scenes, not just calls to isolated colour functions.
motion=[]
for orient in ['vertical','horizontal','diag+','diag-']:
 for width in [1,2,3]:
  for frame in range(8):
   yy,xx=np.mgrid[:96,:160];axis=xx-50-frame if orient=='vertical' else yy-35-frame if orient=='horizontal' else xx-yy-20-frame if orient=='diag+' else xx+yy-100-frame
   mask=(axis>=0)&(axis<width);image=np.full((96,160,3),60,np.uint8);image[mask]=[40,80,40]
   q,f=new.render(image,1,gm.guide);valid=q[6:,12:].astype(int);flat=f['fill']
   assert np.all(valid>0),'moving colour line created black'
   assert np.all(flat-valid<=flat//4+flat//8)
  motion.append({'orientation':orient,'width':width,'frames':8,'pass':True})
tests['moving_colour_lines']={'pass':True,'cases':len(motion),'details':motion}
# A shallow ramp should form longer low-gradient patches than unmodified B2.
image=np.repeat(np.tile(np.arange(256,dtype=np.uint8),(96,2))[...,None],3,-1)
q,f=new.render(image,1,gm.guide);a=np.diff(f['source'][10,12:-12,0]);z=np.diff(f['fill'][10,12:-12,0])
tests['painterly_tone_ramp']={'pass':int((z==0).sum())>int((a==0).sum()),'v8_zero_slope_samples':int((a==0).sum()),'v9_zero_slope_samples':int((z==0).sum())}
assert tests['painterly_tone_ramp']['pass']
rows=[];W,HH=384,216
for name in ['test_photo','board_real_bakery','board_like_cast','board_like_lowcontrast']:
 img=np.fromfile(R.parent/'05_stylize_on_v5/sim'/f'{name}.raw',np.uint8).reshape(720,1280,3);img=np.asarray(Image.fromarray(img).resize((W,HH),Image.Resampling.BILINEAR))
 for dark in [False,True]:
  im=np.clip(img.astype(float)*(0.35 if dark else 1),0,255).astype(np.uint8);a,_=old.render(im,1,gm.guide);z,_=new.render(im,1,gm.guide)
  rows.append([(name+('_dark' if dark else ''),im),('V8 style before display',a),('V9 style before display',z)])
font=ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc',14);canvas=Image.new('RGB',(W*3,len(rows)*(HH+24)),(20,25,30));draw=ImageDraw.Draw(canvas)
for yy,row in enumerate(rows):
 for xx,(label,im) in enumerate(row):draw.text((xx*W+2,yy*(HH+24)+2),label,font=font,fill='white');canvas.paste(Image.fromarray(im),(xx*W,yy*(HH+24)+24))
canvas.save(V/'natural_preview.png')
assert source=={p:sha(R/p) for p in source},'source changed during quality run'
assert oracles=={p:sha(R/p) for p in oracles},'oracle changed during quality run'
result={'tests':tests,'comparisons':comparisons,'source_sha256':source,'oracle_sha256':oracles,'metrics':metrics,'seconds':round(time.time()-start,2),'selected_cartoon_display_parameters':{'stride':4,'th_dark':32,'th_bright':16,'max_correction':6},'limitations':['The V9 cartoon renderer without its selected post-filter regresses flat-wall noise; its bypass experiment is retained in comparisons.','Weak +/-4..12 RGB-code noise near tone transitions can have a small positive absolute STD increase; see full weak-noise diagnostics.','Model figures are pre-display-tone fixtures, not board-captured images or a universal real-sensor denoising guarantee.'],'scope':'Synthetic colour/8-frame IID and 2x2/3x3/4x4 block fixtures, all 256 greys at +/-20. V8 complete includes original STRIDE4 40/16 cap12; V9 selected cartoon-only STRIDE4 uses32/16 cap6. No display tone, source calibration, sensor/DDR or physical HDMI measurement.'}
(V/'quality_result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('CARTOON_V9_QUALITY_RESULT',json.dumps({k:v for k,v in tests.items() if k.endswith('_noise')}),flush=True)
