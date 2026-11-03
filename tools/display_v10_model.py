"""V10 clear retains V9; independent absolute-stream-offset oracle, not an RTL RAM model."""
import numpy as np

def filter_rgb(rgb,de,overlay,control,h_total=1650,th_dark=32,th_bright=16,max_correction=6):
    rgb=np.asarray(rgb,dtype=np.uint8); c=rgb.astype(np.int16)
    de=np.asarray(de,dtype=bool);overlay=np.asarray(overlay,dtype=bool);control=np.asarray(control,dtype=np.uint8)
    n=len(c); neighbours=[];valid=[]
    for offset in [-1,1,-h_total,h_total]:
        index=np.arange(n)+offset;inside=(index>=0)&(index<n);safe=np.clip(index,0,n-1)
        neighbours.append(c[safe])
        valid.append(inside&de[safe]&~overlay[safe]&((control[safe]>>3)==(control>>3)))
    enabled=de&~overlay&(((control>>5)==0)|(((control>>5)==1)&((control&0x18)==0)))
    enabled&=np.logical_and.reduce(valid)
    luma=(c[:,0]+2*c[:,1]+c[:,2])//4
    threshold=np.maximum(th_bright,th_dark-np.maximum(luma-64,0)//8)
    sums=4*c
    for neighbour in neighbours:
        accepted=enabled&(np.abs(neighbour-c).max(axis=1)<=threshold)
        sums+=np.where(accepted[:,None],neighbour,c)
    target=(sums+4)//8
    return (c+np.clip(target-c,-max_correction,max_correction)).astype(np.uint8)
