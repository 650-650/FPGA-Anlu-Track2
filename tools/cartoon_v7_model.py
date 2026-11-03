"""Independent array oracle for V7; spatial convolutions stay in baseline maths."""
import numpy as np
import model_baseline as b
import model_denoise as d

def update(p,B,Y,M):
 q=b.update(p,B,Y,M)
 sel=lambda a:a[:,0::4][:,:b.GRP-2].ravel()
 y=sel(Y);xb,yy=[sel(a) for a in b.content_xy(Y.shape)]
 cr=sel(B[...,0]-Y)-b.offmap(p['ocr'],p['xcr'],p['ycr'],xb,yy)
 cb=sel(B[...,2]-Y)-b.offmap(p['ocb'],p['xcb'],p['ycb'],xb,yy)
 near=(((np.abs(cr)<24)&(np.abs(cb)<24))|((y>=144)&(np.abs(cr)<48)&(np.abs(cb)<48)))&((y>=96)|(np.abs(cr)+np.abs(cb)<=2+(y>>3)))
 right,bottom=xb>=b.GRP//2,yy>=b.H//2;tol=b.NS//128
 def bal(a,m):return int((near&m&(a>0)).sum())-int((near&m&(a<0)).sum())
 def step(v,n,lim):return min(v+1,lim) if n>tol else max(v-1,-lim) if n<-tol else v
 for ch,a in [('cr',cr),('cb',cb)]:
  q['o'+ch]=step(p['o'+ch],bal(a,np.ones_like(right)),48)
  q['x'+ch]=step(p['x'+ch],bal(a,right)-bal(a,~right),20)
  q['y'+ch]=step(p['y'+ch],bal(a,bottom)-bal(a,~bottom),20)
 return q

def render(B,Y,M,mode,p,img,metrics=False):
 if mode!=1:return d.render(B,Y,M,mode,p,img)
 band,_,cr,cb=b.stage2(B,Y,M,mode,p)
 h,w=b.H-6,b.W-12
 def win(a,dy=0,dx=0):
  ap=b.lpad(a);return ap[1+dy:1+dy+h,1+dx:1+dx+w]
 med=np.median(np.stack([win(band,y,x) for y in [-1,0,1] for x in [-1,0,1]]),axis=0).astype(int)
 tone=np.array(b.tones(p['t']))[med];r,c=win(cr),win(cb)
 center_y,fine,smooth,_,_=d.guide(Y,M)
 mw=d.windows(M);tolerance=2+fine//16
 stable=np.logical_or.reduce([(np.abs(mw[a]-fine)<=tolerance)&(np.abs(mw[z]-fine)<=tolerance) for a,z in [(0,8),(1,7),(2,6),(3,5)]])
 th=min(p['th'],72);flags=[a>=th for a in mw]
 connected=np.logical_or.reduce([flags[a]&flags[z] for a,z in [(0,8),(1,7),(2,6),(3,5)]])
 count=sum(flags[i].astype(int) for i in [0,1,2,3,5,6,7,8]);connected|=count>=3
 edge=(fine>=th)&((smooth>=th)|(fine>=128)|np.where(center_y>=128,connected,stable))
 floor=np.minimum((center_y-(center_y>>3))&248,64);tone=np.maximum(tone,floor)
 shadow_ink=edge&(center_y<96);tone=np.where(shadow_ink,tone>>1,tone)
 r,c=np.where(shadow_ink,r>>1,r),np.where(shadow_ink,c>>1,c)
 fill=np.repeat(tone[...,None],3,axis=-1);chosen=np.zeros(tone.shape,bool)
 for scale in [0,1,2,3]:
  dr,db=r>>scale,c>>scale;candidate=np.stack([tone+dr,tone-((dr+db)>>1),tone+db],-1)
  fits=np.all((candidate>=0)&(candidate<=255),axis=-1)&~chosen
  fill=np.where(fits[...,None],candidate,fill);chosen|=fits
 out=np.zeros_like(img);out[6:,12:]=np.where((edge&(center_y>=96))[...,None],0,fill).astype(np.uint8)
 return (out,{'edge':edge,'shadow_ink':shadow_ink,'center_y':center_y}) if metrics else out
