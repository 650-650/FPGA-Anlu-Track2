"""Noisy real-contour measurements; complements exact streaming-oracle tests."""
from pathlib import Path
import json,numpy as np
from PIL import Image
from edge_v7_verify import core,original,R,V

def align(edge,offset):
 a=np.zeros_like(edge,dtype=bool);a[:-offset,:-offset]=edge[offset:,offset:]>0;return a

def gaplength(present):
 longest=now=0
 for p in present:
  now=0 if p else now+1;longest=max(longest,now)
 return longest

def main():
 h,w=96,160;y,x=np.mgrid[:h,:w];result=[]
 for sigma in [4,8]:
  for contrast in [16,32,64]:
   for orientation in ['vertical','horizontal','diag+','diag-']:
    rng=np.random.default_rng(20261028+sigma)
    gray=np.full((h,w),48.,float)
    if orientation=='vertical':mask=x==80;points=[(r,80) for r in range(8,h-8)]
    elif orientation=='horizontal':mask=y==48;points=[(48,c) for c in range(8,w-8)]
    elif orientation=='diag+':mask=x-y==30;points=[(r,r+30) for r in range(8,h-8)]
    else:mask=x+y==120;points=[(r,120-r) for r in range(8,h-8)]
    gray[mask]+=contrast;gray=np.clip(gray+rng.normal(0,sigma,(h,w)),0,255).astype(np.uint8)
    th7=th6=40
    for _ in range(48):e7,th7=core(gray,th7);e6,th6=original(gray,th6)
    a7,a6=align(e7,2),align(e6,1);band=np.zeros((h,w),bool)
    p7=[];p6=[]
    for r,c in points:
     # Same source-coordinate tolerance covers both stencil rim offsets.
     # Noisy 1-pixel traces need a nearby visible contour, not identical width.
     roi=(slice(r-1,r+2),slice(c-3,c+4)) if orientation in ['vertical','diag+','diag-'] else (slice(r-3,r+4),slice(c-1,c+2))
     p7.append(bool(np.any(a7[roi])));p6.append(bool(np.any(a6[roi])));band[roi]=True
    interior=np.zeros((h,w),bool);interior[8:-8,8:-8]=True;background=interior&~band
    row={'sigma':sigma,'contrast':contrast,'orientation':orientation,'v6_threshold':th6,'v7_threshold':th7,
      'sampled_line_points':len(points),'v6_nearby_contour_fraction':round(float(np.mean(p6)),4),'v7_nearby_contour_fraction':round(float(np.mean(p7)),4),
      'v6_max_missing_run':gaplength(p6),'v7_max_missing_run':gaplength(p7),
      'v6_background_white_fraction':round(float(np.mean(a6[background])),4),'v7_background_white_fraction':round(float(np.mean(a7[background])),4),
      'note':'Known synthetic 1-pixel line, source-coordinate neighborhood metric; does not distinguish every supported pixel from coincident noise.'}
    result.append(row)
    if contrast>=32:
     assert row['v7_nearby_contour_fraction']>=.95,row
    # Save side-by-side input/old/new, explicitly synthetic model output.
    rgb=np.repeat(gray[...,None],3,-1);canvas=np.concatenate([rgb,np.repeat((a6*255).astype(np.uint8)[...,None],3,-1),np.repeat((a7*255).astype(np.uint8)[...,None],3,-1)],axis=1)
    Image.fromarray(canvas).save(V/f'noisy_line_s{sigma}_c{contrast}_{orientation}.png')
    print(row,flush=True)
 (V/'noisy_contour_metrics.json').write_text(json.dumps({'cases':result,'all_strong_line_cases_above_95_percent':True,
 'scope':'Mathematical model backed by exact RTL tests; not field-camera accuracy or hardware observation'},indent=2),encoding='utf-8')
if __name__=='__main__':main()
