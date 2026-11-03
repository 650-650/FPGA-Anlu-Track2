from pathlib import Path
import numpy as np,json
from PIL import Image
import model_baseline as b
import model_denoise as d
import guide_v8_model as g
R=Path(__file__).resolve().parents[1];V=R/'validation/guide_v8';V.mkdir(parents=True,exist_ok=True)

def main():
 h,w=144,320;y,x=np.mgrid[:h,:w];out={}
 for kind in ['iid4','iid8','block2_8','block3_8','block4_8','phase2quiet_other20']:
  rng=np.random.default_rng(843);noise=rng.normal(0,8,(h,w))
  if kind=='iid4':noise=rng.normal(0,4,(h,w))
  if kind.startswith('block'):
   q=int(kind[5]);noise=np.repeat(np.repeat(rng.normal(0,8,((h+q-1)//q,(w+q-1)//q)),q,0),q,1)[:h,:w]
  if kind.startswith('phase'):
   noise=rng.normal(0,20,(h,w));noise[:,2::4]=rng.normal(0,2,(h,w//4))
  rgb=np.clip(np.array([36,48,64])[None,None,:]+noise[...,None]+rng.normal(0,1,(h,w,3)),0,255).astype(np.uint8)
  (B,Y,M),(mag,edge,conf,coarse)=g.frame(rgb)
  oldy,_,_,_,oldmag=d.guide(Y,M)
  ink=g.sketch(mag,oldy);oldink=g.sketch(oldmag,oldy)
  out[kind]={'edge_density':float(np.mean(edge)),'new_sketch_below210':float(np.mean(ink<210)),
   'old_fixed96_below210':float(np.mean(oldink<210)),'new_mean_mag':float(np.mean(mag)),
   'fine_mean':float(np.mean(d.windows(M)[4])),'coarse_mean':float(np.mean(coarse))}
  canvas=np.concatenate([np.repeat(ink[...,None],3,-1),np.repeat(oldink[...,None],3,-1),np.repeat((edge*255).astype(np.uint8)[...,None],3,-1)],axis=1)
  Image.fromarray(canvas).save(V/(kind+'_model.png'))
 for delta in [8,12,17,24,32,64]:
  rgb=np.full((h,w,3),48,np.uint8);rgb[16:h-16,70:72]=48+delta
  (B,Y,M),(mag,edge,conf,_)=g.frame(rgb);oldy=d.windows(Y)[4];s=g.sketch(mag,oldy)
  out['line'+str(delta)]={'edge_pixels':int(edge.sum()),'ink_below210':int((s<210).sum()),'max_mag':int(mag.max())}
 for delta in [8,12,17]:
  for orientation in ['horizontal','diag+','diag-']:
   rgb=np.full((h,w,3),48,np.uint8)
   if orientation=='horizontal':rgb[60:62,20:w-20]=48+delta
   elif orientation=='diag+':rgb[((x-y)>=30)&((x-y)<32)]=48+delta
   else:rgb[((x+y)>=200)&((x+y)<202)]=48+delta
   (B,Y,M),(mag,edge,conf,_)=g.frame(rgb);s=g.sketch(mag,d.windows(Y)[4])
   out[f'{orientation}{delta}']={'edge_pixels':int(edge.sum()),'ink_below210':int((s<210).sum()),'max_mag':int(mag.max())}
 # Same left weak line, first quiet then strong checker in distant right region.
 for textured in [False,True]:
  rgb=np.full((h,w,3),48,np.uint8);rgb[16:h-16,70:72]=65;rgb[60:62,20:w//2]=76
  if textured:
   right=(x>=w*2//3)&(y<h//2);checker=((x//3+y//3)&1)*255;rgb[right]=np.repeat(checker[...,None],3,-1)[right]
  (B,Y,M),(mag,edge,conf,_)=g.frame(rgb);s=g.sketch(mag,d.windows(Y)[4]);left=s[:,:w//2-12]
  out['scene_texture_'+str(textured)]={'left_ink_pixels_below210':int((left<210).sum()),'left_edge_pixels':int(edge[:,:w//2-12].sum())}
 (V/'experiment.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
