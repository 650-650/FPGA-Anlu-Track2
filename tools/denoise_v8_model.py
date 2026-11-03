"""Independent causal RGB display-filter oracle; indexes time, not RTL RAM."""
import numpy as np

def filter_rgb(rgb,de,overlay,control,h_total=1650,stride=4,th_dark=40,th_bright=16,max_correction=12):
 rgb=np.asarray(rgb,dtype=np.uint8);de=np.asarray(de,dtype=bool);overlay=np.asarray(overlay,dtype=bool);control=np.asarray(control,dtype=np.uint8)
 n=len(rgb);center=rgb.astype(np.int16)
 luma=(center[:,0]+2*center[:,1]+center[:,2])//4
 threshold=np.maximum(th_bright,th_dark-np.maximum(luma-64,0)//8)
 mode=control>>3
 change=np.r_[mode[0]!=0,mode[1:]!=mode[:-1]]
 last_change=np.maximum.accumulate(np.where(change,np.arange(n),-1))
 age=np.arange(n)-last_change
 warm=age>=stride*h_total+stride+1
 enabled=((control>>5)<2)&~(((control>>5)==1)&(((control>>3)&3)>=2))&de&~overlay
 sums=4*center;neighbours=[];validities=[];distances=[]
 for which,offset in enumerate([stride,stride*h_total+stride,stride*h_total,stride*h_total-stride]):
  neighbour=np.zeros_like(center);nd=np.zeros(n,bool);no=np.ones(n,bool);valid_time=np.zeros(n,bool)
  neighbour[offset:]=center[:-offset];nd[offset:]=de[:-offset];no[offset:]=overlay[:-offset];valid_time[offset:]=True
  valid=valid_time&nd&~no
  if which:valid&=warm
  else:valid&=age>=stride
  distance=np.abs(neighbour-center).max(1)
  accepted=valid&(distance<=threshold)&enabled
  sums+=np.where(accepted[:,None],neighbour,center)
  neighbours.append(neighbour);validities.append(valid);distances.append(distance)
 valid=np.stack(validities);exact=valid&(np.stack(distances)==0)
 protect=np.zeros(n,bool)
 for k in range(4):
  background=valid[k]&~exact[k]
  consistent=np.logical_and.reduce([exact[j]|np.all(neighbours[j]==neighbours[k],1) for j in range(4)])
  protect|=background&exact.any(0)&valid.all(0)&consistent&(distances[k]>=8)
 sums=np.where(protect[:,None],8*center,sums)
 target=(sums+4)>>3
 delta=np.clip(target-center,-max_correction,max_correction)
 out=(center+delta).astype(np.uint8)
 return out

def synthetic_metrics():
 rng=np.random.default_rng(20261029);w,h,ht,vt=192,128,208,136
 de=np.zeros((vt,ht),bool);de[:h,:w]=1
 overlay=np.zeros_like(de);control=np.zeros(de.size,np.uint8);results=[]
 for block in [1,2,3,4]:
  common=rng.normal(0,8,(int(np.ceil(h/block)),int(np.ceil(w/block)),1))
  chroma=rng.normal(0,2,(int(np.ceil(h/block)),int(np.ceil(w/block)),3))
  noise=np.repeat(np.repeat(common+chroma,block,0),block,1)[:h,:w]
  inp=np.zeros((vt,ht,3),np.uint8);inp[:h,:w]=np.clip(np.array([48,42,32])+noise,0,255).round().astype(np.uint8)
  for stride in [1,2,3,4]:
   for t in [16,20,24,28]:
    output=filter_rgb(inp.reshape(-1,3),de.ravel(),overlay.ravel(),control,ht,stride,t,10,6).reshape(vt,ht,3)
    valid=np.zeros_like(de);valid[12:h-4,12:w-8]=True
    old=inp[valid].astype(float)-np.array([48,42,32]);new=output[valid].astype(float)-np.array([48,42,32])
    results.append({'block':block,'stride':stride,'dark_threshold':t,'input_std':float(old.std()),'output_std':float(new.std()),'std_ratio':float(new.std()/old.std()),'maximum_delta':int(np.abs(output.astype(int)-inp.astype(int)).max())})
 return results

if __name__=='__main__':
 import json
 for r in synthetic_metrics():
  if r['stride']==2 and r['dark_threshold'] in [20,28]:print(json.dumps(r))
