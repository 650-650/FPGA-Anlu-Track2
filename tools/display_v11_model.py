"""Independent absolute-time model for the combined V11 display stage.

Vector median is obtained by a NumPy whole-nine sort, not the RTL's 19-compare
network. Returned RGB is indexed at the original input coordinate; the RTL's
sample-edge lag is tested separately with all 36 packet bits.
"""
import numpy as np
from display_v9_model import filter_rgb as clear_cross

def filter_rgb(rgb,de,overlay,control,h_total=1650,width=1280,height=720,vs=None,
               roi=(672,720,144,176),diagnostics=False,cartoon_despeckle=True):
    rgb=np.asarray(rgb,np.uint8);c=rgb.astype(np.int16);n=len(c)
    de=np.asarray(de,bool);overlay=np.asarray(overlay,bool);control=np.asarray(control,np.uint8)
    baseline=clear_cross(rgb,de,overlay,control,h_total)
    samples=[];valid=[]
    offsets=[dy*h_total+dx for dy in [-2,0,2] for dx in [-2,0,2]]
    for delta in offsets:
        ix=np.arange(n)+delta;inside=(ix>=0)&(ix<n);safe=np.clip(ix,0,n-1)
        samples.append(c[safe]);valid.append(inside&de[safe]&~overlay[safe]&((control[safe]>>3)==(control>>3)))
    p=np.stack(samples)
    yy=(p[:,:,0]+2*p[:,:,1]+p[:,:,2])//4
    packed=(yy.astype(np.uint32)<<24)|(p[:,:,0].astype(np.uint32)<<16)|(p[:,:,1].astype(np.uint32)<<8)|p[:,:,2].astype(np.uint32)
    med=np.sort(packed,axis=0)[4]
    m=np.stack([(med>>16)&255,(med>>8)&255,med&255],axis=1).astype(np.int16)
    my=(med>>24).astype(np.int16);y=(c[:,0]+2*c[:,1]+c[:,2])//4
    before=np.cumsum(de.astype(np.int64))-de
    if vs is None:start=np.zeros(n,np.int64)
    else:
        vs=np.asarray(vs,bool);rise=vs&~np.r_[False,vs[:-1]]
        start=np.maximum.accumulate(np.where(rise,before,0))
    rank=before-start;x=rank%width;row=(rank//width)%height
    x0,x1,y0,y1=roi;in_roi=(x>=x0)&(x<x1)&(row>=y0)&(row<y1)
    group=control>>5;page=(control>>3)&3;colour_page=~((group==1)&(page>=2))
    coherent=np.abs(p-m).max(2)<=32;coherent[4]=False;count=coherent.sum(0)
    continuation=np.abs(p-c).max(2)<=16
    line=np.logical_or.reduce([continuation[a]&continuation[b] for a,b in [(0,8),(1,7),(2,6),(3,5)]])
    co=c[:,0]-c[:,2];mco=m[:,0]-m[:,2]
    cg=c[:,1]-(c[:,0]+c[:,2])//2;mcg=m[:,1]-(m[:,0]+m[:,2])//2
    bright=(y>=160)&(y-my>=48)
    coloured=(c.max(1)>=160)&((np.abs(co-mco)>=48)|(np.abs(cg-mcg)>=48))
    window_valid=de&~overlay&np.logical_and.reduce(valid)
    dpc_event=window_valid&colour_page&in_roi&~line&(count>=5)&(np.abs(c-m).max(1)>=64)&(bright|coloured)
    coh24=np.abs(p-m).max(2)<=24;coh24[4]=False;count24=coh24.sum(0)
    cartoon_event=window_valid&(group==1)&(page==1)&(np.abs(y-my)>=32)&(count24>=7)&bool(cartoon_despeckle)
    event=dpc_event|cartoon_event
    out=np.where(event[:,None],m,baseline).astype(np.uint8)
    assert np.array_equal(out[~event],baseline[~event])
    if diagnostics:return out,event,{'median_rgb':m.astype(np.uint8),'coherent_count':count,'coherent24_count':count24,
        'dpc_event':dpc_event,'cartoon_event':cartoon_event,'line_continues':line,'x':x,'y':row,'baseline':baseline}
    return out
