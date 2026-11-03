from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
import model_baseline as b,model_denoise as d,cartoon_v9_model as old,guide_v8_model as gm
R=Path(__file__).resolve().parents[1];V=R/'validation/cartoon_v10';V.mkdir(exist_ok=True)
def stair(c):
 c=np.asarray(c,dtype=np.int64);step=np.where(c<64,16,32);rem=c%step;base=c-rem
 q=base+np.where(rem<step//4,2*rem,np.where(rem<3*step//4,step//2,2*rem-step))
 return np.where(c==255,255,q)
def stair_fixed(c,step):
 c=np.asarray(c,dtype=np.int64);r=c%step;base=c-r
 return base+np.where(r<3*step//8,(4*r)//3,np.where(r<5*step//8,step//2,step//2+(4*(r-5*step//8))//3))
def colour(c):
 co=c[...,0]-c[...,2];t=c[...,2]+(co//2);cg=c[...,1]-t;y=t+(cg//2)
 coq=np.where(np.abs(co)<8,co,np.sign(co)*stair_fixed(np.abs(co),16));cgq=np.where(np.abs(cg)<8,cg,np.sign(cg)*stair_fixed(np.abs(cg),16))
 # Dark shades have narrower shelves, mid/high shades broader shelves.
 q=stair_fixed(y,64);q=np.where(y<64,stair_fixed(y,32),q);q=np.where((y<16)|(y>=224),y,q)
 tq=q-(cgq//2);g=cgq+tq;blue=tq-(coq//2);red=blue+coq
 return np.clip(np.stack([red,g,blue],-1),0,255)
def render(im,smooth):
 h,w=im.shape[:2];b.set_size(w,h);B,Y,M=b.core(im);ns=np.stack([np.stack(d.windows(B[...,k]),0) for k in range(3)],-1)
 center=ns[4]
 if smooth=='cross': center=(4*center+ns[1]+ns[3]+ns[5]+ns[7]+4)//8
 elif smooth=='gauss':center=np.sum(ns*np.array([1,2,1,2,4,2,1,2,1])[:,None,None,None],0)//16
 mag,edge,_=gm.guide(d.windows(Y),d.windows(M))[:3];c=colour(center);c=old.ink(c,mag,edge)
 out=np.zeros_like(im);out[6:,12:]=c
 return out
if __name__=='__main__':
 from denoise_v8_model import filter_rgb
 import json,time
 rng=np.random.default_rng(21);w,h,ht,vt=64,48,80,56;roi=(slice(12,-8),slice(20,-8));de=np.zeros((vt,ht),bool);de[:h,:w]=1;ov=np.zeros_like(de);control=np.full(de.size,40,np.uint8)
 def display(im):
  a=np.zeros((vt,ht,3),np.uint8);a[:h,:w]=im
  return filter_rgb(a.reshape(-1,3),de.ravel(),ov.ravel(),control,h_total=ht,th_dark=32,max_correction=6).reshape(vt,ht,3)[:h,:w]
 cases=[]
 for block in [1,2,4]:
  for level in range(0,256,4):
   vals={key:[] for key in ['v9','center','gauss']}
   for frame in range(5):
    ns=((h+block-1)//block,(w+block-1)//block,3);noise=rng.integers(-20,21,ns);noise=np.repeat(np.repeat(noise,block,0),block,1)[:h,:w];im=np.clip(level+noise,0,255).astype(np.uint8)
    q,_=old.render(im,1,gm.guide);vals['v9'].append(display(q)[roi])
    for key in ['center','gauss']:vals[key].append(display(render(im,key))[roi])
   std={key:float(np.asarray(v,dtype=float).std(0).mean()) for key,v in vals.items()};cases.append({'level':level,'block':block,**std})
  print('noise sweep',block,flush=True)
 for key in ['center','gauss']:
  ratios=[c[key]/c['v9'] for c in cases];i=int(np.argmax(ratios));print(key,'median',np.median(ratios),'worst',ratios[i],cases[i], 'improved',sum(r<=1 for r in ratios),'/',len(cases))
 (V/'candidate_noise.json').write_text(json.dumps(cases,indent=2))
