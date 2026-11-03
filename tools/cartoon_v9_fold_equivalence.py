"""Compact production vs its actual before-fold snapshot, using real RTL.

Unlike the inherited candidate artifact, both source paths in this report are
actual compact files: production8abf and validation/style_before_fold1b27.
"""
from pathlib import Path
import hashlib,json,re,subprocess,time
import numpy as np
from PIL import Image
R=Path(__file__).resolve().parents[1];V=R/'validation/cartoon_v9/fold_equivalence';V.mkdir(exist_ok=True)
S=R/'user_source/hdl_source/isp/stylize_v5_96.v';OLD=R/'validation/cartoon_v9/style_before_fold_v9.v';G=R/'user_source/hdl_source/isp/style_guide_v8.v'
T=R/'validation/cartoon_v9/fold_candidate/fold_candidate_tb.v';IV=Path(r'D:\anlu\iverilog\bin\iverilog.exe')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(S)=='8abf903b9e62fc18618da80fbdace6179e692d06d786dd9852a985e952f723fe'
assert sha(OLD)=='1b2741d42dd9bf41180f9e81d769a076b8af63b540b68602f36adc0dc156dbc7'
snapshot=OLD.read_text(encoding='utf-8')
for name in sorted(re.findall(r'(?m)^module\s+(\w+)',snapshot),key=len,reverse=True):snapshot=re.sub(r'\b'+name+r'\b',name+'_current_ref',snapshot)
(V/'snapshot_reference.v').write_text(snapshot,encoding='utf-8');(V/'fold_tb.v').write_text(T.read_text(encoding='utf-8'),encoding='utf-8')
sources={p.relative_to(R).as_posix():sha(p) for p in [S,OLD,G]}
oracles={p.relative_to(R).as_posix():sha(p) for p in [Path(__file__),T]}
photo=np.fromfile(R.parent/'05_stylize_on_v5/sim/test_photo.raw',np.uint8).reshape(720,1280,3)
rng=np.random.default_rng(20261030);tests={};start=time.time()
def run(label,args):
 p=subprocess.run(list(map(str,args)),cwd=V,capture_output=True,text=True,timeout=600);log=p.stdout+p.stderr
 (V/(label+'.log')).write_text(log,encoding='utf-8');assert p.returncode==0,(label,p.returncode,log[-1600:]);return log
for label,w,h,F in [('all_modes',160,90,8),('full_width',1280,48,4)]:
 im=np.asarray(Image.fromarray(photo).resize((w,h),Image.Resampling.BILINEAR))
 with (V/'frames.hex').open('w') as fd:
  for f in range(F):
   a=np.clip(im.astype(float)*(0.35 if f%2 else 1),0,255).astype(int)
   if f%4==1:
    a[:,w//4:w//2]=[18,32,70];a[:,w//2:3*w//4]=[86,52,29]
    a=np.clip(a+rng.integers(-20,21,a.shape),0,255)
   for beat in a.astype(np.uint8).reshape(-1,12):fd.write(beat.tobytes().hex()+'\n')
 run(label+'_compile',[IV,'-g2012','-s','fold_candidate_tb','-P',f'fold_candidate_tb.W={w}','-P',f'fold_candidate_tb.H={h}','-P',f'fold_candidate_tb.F={F}','-o',V/'test.vvp',V/'fold_tb.v',S,V/'snapshot_reference.v',G])
 log=run(label,[IV.with_name('vvp.exe'),V/'test.vvp']);assert 'CARTOON_V9_FOLD_EQ_PASS' in log
 tests[label]={'pass':True,'width':w,'height':h,'frames':F,'pixels':w*h*F,'each_mode_pixels':w*h*F//4,'log':log.strip()};print(log.strip(),flush=True)
assert sources=={p:sha(R/p) for p in sources};assert oracles=={p:sha(R/p) for p in oracles}
result={'tests':tests,'source_sha256':sources,'oracle_sha256':oracles,'seconds':round(time.time()-start,2),'register_bits_before':864,'register_bits_current':360,'register_bits_saved':504,'scope':'Real compact production8abf versus actual compact snapshot before_fold1b27. Same guide, all modes and1280 width, 16clk, frame-mode latch, random gaps. This proof does not use the stale inherited fold_candidate source binding. No TD or board claim.'}
(V/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('CARTOON_V9_COMPACT_FOLD_EQ_PASS',sha(S),flush=True)
