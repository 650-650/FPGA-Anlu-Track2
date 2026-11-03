"""Integer frame oracle; separate spatial convolution and vector gamut mapping."""
import numpy as np
import model_baseline as b
import model_denoise as d

def update(p,B,Y,M):
 # Reuse established statistics maths, changing only eligibility of bright neutrals.
 sel=lambda a:a[:,0::4][:,:b.GRP-2].ravel()
 q=b.update(p,B,Y,M);y=sel(Y);xb,yy=[sel(a) for a in b.content_xy(Y.shape)]
 cr=sel(B[...,0]-Y)-b.offmap(p['ocr'],p['xcr'],p['ycr'],xb,yy)
 cb=sel(B[...,2]-Y)-b.offmap(p['ocb'],p['xcb'],p['ycb'],xb,yy)
 near=((np.abs(cr)<24)&(np.abs(cb)<24))|((y>=144)&(np.abs(cr)<48)&(np.abs(cb)<48))
 right,bottom=xb>=b.GRP//2,yy>=b.H//2;tol=b.NS//128
 def bal(a,m):return int((near&m&(a>0)).sum())-int((near&m&(a<0)).sum())
 def step(v,n,lim):return min(v+1,lim) if n>tol else max(v-1,-lim) if n<-tol else v
 for ch,a in [('cr',cr),('cb',cb)]:
  q['o'+ch]=step(p['o'+ch],bal(a,np.ones_like(right)),48)
  q['x'+ch]=step(p['x'+ch],bal(a,right)-bal(a,~right),20)
  q['y'+ch]=step(p['y'+ch],bal(a,bottom)-bal(a,~bottom),20)
 return q

def render(B,Y,M,mode,p,img):
 if mode!=1:return d.render(B,Y,M,mode,p,img)
 band,_,cr,cb=b.stage2(B,Y,M,mode,p)
 h,w=b.H-6,b.W-12
 def win(a,dy=0,dx=0):
  ap=b.lpad(a);return ap[1+dy:1+dy+h,1+dx:1+dx+w]
 med=np.median(np.stack([win(band,y,x) for y in [-1,0,1] for x in [-1,0,1]]),axis=0).astype(int)
 tone=np.array(b.tones(p['t']))[med];r,c=win(cr),win(cb)
 fill=np.repeat(tone[...,None],3,axis=-1);chosen=np.zeros(tone.shape,bool)
 for scale in [0,1,2,3]:
  dr,db=r>>scale,c>>scale
  candidate=np.stack([tone+dr,tone-((dr+db)>>1),tone+db],-1)
  fits=np.all((candidate>=0)&(candidate<=255),axis=-1)&~chosen
  fill=np.where(fits[...,None],candidate,fill);chosen|=fits
 _,fine,smooth,preserve,_=d.guide(Y,M)
 th=min(p['th'],72);edge=(fine>=th)&(preserve|(smooth>=th))
 out=np.zeros_like(img);out[6:,12:]=np.where(edge[...,None],0,fill).astype(np.uint8)
 return out
