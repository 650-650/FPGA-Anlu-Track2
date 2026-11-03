"""Proposal-only impulse repair over existing one-pixel display cross taps.

No production edits. Non-event RGB is the exact existing clear-filter oracle;
metadata is not transformed. A local bright point and a real same-RGB punctuation
point are deliberately indistinguishable in the global blind proposal.
"""
import numpy as np
from display_v9_model import filter_rgb as clear_filter

def repair(rgb,de,overlay,control,h_total,policy='colour',roi=None,bad_mask=None,
           min_known_support=2,known_all_visual=False,coherence=8,min_distance=96,
           min_peak=224,min_colour=80,min_colour_y=96,min_white_y=224,min_white_delta=80,
           allow_sw2_display=False):
    rgb=np.asarray(rgb,dtype=np.uint8);c=rgb.astype(np.int16);n=len(c)
    de=np.asarray(de,bool);overlay=np.asarray(overlay,bool);control=np.asarray(control,np.uint8)
    base=clear_filter(rgb,de,overlay,control,h_total)
    neighbours=[];valid=[];m=np.zeros(n,bool) if bad_mask is None else np.asarray(bad_mask,bool)
    for delta in [-h_total,h_total,-1,1]:
        ix=np.arange(n)+delta;inside=(ix>=0)&(ix<n);safe=np.clip(ix,0,n-1)
        neighbours.append(c[safe])
        v=inside&de[safe]&~overlay[safe]&((control[safe]>>3)==(control>>3))
        if bad_mask is not None:v&=~m[safe]
        valid.append(v)
    p=np.stack(neighbours);valid=np.stack(valid);count=valid.sum(0)
    sums=np.where(valid[:,:,None],p,0).sum(0)
    bg=(sums+count[:,None]//2)//np.maximum(count[:,None],1)
    dist=lambda a,b:np.abs(a-b).max(-1)
    group=control>>5;page=(control>>3)&3
    visual=(group==0)|((group==1)&((page<2)|known_all_visual))
    if allow_sw2_display:visual|=group==2
    eligible=de&~overlay&visual
    if roi is not None:eligible&=np.asarray(roi,bool)
    if bad_mask is not None:
        # This is conditional interpolation of precisely established bad sites,
        # not an unconditional rectangle fill. Single-support mode is explicit.
        agree=np.ones(n,bool)
        for a in range(4):
            for b in range(a+1,4):agree&=~(valid[a]&valid[b])|(dist(p[a],p[b])<=12)
        event=eligible&m&(count>=min_known_support)&agree&(dist(c,bg)>=64)
    else:
        pair0=(p[0]+p[1]+1)//2;pair1=(p[2]+p[3]+1)//2
        coherent=(dist(p[0],p[1])<=coherence)&(dist(p[2],p[3])<=coherence)&(dist(pair0,pair1)<=coherence)
        yc=(c[:,0]+2*c[:,1]+c[:,2])//4;yb=(bg[:,0]+2*bg[:,1]+bg[:,2])//4
        co=c[:,0]-c[:,2];cob=bg[:,0]-bg[:,2]
        cg=c[:,1]-(c[:,0]+c[:,2])//2;cgb=bg[:,1]-(bg[:,0]+bg[:,2])//2
        colour=(c.max(1)>=min_peak)&(yc>=min_colour_y)&((np.abs(co-cob)>=min_colour)|(np.abs(cg-cgb)>=min_colour))
        bright=(yc>=min_white_y)&(yc-yb>=min_white_delta)
        impulse=colour if policy=='colour' else colour|bright
        event=eligible&valid.all(0)&coherent&(dist(c,bg)>=min_distance)&impulse
    out=np.where(event[:,None],bg,base).astype(np.uint8)
    assert np.array_equal(out[~event],base[~event])
    return out,event,{'eligible':eligible,'support':count,'background':bg.astype(np.uint8)}
