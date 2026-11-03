"""Independent local two-scale style guide; no frame/scene statistics.

Input nine B2 luminances and nine aligned fine Sobel magnitudes, row-major.
The upstream RGB→B1→B2 maths is supplied by the unchanged frame oracle.
"""
import numpy as np
import model_baseline as b
import model_denoise as d

def guide(y,m):
 y=np.asarray(y,dtype=np.int64);m=np.asarray(m,dtype=np.int64)
 gx=y[2]+2*y[5]+y[8]-y[0]-2*y[3]-y[6]
 gy=y[6]+2*y[7]+y[8]-y[0]-2*y[1]-y[2]
 ax,ay=np.abs(gx),np.abs(gy);coarse=np.minimum(ax+ay,255)
 vertical=ax>=2*ay;horizontal=ay>=2*ax
 same=(gx<0)==(gy<0)
 t0=np.where(vertical,m[1],np.where(horizontal,m[3],np.where(same,m[2],m[0])))
 t1=np.where(vertical,m[7],np.where(horizontal,m[5],np.where(same,m[6],m[8])))
 n0=np.where(vertical,m[3],np.where(horizontal,m[1],np.where(same,m[0],m[2])))
 n1=np.where(vertical,m[5],np.where(horizontal,m[7],np.where(same,m[8],m[6])))
 center=m[4];stable=np.median(np.stack([center,t0,t1]),axis=0).astype(np.int64)
 linked=(t0>=center//2)&(t1>=center//2)
 tolerance=2+center//8
 coherent=(np.abs(t0-center)<=tolerance)&(np.abs(t1-center)<=tolerance)
 strict=(np.abs(t0-center)<=2)&(np.abs(t1-center)<=2)
 weak_edge=(np.abs(t0-center)<=1)&(np.abs(t1-center)<=1)
 ridge=(center>=n0)&(center>=n1)
 scale=stable<=coarse+(coarse//2)+6
 confidence=linked&ridge&scale&(coarse>=8)&(coherent|(coarse>=64))
 mixed=np.minimum((3*coarse+stable)//4,center)
 trusted=np.maximum(mixed-4,0)
 fallback=np.minimum(center,np.maximum(coarse-24,0))//4
 magnitude=np.where(confidence,np.where(strict,center,trusted),fallback)
 edge=confidence&((magnitude>=32)|(weak_edge&(magnitude>=24)))
 return magnitude,edge,confidence,coarse

def frame(rgb):
 h,w=rgb.shape[:2];b.set_size(w,h)
 B,Y,M=b.core(rgb);ys=d.windows(Y);ms=d.windows(M)
 return (B,Y,M),guide(ys,ms)

def sketch(mag,y):
 # Original paper formula and phi96's floor12/gain49, locally driven magnitude.
 ink=np.minimum(np.maximum(mag-12,0)*49//16,255)
 paper=224+y//8
 return np.maximum(paper-ink,0).astype(np.uint8)

