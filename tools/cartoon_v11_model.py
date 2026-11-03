"""V11 categorical colour-region prototype; independent spatial oracle.

Native pixel sampling only. Modes0/2/3 retain the V10/V8 guide and rendering.
Cartoon: denoised B2 luma -> fixed ordered bands -> 3x3 label median ->
fixed palette luma, original or categorical chroma and a common gamut guard.
No third Gaussian and no continuous-luma shelf.
"""
import numpy as np
import model_baseline as b,model_denoise as d
PALETTES={6:np.array([0,51,102,153,204,255],dtype=np.int64),8:np.array([0,36,73,109,146,182,219,255],dtype=np.int64)}
def bands(y,levels=6):
 p=PALETTES[levels];threshold=(p[:-1]+p[1:])//2
 return np.sum(np.asarray(y)[...,None]>threshold,axis=-1).astype(np.int64)
def tint(rgb,palette_y,chroma_step=0):
 p=np.asarray(rgb,dtype=np.int64);y=b.gray(p)
 if chroma_step:
  co=p[...,0]-p[...,2];t=p[...,2]+co//2;cg=p[...,1]-t
  def cq(c):
   a=np.abs(c);q=np.minimum(((a+chroma_step//2)//chroma_step)*chroma_step,255)
   return np.where(a<chroma_step,c,np.sign(c)*q)
  co,cg=cq(co),cq(cg);t=y-cg//2;g=t+cg;bl=t-co//2;red=bl+co
  p=np.stack([red,g,bl],-1)
  # Chroma quantisation may exceed gamut by a few codes; a common correction
  # fits all components, preserving their relative differences.
  p=p+np.maximum(-p.min(-1),np.minimum(255-p.max(-1),0))[...,None]
 delta=np.asarray(palette_y,dtype=np.int64)-y
 delta=np.maximum(-p.min(-1),np.minimum(255-p.max(-1),delta))
 return np.clip(p+delta[...,None],0,255)
def ink(fill,mag,edge):
 # Clear thin ink, bounded at 5/8 darkening; no unconditional black pixels.
 drop=np.where((mag<64)[...,None],fill//4,fill//2)
 return np.where(edge[...,None],fill-drop,fill)
def smooth_guard_target(tone,cy,span,support,levels=6,dead=8,blend=4):
 thresholds=(PALETTES[levels][:-1]+PALETTES[levels][1:])//2
 dist2=np.min(np.abs(2*cy[...,None]-(2*thresholds+1)),axis=-1)
 amount=np.clip(dist2-2*dead,0,2*blend)
 mixed=cy+((tone-cy)*amount)//(2*blend)
 flat=(span<=12)&(~np.asarray(support,dtype=bool))
 return np.where(flat,mixed,tone),flat&(amount<2*blend)
def first_scale_median_labels(img,levels=6):
 h,w=img.shape[:2];P=b.lpad(np.asarray(img,dtype=np.int64));v=P[:h-2]+2*P[1:h-1]+P[2:h]
 first=(v[:,0:w-1]+2*v[:,1:w]+v[:,2:w+1])//16
 g=b.lpad(b.gray(first));nc=w-8
 ns=np.stack([g[dy:dy+h-4,1+dx:1+dx+nc] for dy in range(3) for dx in [-1,0,1]],0)
 return np.sort(bands(ns,levels),axis=0)[4]
def render(img,mode,guide,floor=12,gain=49,levels=6,chroma_step=0,label_median=True,stages=1,guard=False,confidence=7):
 if mode==0:return img.copy(),None
 h,w=img.shape[:2];b.set_size(w,h);B,Y,M=b.core(img)
 mag,edge,support=guide(d.windows(Y),d.windows(M))[:3];mag=np.asarray(mag,dtype=np.int64);edge=np.asarray(edge,dtype=bool)
 cy=d.windows(Y)[4];rgb=np.stack([d.windows(B[...,k])[4] for k in range(3)],-1).astype(np.int64)
 features={'mag':mag,'edge':edge,'support':np.asarray(support,dtype=bool),'rgb':rgb,'center_y':cy}
 if mode==1:
  labels=first_scale_median_labels(img,levels) if stages==2 else bands(Y,levels);n=np.stack(d.windows(labels),0);med=np.sort(n,axis=0)[4] if label_median else n[4]
  tone=PALETTES[levels][med]
  support_count=np.sum(n==med[None,...],axis=0)
  yn=np.stack(d.windows(Y),0);span=yn.max(0)-yn.min(0)
  fallback=(support_count<confidence)&(~np.asarray(support,dtype=bool))&(span<=12) if guard else np.zeros_like(med,dtype=bool)
  target=np.where(fallback,cy,tone)
  if isinstance(guard,str) and guard.startswith('smooth'):
   dead,blend=map(int,guard[6:].split('_'));target,fallback=smooth_guard_target(tone,cy,span,support,levels,dead,blend)
  flat=tint(rgb,target,chroma_step);fill=ink(flat,mag,edge)
  rough=np.abs(yn[3]+yn[5]-2*cy)+np.abs(yn[1]+yn[7]-2*cy)
  features.update(labels=n[4],median=med,tones=tone,target=target,fill=flat,support_count=support_count,span=span,fallback=fallback,rough=rough)
 elif mode==2:
  amount=np.minimum(np.maximum(mag-floor,0)*gain//16,255);paper=224+cy//8;fill=np.repeat(np.maximum(paper-amount,0)[...,None],3,-1)
 else:fill=np.repeat(edge[...,None],3,-1)*255
 out=np.zeros_like(img);out[6:,12:]=fill.astype(np.uint8)
 return out,features
