from pathlib import Path
import numpy as np,json
R=Path(__file__).resolve().parents[1];V=R/'validation/edge_v7';V.mkdir(exist_ok=True)

def arrays(g):
 h,w=g.shape;z=[g[y:y+h-2,x:x+w-2].astype(int) for y in range(3) for x in range(3)]
 r=np.stack([z[2]-z[0],z[5]-z[3],z[8]-z[6]])
 c=np.stack([z[6]-z[0],z[7]-z[1],z[8]-z[2]])
 mag=np.abs(r[0]+2*r[1]+r[2])+np.abs(c[0]+2*c[1]+c[2])
 med=4*(np.abs(np.median(r,axis=0))+np.abs(np.median(c,axis=0)))
 return z,r,c,mag,med

def render(g,kind,th=40):
 if kind.startswith('h2_'):
  g=(g+np.pad(g[:,:-1],((0,0),(1,0)),mode='edge')+1)//2;kind=kind[3:]
 if kind.startswith('h3_'):
  p=np.pad(g,((0,0),(2,0)),mode='edge');g=(p[:,:-2]+2*p[:,1:-1]+p[:,2:]+2)//4;kind=kind[3:]
 z,r,c,mag,med=arrays(g)
 high=np.where(z[4]<64,th//2+8,np.where(z[4]<160,th-th//4,th));low=np.maximum(high//2,10)
 old_coh=np.any(np.stack([np.all(a>=2,axis=0)|np.all(a<=-2,axis=0) for a in [r,c]]),axis=0)
 coherent=np.any(np.stack([np.all(a>=6,axis=0)|np.all(a<=-6,axis=0) for a in [r,c]]),axis=0)
 if kind=='v6':out=(mag>=2*high)|(old_coh&(mag>=low))
 elif kind=='median':out=(med>=2*high)|(coherent&(med>=low))
 elif kind.startswith('median_diag') or kind=='direction':
  out=((med>=4*high) if kind!='direction' else np.zeros_like(med,dtype=bool))|(coherent&(mag>=low))
  ds=[(z[1]-z[3],z[5]-z[7]),(z[3]-z[7],z[1]-z[5])]
  for a,b in ds:
   cons=((a>=4)&(b>=4))|((a<=-4)&(b<=-4))
   n=np.abs(a)+np.abs(b)
   if kind=='median_diag':out|=cons&(n>=high//2)&(np.abs(a-b)<=3+(n//8))
   if kind in ['median_diag_strong','direction']:out|=cons&(n>=high)&(np.abs(a-b)<=3+(n//8))
   if kind=='median_diag_weak':out|=cons&(n>=high//2)
 elif kind=='consensus':
  pairs=np.any(np.stack([((a[0]>=4)&(a[1]>=4))|((a[0]>=4)&(a[2]>=4))|((a[1]>=4)&(a[2]>=4))|
    ((a[0]<=-4)&(a[1]<=-4))|((a[0]<=-4)&(a[2]<=-4))|((a[1]<=-4)&(a[2]<=-4)) for a in [r,c]]),axis=0)
  out=((mag>=2*high)&pairs)|(coherent&(mag>=low))
 else:raise ValueError(kind)
 result=np.zeros(g.shape,bool);result[2:,2:]=out;result[:,:4]=False;return result

def main():
 h,w=128,1280;y,x=np.mgrid[:h,:w];rng=np.random.default_rng(42);res={}
 for kind in ['v6','median_diag_strong','direction','h2_median_diag_strong','h2_direction']:
  met={}
  for sigma in [2,4,8,12]:
   g=np.clip(48+rng.normal(0,sigma,(h,w)),0,255).astype(int)
   # Reset seed so different algorithms see identical samples.
   rng=np.random.default_rng(42)
   met['gauss'+str(sigma)]=int(render(g,kind).sum())
  g=np.full((h,w),48);g[20:110:7,16:1260:19]=240
  met['impulse']=int(render(g,kind).sum())
  for strength in [8,16,64,192]:
   a=np.full((h,w),48);a[:,80:82]+=strength;a[:,720:722]+=strength;a[30:32,:]+=strength;a[90:92,:]+=strength
   a=np.clip(a,0,255);e=render(a,kind);met['vh'+str(strength)]=int(e.sum())
   a=np.full((h,w),48);a[(x-y)%320==40]+=strength;a=np.clip(a,0,255);met['diag'+str(strength)]=int(render(a,kind).sum())
  res[kind]=met
 (V/'experiment.json').write_text(json.dumps(res,indent=2),encoding='utf-8');print(json.dumps(res,indent=2))
if __name__=='__main__':main()
