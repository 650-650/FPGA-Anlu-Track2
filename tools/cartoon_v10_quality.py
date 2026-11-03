"""V9/V10 whole-production cartoon comparisons, including display postfilter.

No all-noise-improved assertion: all 256 grey levels, correlated and IID noise,
weak-transition cases and the worst increase are deliberately retained.
"""
from pathlib import Path
import hashlib,json,time
import numpy as np
from PIL import Image,ImageDraw
import model_baseline as b,guide_v8_model as gm
import cartoon_v9_model as old,cartoon_v10_model as new
from denoise_v8_model import filter_rgb
R=Path(__file__).resolve().parents[1];V=R/'validation/cartoon_v10';V.mkdir(exist_ok=True);H=R/'user_source/hdl_source';start=time.time()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
source={p.relative_to(R).as_posix():sha(p) for p in [H/'isp/stylize_v5_96.v',H/'isp/style_guide_v8.v',H/'display_cartoon_finish_v9.v']}
oracles={p.relative_to(R).as_posix():sha(p) for p in [R/'tools/cartoon_v10_model.py',R/'tools/cartoon_v9_model.py',R/'tools/guide_v8_model.py',R/'tools/denoise_v8_model.py',R/'tools/model_baseline.py',R/'tools/model_denoise.py',Path(__file__)]}
rng=np.random.default_rng(20261030);w,h,ht,vt=64,48,80,56;roi=(slice(12,-8),slice(20,-8));de=np.zeros((vt,ht),bool);de[:h,:w]=True;ov=np.zeros_like(de);control=np.full(de.size,40,np.uint8)
def display(im):
 a=np.zeros((vt,ht,3),np.uint8);a[:h,:w]=im
 return filter_rgb(a.reshape(-1,3),de.ravel(),ov.ravel(),control,h_total=ht,th_dark=32,max_correction=6).reshape(vt,ht,3)[:h,:w]
