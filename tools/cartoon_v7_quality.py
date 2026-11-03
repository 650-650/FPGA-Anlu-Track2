"""Deterministic clean-line and flat-noise comparisons; synthetic, not board photos."""
from pathlib import Path
import hashlib,json,sys
import numpy as np
import model_baseline as b
import model_visual_v6 as old
import model_denoise as d
import cartoon_v7_model as new
R=Path(__file__).resolve().parents[1];V=R/'validation/cartoon_v7';V.mkdir(exist_ok=True)
b.set_size(256,128);tests={}
def evaluate(img,frames=100):
 B,Y,M=b.core(img);po=dict(b.P0);pn=dict(b.P0)
 for f in range(frames):
  qo=old.render(B,Y,M,1,po,img);qn,nm=new.render(B,Y,M,1,pn,img,True)
  if f<frames-1:po=old.update(po,B,Y,M);pn=new.update(pn,B,Y,M)
 _,fine,smooth,preserve,_=d.guide(Y,M);th=min(po['th'],72)
 om=(fine>=th)&(preserve|(smooth>=th));return qo,qn,om,nm['edge']
for level in [30,100,185]:
 img=np.full((128,256,3),level,np.uint8)
 img[20:108,60:62]=230;img[70:72,16:240]=230
 for j in range(30,100):img[j,j+100:j+102]=230
 qo,qn,oe,ne=evaluate(img)
 retained=int(np.count_nonzero(ne&oe));total=int(np.count_nonzero(oe))
 assert retained==total,(level,'clean contour loss',retained,total)
 tests[f'clean_lines_{level}']={'pass':True,'v6_contour_pixels':total,'retained_v6_contour_pixels':retained,'recall':retained/total}
for level in [30,100,185]:
 for amplitude in [25,45]:
  img=np.clip(level+np.random.default_rng(27).integers(-amplitude,amplitude+1,(128,256,3)),0,255).astype(np.uint8)
  qo,qn,oe,ne=evaluate(img)
  old_count,new_count=int(np.count_nonzero(oe)),int(np.count_nonzero(ne))
  assert new_count<=old_count,(level,amplitude,'flat-field false edge increased',old_count,new_count)
  region=(slice(14,-10),slice(30,-20))
  ob=int(np.count_nonzero(np.all(qo[region]==0,axis=-1)));nb=int(np.count_nonzero(np.all(qn[region]==0,axis=-1)))
  assert nb<=ob,(level,amplitude,'black speckles increased',ob,nb)
  tests[f'flat_noise_{level}_{amplitude}']={'pass':True,'v6_false_contour_pixels':old_count,'v7_false_contour_pixels':new_count,'v6_black_speckles':ob,'v7_black_speckles':nb}
result={'tests':tests,'source_sha256':hashlib.sha256((R/'user_source/hdl_source/isp/stylize_v5_96.v').read_bytes()).hexdigest(),'scope':'synthetic clean 2px horizontal vertical diagonal contours and independent RGB bounded noise; no real-board accuracy claim'}
(V/'quality_result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('CARTOON_V7_QUALITY_PASS',json.dumps(result),flush=True)
