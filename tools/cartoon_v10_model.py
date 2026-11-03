"""Independent fixed-point V10 colour-region model; no frame blending.

V9 protected guide/render paths are reused as their unchanged reference.
Cartoon B2 windows use exact [1,2,1] Gaussian /16, then YCoCg lifting,
shadow-preserving luminance and continuous colour shelves, bounded V9 ink. No tone learning.
"""
import numpy as np
import model_baseline as b, model_denoise as d
from cartoon_v9_model import ink

def shelf(value,period):
 v=np.asarray(value,dtype=np.int64);r=v%period;base=v-r
 q=np.where(r<3*period//8,4*r//3,np.where(r<5*period//8,period//2,period//2+4*(r-5*period//8)//3))
 return base+q

def colour(pixel):
 p=np.asarray(pixel,dtype=np.int64)
 co=p[...,0]-p[...,2];middle=p[...,2]+co//2;cg=p[...,1]-middle;y=middle+cg//2
 r=y%64;shadow_delta=np.where(r<16,r//2,np.where(r<48,(32-r)//2,(r-64)//2));shadow_delta=np.where(y<32,0,shadow_delta)
 yq=np.where(y<64,y+shadow_delta,shelf(y,64));yq=np.where(y>=224,y,yq)
 coq=np.where(np.abs(co)<16,co,np.sign(co)*shelf(np.abs(co),16))
 cgq=np.where(np.abs(cg)<16,cg,np.sign(cg)*shelf(np.abs(cg),16))
 middleq=yq-cgq//2;green=middleq+cgq;blue=middleq-coq//2;red=blue+coq
 out=np.clip(np.stack([red,green,blue],-1),0,255)
 return out,dict(y=y,yq=yq,co=co,coq=coq,cg=cg,cgq=cgq)

def render(img,mode,guide,floor=12,gain=49):
 if mode==0:return img.copy(),None
 h,w=img.shape[:2];b.set_size(w,h);B,Y,M=b.core(img)
 mag,edge,support=guide(d.windows(Y),d.windows(M))[:3]
 mag=np.asarray(mag,dtype=np.int64);edge=np.asarray(edge,dtype=bool)
 cy=d.windows(Y)[4]
 rgb=np.stack([d.windows(B[...,k])[4] for k in range(3)],-1).astype(np.int64)
 features={'mag':mag,'edge':edge,'support':np.asarray(support,dtype=bool),'rgb':rgb,'center_y':cy}
 if mode==1:
  ns=np.stack([np.stack(d.windows(B[...,k]),0) for k in range(3)],-1)
  smooth=np.sum(ns*np.array([1,2,1,2,4,2,1,2,1])[:,None,None,None],0)//16
  flat,extra=colour(smooth);fill=ink(flat,mag,edge)
  features.update(extra);features.update(smoothed=smooth,fill=flat,source=rgb)
 elif mode==2:
  amount=np.minimum(np.maximum(mag-floor,0)*gain//16,255);paper=224+cy//8
  fill=np.repeat(np.maximum(paper-amount,0)[...,None],3,-1)
 else:fill=np.repeat(edge[...,None],3,-1)*255
 out=np.zeros_like(img);out[6:,12:]=fill.astype(np.uint8)
 return out,features