def compare(level,block,amplitude,frames=8):
 captures=[[],[]]
 for f in range(frames):
  ns=((h+block-1)//block,(w+block-1)//block,3);noise=rng.integers(-amplitude,amplitude+1,ns);noise=np.repeat(np.repeat(noise,block,0),block,1)[:h,:w]
  image=np.clip(level+noise,0,255).astype(np.uint8)
  for j,model in enumerate([old,new]):
   out,_=model.render(image,1,gm.guide);captures[j].append(display(out)[roi].astype(float))
 a,z=[float(np.asarray(c).std(0).mean()) for c in captures]
 return {'gray':level,'block':block,'amplitude':amplitude,'frames':frames,'v9_std':a,'v10_std':z,'ratio':z/a if a else None,'absolute_std_increase':z-a}
noise=[]
for block in [1,2,3,4]:
 for level in range(256):noise.append(compare(level,block,20))
 print('V10_GREY_NOISE_DONE',block,flush=True)
weak=[]
for amplitude in [4,8,12]:
 for block in [1,2,3,4]:
  for level in [0,8,16,32,48,56,60,63,64,65,68,96,128,192,224,253]:weak.append(compare(level,block,amplitude))
 print('V10_WEAK_NOISE_DONE',amplitude,flush=True)
def summary(cases):
 ratios=[a['ratio'] for a in cases if a['ratio'] is not None]
 return {'cases':len(cases),'improved_or_equal':sum(a['v10_std']<=a['v9_std'] for a in cases),'median_ratio':float(np.median(ratios)),'worst_ratio':max(cases,key=lambda a:a['ratio'] or 0),'worst_absolute_increase':max(cases,key=lambda a:a['absolute_std_increase']),'details':cases}
# True flat shelf intervals, anchored black/white and weak chroma.
ys=np.arange(256,dtype=np.int64);neutral=np.repeat(ys[:,None],3,-1);q,f=new.colour(neutral)
assert np.all(np.diff(q[:,0])>=0) and np.array_equal(q[0],[0,0,0]) and np.array_equal(q[-1],[255,255,255])
assert np.array_equal(q[:,0],q[:,1]) and np.array_equal(q[:,1],q[:,2])
assert np.all(q[88:105,0]==96) and np.all(q[152:169,0]==160)
assert np.array_equal(q[:16],neutral[:16]) and np.array_equal(q[224:],neutral[224:])
tests={'neutral_shelf_and_endpoints':{'pass':True,'points':256,'shelf_samples':[88,104,152,168]}}
colours=[]
for name,c in [('deep_blue',[18,32,70]),('brown',[86,52,29]),('skin',[210,160,130]),('dark_red',[60,20,16]),('green',[28,74,32]),('purple',[62,28,70]),('cyan',[20,65,80])]:
 for factor in [1,0.6,0.35,0.15]:
  p=np.floor(np.array(c)*factor).astype(np.int64);qq,_=new.colour(p)
  assert np.ptp(p)==0 or np.ptp(qq)>0,(name,factor,p,qq)
  colours.append({'name':name,'factor':factor,'input':p.tolist(),'output':qq.tolist()})
tests['named_dark_colours_retained']={'pass':True,'cases':len(colours),'details':colours}
# Exhaustive palette-model invariants on all 16.7M RGB triples. Report weak
# RGB-channel rank crossings rather than claiming exact hue preservation.
ex={'pixels':0,'coloured_to_neutral':0,'neutral_to_colour':0,'co_sign_flips':0,'cg_sign_flips':0,'max_abs_rgb_delta':0,'channel_order_flips':0,'largest_original_channel_gap_flipped':0}
g,bl=np.mgrid[0:256,0:256]
for red in range(256):
 p=np.stack([np.full_like(g,red),g,bl],-1);qq,f=new.colour(p);ex['pixels']+=65536
 ex['coloured_to_neutral']+=int(np.count_nonzero((np.ptp(p,axis=-1)>0)&(np.ptp(qq,axis=-1)==0)))
 ex['neutral_to_colour']+=int(np.count_nonzero((np.ptp(p,axis=-1)==0)&(np.ptp(qq,axis=-1)>0)))
 ex['co_sign_flips']+=int(np.count_nonzero(f['co']*f['coq']<0));ex['cg_sign_flips']+=int(np.count_nonzero(f['cg']*f['cgq']<0));ex['max_abs_rgb_delta']=max(ex['max_abs_rgb_delta'],int(np.max(np.abs(qq-p))))
 for a,z in [(0,1),(0,2),(1,2)]:
  gap=p[...,a]-p[...,z];flip=gap*(qq[...,a]-qq[...,z])<0;ex['channel_order_flips']+=int(np.count_nonzero(flip))
  if np.any(flip):ex['largest_original_channel_gap_flipped']=max(ex['largest_original_channel_gap_flipped'],int(np.max(np.abs(gap[flip]))))
assert all(ex[k]==0 for k in ['coloured_to_neutral','neutral_to_colour','co_sign_flips','cg_sign_flips'])
tests['exhaustive_palette_invariants']={'pass':True,**ex,'scope':'Python fixed-point palette model, not 16.7M actual RTL transactions; actual RTL oracle checked separately.'}
# Natural-image images are software demonstrations, not board photographs.
rows=[];natural=[];W,HH=480,270
for name in ['test_photo','board_real_bakery','board_like_cast','board_like_lowcontrast']:
 original=np.fromfile(R.parent/'05_stylize_on_v5/sim'/f'{name}.raw',np.uint8).reshape(720,1280,3);original=np.asarray(Image.fromarray(original).resize((W,HH),Image.Resampling.BILINEAR))
 for dark in [False,True]:
  im=np.clip(original.astype(float)*(0.35 if dark else 1),0,255).astype(np.uint8);aa,fa=old.render(im,1,gm.guide);zz,fz=new.render(im,1,gm.guide)
  a,z=fa['fill'],fz['fill'];ma=float(np.all(np.diff(a,axis=1)==0,axis=-1).mean());mz=float(np.all(np.diff(z,axis=1)==0,axis=-1).mean())
  natural.append({'name':name,'darkened_0p35':dark,'v9_flat_rgb_horizontal':ma,'v10_flat_rgb_horizontal':mz,'v9_distinct_colours':len(np.unique(a.reshape(-1,3),axis=0)),'v10_distinct_colours':len(np.unique(z.reshape(-1,3),axis=0))})
  rows.append(np.concatenate([im,aa,zz],1))
canvas=Image.new('RGB',(W*3,HH*len(rows)+36),'white');draw=ImageDraw.Draw(canvas)
for j,label in enumerate(['INPUT - software sample','V9 - model','V10 - model']):draw.text((j*W+8,10),label,fill='black')
canvas.paste(Image.fromarray(np.concatenate(rows,0)),(0,36));canvas.save(V/'model_comparison.png')
normal=[a for a in natural if not a['darkened_0p35']];dark=[a for a in natural if a['darkened_0p35']]
def regions_improved(cases):return all(a['v10_flat_rgb_horizontal']>a['v9_flat_rgb_horizontal'] and a['v10_distinct_colours']<a['v9_distinct_colours'] for a in cases)
tests['normal_light_colour_regions_improve']={'pass':regions_improved(normal),'details':normal,'scope':'Before display filter; normal-light palette is intended to form stronger colour regions. Not proof of board aesthetics.'}
diagnostics={'all8_improved':regions_improved(natural),'all8_comparison':natural,'dark4_comparison':dark,'scope_change':'The former all8 natural-region-improvement hypothesis failed and is retained in quality_all8_hypothesis.json. Production deliberately restores V9 shadow luminance to suppress dark transition noise; dark fixtures remain diagnostics, not a blanket improvement assertion. No fixture or value was removed or a numerical acceptance tolerance invented.'}

# Counterexamples are diagnostics, never discarded to create an all-pass story.
assert source=={p:sha(R/p) for p in source},'Production source changed while measuring'
assert oracles=={p:sha(R/p) for p in oracles},'Oracle changed while measuring'
result={'tests':tests,'diagnostics':diagnostics,'noise_strong':summary(noise),'noise_weak':summary(weak),'source_sha256':source,'oracle_sha256':oracles,'seconds':round(time.time()-start,2),'scope':'V9 vs V10 actual-style mathematical models plus unchanged cartoon display filter threshold32/cap6. No sensor/DDR/monitor modelling. More pronounced flat regions involve explicit transition-noise costs.'}
(V/'quality_result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('V10_QUALITY_DONE',result['seconds'],'strong',summary(noise)['median_ratio'],'weak',summary(weak)['median_ratio'],flush=True)
