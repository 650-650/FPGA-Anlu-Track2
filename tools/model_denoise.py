"""Independent integer frame model for v3, using original v1 mappings/statistics."""
import numpy as np
import model_baseline as original

def windows(a):
    h,w=a.shape[:2]
    padded=np.pad(a,((0,0),(1,0)),mode='edge')
    return [padded[y:y+h-2,x:x+w-4] for y in range(3) for x in range(3)]

def guide(Y,M):
    y=windows(Y);m=windows(M);center=m[4]
    gx=(y[2]+2*y[5]+y[8])-(y[0]+2*y[3]+y[6])
    gy=(y[0]+2*y[1]+y[2])-(y[6]+2*y[7]+y[8])
    coarse=np.minimum(np.abs(gx)+np.abs(gy),255)
    smooth=np.maximum(coarse-4,0)
    tolerance=2+center//16
    coherent=np.logical_or.reduce([
        (np.abs(m[a]-center)<=tolerance)&(np.abs(m[b]-center)<=tolerance)
        for a,b in [(0,8),(1,7),(2,6),(3,5)]])
    preserve=(y[4]>=128)|(center>=128)|coherent
    limited=np.where(preserve,center,np.minimum(center,smooth))
    return y[4],center,smooth,preserve,limited

def render(B2,Y2,mag,mode,p,img):
    if mode not in (1,2):return img.astype(np.uint8)
    out=np.zeros_like(img,dtype=np.uint8)
    y,fine,smooth,preserve,limited=guide(Y2,mag)
    if mode==2:
        floor=p['phi']//8
        gain=original.gain16(p['phi']-floor)
        ink=np.minimum(np.maximum(limited-floor,0)*gain//16,255)
        paper=255-(255-y)//8
        # paper uses the exact RTL baseline: 255 - (31 - floor(Y2/8)).
        paper=255-(31-y//8)
        gray=np.maximum(paper-ink,0)
        out[6:,12:]=np.repeat(gray[...,None],3,axis=-1)
    else:
        band,_,cr,cb=original.stage2(B2,Y2,mag,mode,p)
        fill=original.stage3((band,np.zeros_like(mag,dtype=bool),cr,cb),mode,p)
        edge=(fine>=p['th'])&(preserve|(smooth>=p['th']))
        out[6:,12:]=np.where(edge[...,None],0,fill)
    return out
