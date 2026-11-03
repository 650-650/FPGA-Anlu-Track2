"""Selected V11 style + actual final display: fine-line/point tradeoffs."""
from pathlib import Path
import json,hashlib
import numpy as np
import cartoon_v11_model as style,guide_v8_model as gm
from display_v11_model import filter_rgb
R=Path(__file__).resolve().parents[1];V=R/'validation/cartoon_v11'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
files=[R/'user_source/hdl_source/isp/stylize_v5_96.v',R/'user_source/hdl_source/display_denoise_v11.v',R/'tools/cartoon_v11_model.py',R/'tools/display_v11_model.py',Path(__file__)]
hashes={p.relative_to(R).as_posix():sha(p) for p in files}
def display(im):
 h,w=im.shape[:2];ht=w+32;vt=h+30;rgb=np.zeros((vt,ht,3),np.uint8);rgb[:h,:w]=im;de=np.zeros((vt,ht),bool);de[:h,:w]=True;ov=np.zeros_like(de);control=np.full(de.size,40,np.uint8)
 out=filter_rgb(rgb.reshape(-1,3),de.ravel(),ov.ravel(),control,h_total=ht,width=w,height=h)
 return out.reshape(vt,ht,3)[:h,:w]
cases=[]
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
  direct=display(im);q,_=style.render(im,1,gm.guide);z=display(q)
  change=np.any(z!=q,axis=-1);interior=change[18:-12,36:-24]
  cases.append({'colour':name,'kind':kind,'direct_filter_changed':int(np.count_nonzero(np.any(direct!=im,axis=-1))),'style_then_display_changed':int(change.sum()),'style_then_display_interior_changed':int(interior.sum())})
  if kind in ['line1','line2','diag1','edge']:assert not np.any(interior),(name,kind,'legitimate line interior changed')
assert hashes=={p.relative_to(R).as_posix():sha(p) for p in files}
res={'tests':{'long_lines_diagonals_edges_interior_preserved':{'pass':True,'colour_backgrounds':4,'patterns':['line1','line2','diag1','edge'],'scope':'actual selected style and final display model, excludes pipeline border area; not a claim that every isolated genuine point is preserved'}},'diagnostics':cases,'source_and_oracle_sha256':hashes,'scope':'Physical pixel fixtures160x96 without resizing. Neutral calibration identity. Final {Y,RGB} model, default cartoon cleanup1. Tiny real1px/2x2/3x3 points can be deliberately removed; data retained below. Fixed sensor DPC ROI is outside these fixtures, so this tests global cartoon cleanup.'}
(V/'detail_quality_result.json').write_text(json.dumps(res,indent=2),encoding='utf-8');print('V11_DETAIL_QUALITY_PASS');print(cases)
