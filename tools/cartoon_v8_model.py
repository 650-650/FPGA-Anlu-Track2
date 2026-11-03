"""Spatial-array oracle for the V8 style pipeline, with an injected guide oracle."""
import numpy as np
import model_baseline as b
import model_denoise as d

def render(img,mode,guide,floor=12,gain=49):
 if mode==0:return img.copy(),None
 h,w=img.shape[:2];b.set_size(w,h);B,Y,M=b.core(img)
 mag,edge,support=guide(d.windows(Y),d.windows(M))[:3]
 mag=np.asarray(mag,dtype=np.int64);edge=np.asarray(edge,dtype=bool);support=np.asarray(support,dtype=bool)
 cy=d.windows(Y)[4]
 rgb=np.stack([d.windows(B[...,k])[4] for k in range(3)],-1).astype(np.uint8)
 out=np.zeros_like(img)
 if mode==1:
  shadow=np.where((cy<96)[...,None],rgb>>1,np.zeros_like(rgb))
  fill=np.where(edge[...,None],shadow,rgb)
 elif mode==2:
  ink=np.minimum(np.maximum(mag-floor,0)*gain//16,255)
  paper=224+cy//8
  fill=np.repeat(np.maximum(paper-ink,0)[...,None],3,-1).astype(np.uint8)
 else:fill=np.repeat(edge[...,None],3,-1).astype(np.uint8)*255
 out[6:,12:]=fill
 return out,{'mag':mag,'edge':edge,'support':support,'rgb':rgb,'center_y':cy}
