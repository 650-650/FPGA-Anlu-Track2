"""Independent spatial oracle for the mode1-only V9 painterly renderer.

RGB range decisions use all three colour channels; equal-luma colour detail is
not classified as a flat grey surface. No temporal state or new frame buffer.
The guide and modes0/2/3 are the frozen V8 algorithms.
"""
import numpy as np
import model_baseline as b
import model_denoise as d


def distance(a, z):
    return np.max(np.abs(a-z), axis=-1)


def colour_fill(neighbours, step=64):
    n = np.asarray(neighbours, dtype=np.int64)
    center = n[4]
    dist = distance(n, center)
    # A real thin line has continuation in one direction and a different,
    # locally coherent background on both sides. Tolerances, not equality.
    line = np.zeros(center.shape[:-1], dtype=bool)
    for t0,t1,n0,n1 in [(1,7,3,5),(3,5,1,7),(0,8,2,6),(2,6,0,8)]:
        line |= ((dist[t0]<=2)&(dist[t1]<=2)&
                 (dist[n0]>=4)&(dist[n1]>=4)&(distance(n[n0],n[n1])<=2))
    selected = np.where((dist<=16)[...,None],n,center)
    smooth = np.sum(selected*np.array([1,2,1,2,4,2,1,2,1])[:,None,None,None],axis=0)//16
    smooth = np.where(line[...,None],center,smooth)
    y = b.gray(smooth)
    r = y % step
    # Continuous soft staircase. Half strength: plateau slope 1/2, transition
    # slope 3/2. Step64 has at most eight codes of shared RGB correction.
    q = y-r+np.where(r<step//4,2*r,np.where(r<3*step//4,step//2,2*r-step))
    q = np.where(y==255,255,q)
    delta = (q-y)//2
    # Anchor the first/last half-periods: do not steepen black/white-floor noise.
    # Their join corrections are zero, so neither endpoint creates a cutoff.
    delta = np.where((y<step//2)|(y>=256-step//2),0,delta)
    delta = np.maximum(-smooth.min(-1),np.minimum(255-smooth.max(-1),delta))
    # Preserve the brightness contrast as well as hue of a supported thin line.
    delta = np.where(line,0,delta)
    return smooth+delta[...,None], {'line':line,'smoothed':smooth,'delta':delta,'source':center}


def ink(fill, mag, edge):
    # Weak/medium/strong lines remove 1/8, 1/4 or 3/8 of each colour channel.
    # A single guide decision can no longer replace a mid/bright pixel by black.
    drop = np.where((mag<48)[...,None],fill//8,
                    np.where((mag<96)[...,None],fill//4,fill//4+fill//8))
    return np.where(edge[...,None],fill-drop,fill)


def render(img,mode,guide,floor=12,gain=49,step=64):
    if mode==0:return img.copy(),None
    h,w=img.shape[:2];b.set_size(w,h);B,Y,M=b.core(img)
    mag,edge,support=guide(d.windows(Y),d.windows(M))[:3]
    mag=np.asarray(mag,dtype=np.int64);edge=np.asarray(edge,dtype=bool)
    cy=d.windows(Y)[4]
    rgb=np.stack([d.windows(B[...,k])[4] for k in range(3)],-1).astype(np.int64)
    features={'mag':mag,'edge':edge,'support':np.asarray(support,dtype=bool),'rgb':rgb,'center_y':cy}
    if mode==1:
        n=np.stack([np.stack(d.windows(B[...,k]),axis=0) for k in range(3)],axis=-1)
        flat,extra=colour_fill(n,step=step);fill=ink(flat,mag,edge)
        features.update(extra);features['fill']=flat
    elif mode==2:
        amount=np.minimum(np.maximum(mag-floor,0)*gain//16,255)
        paper=224+cy//8
        fill=np.repeat(np.maximum(paper-amount,0)[...,None],3,-1)
    else:fill=np.repeat(edge[...,None],3,-1)*255
    out=np.zeros_like(img);out[6:,12:]=fill.astype(np.uint8)
    return out,features
