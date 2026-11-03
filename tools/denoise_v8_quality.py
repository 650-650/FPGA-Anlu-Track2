"""Joint noise/tone checks, with flat-field statistics and known line truth."""
from pathlib import Path
import hashlib,json,sys
import numpy as np
from denoise_v8_model import filter_rgb
sys.stdout.reconfigure(encoding='utf-8')
R=Path(__file__).resolve().parents[1];H=R/'user_source/hdl_source';V=R/'validation/denoise_v8'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
table=np.array([int(s,2) for s in (H/'display_tone.dat').read_text().split()],dtype=np.int16).reshape(2,8,256)
w,h,ht,vt=192,128,208,136
de=np.zeros((vt,ht),bool);de[:h,:w]=True
over=np.zeros_like(de);control=np.zeros(de.size,np.uint8)
roi=np.zeros_like(de);roi[12:h-4,12:w-8]=True
def filtered(image):return filter_rgb(image.reshape(-1,3),de.ravel(),over.ravel(),control,ht).reshape(vt,ht,3)
def tone(image,legacy=False):
 a=image.astype(np.int16);y=(a[:,:,0]+2*a[:,:,1]+a[:,:,2])//4
 d=table[int(legacy),7,y]-y
 d=np.maximum(-a.min(2),np.minimum(255-a.max(2),d))
 return a+d[:,:,None]
rng=np.random.default_rng(20261029);rows=[];line_rows=[]
for block in [1,2,3,4]:
 for sigma in [4,8,16]:
  common=rng.normal(0,sigma,((h+block-1)//block,(w+block-1)//block,1))
  chroma=rng.normal(0,2,common.shape[:2]+(3,))
  noise=np.repeat(np.repeat(common+chroma,block,0),block,1)[:h,:w]
  for mean in [8,16,24,32,40,48,56,64,80,96,112,128,160,208]:
   inp=np.zeros((vt,ht,3),np.uint8);inp[:h,:w]=np.clip(mean+noise,0,255).round().astype(np.uint8)
   out=filtered(inp);old=tone(inp,True)[roi];new=tone(out)[roi]
   ratio=float(new.std()/old.std())
   assert ratio<1.0,('joint night noise worsened',block,sigma,mean,ratio)
   rows.append({'block':block,'sigma':sigma,'mean':mean,'v7_output_std':float(old.std()),
    'v8_output_std':float(new.std()),'ratio':ratio,'v7_output_mean':float(old.mean()),'v8_output_mean':float(new.mean())})
for delta in [8,12,24,64,128]:
 for orientation in ['vertical','horizontal','diag+','diag-','step']:
  image=np.full((vt,ht,3),48,np.uint8);y,x=np.indices((h,w))
  mask=(x==70) if orientation=='vertical' else (y==60) if orientation=='horizontal' else (x-y==30) if orientation=='diag+' else (x+y==170) if orientation=='diag-' else (x>=80)
  image[:h,:w][mask]=48+delta
  out=filtered(image);count=int(np.count_nonzero(out[roi]!=image[roi]));assert count==0,(delta,orientation,count)
  line_rows.append({'contrast':delta,'orientation':orientation,'changed_channel_samples':count,'pass':True})
# A chromatic boundary is not a grey-luma edge. Keep a low-difference RGB step.
image=np.zeros((vt,ht,3),np.uint8);image[:h,:w]=[28,42,64];image[:h,80:w]=[42,34,60]
out=filtered(image);assert np.array_equal(out[roi],image[roi]),'low contrast chromatic edge blended'
# A finite isolated outlier has no line continuation, so it should be reduced.
image=np.full((vt,ht,3),48,np.uint8);image[60,80]=72;out=filtered(image)
assert np.all(out[60,80]<72) and np.all(out[60,80]>=60)
# A common RGB tone delta preserves every channel difference, including skin/blue.
for rgb in [[32,40,64],[64,38,24],[112,82,62],[0,20,64],[230,210,185]]:
 a=np.array(rgb,dtype=np.uint8).reshape(1,1,3);b=tone(a)[0,0]
 assert b[0]-b[1]==int(rgb[0])-rgb[1] and b[1]-b[2]==int(rgb[1])-rgb[2]
assert table[0,7,0]==0 and table[0,7,16]<table[1,7,16] and table[0,7,20]<table[1,7,20]
assert all(table[0,7,y]>=y for y in range(24,225))
assert np.array_equal(table[0,0],table[1,0])
result={'tests':{'joint_night_noise':{'pass':True,'cases':len(rows),'worst_std_ratio':max(a['ratio'] for a in rows)},
 'known_clean_thin_lines_and_steps':{'pass':True,'cases':len(line_rows),'details':line_rows},
 'chromatic_step':{'pass':True},'finite_impulse':{'pass':True},'tone_chroma_and_grey_floor':{'pass':True}},
 'source_sha256':{p.relative_to(R).as_posix():sha(p) for p in [H/'display_denoise_v8.v',H/'display_contrast.v',H/'display_tone.dat']},
 'oracle_sha256':{p.relative_to(R).as_posix():sha(p) for p in [R/'tools/denoise_v8_model.py',Path(__file__)]},
 'metrics':rows,'scope':'Independent oracle quality fixtures. Dark level7, pedestal0, stationary shared+RGB block noise; not an image captured from the FPGA and not a guarantee for all real sensor noise or motion.'}
(V/'quality_result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('DENOISE_V8_QUALITY_PASS',len(rows),'noise cases',len(line_rows),'clean geometries; worst noise std ratio',max(a['ratio'] for a in rows))
