"""Known-truth coverage, line preservation and explicit median-DPC limits."""
from pathlib import Path
import hashlib,json
import numpy as np
from display_v11_model import filter_rgb
R=Path(__file__).resolve().parents[1];V=R/'validation/display_v11';V.mkdir(exist_ok=True)
OFF=np.array([(dy,dx) for dy in [-2,0,2] for dx in [-2,0,2]])
def classify(p):
    a=p.astype(np.int16);y=(a[:,:,0]+2*a[:,:,1]+a[:,:,2])//4
    key=(y.astype(np.uint32)<<24)|(a[:,:,0].astype(np.uint32)<<16)|(a[:,:,1].astype(np.uint32)<<8)|a[:,:,2].astype(np.uint32)
    ix=np.argsort(key,axis=1)[:,4];m=a[np.arange(len(a)),ix];c=a[:,4];my=y[np.arange(len(a)),ix];cy=y[:,4]
    coh=(np.abs(a-m[:,None,:]).max(2)<=32);coh[:,4]=False
    close=np.abs(a-c[:,None,:]).max(2)<=16
    line=np.logical_or.reduce([close[:,i]&close[:,j] for i,j in [(0,8),(1,7),(2,6),(3,5)]])
    co=c[:,0]-c[:,2];mo=m[:,0]-m[:,2];cg=c[:,1]-(c[:,0]+c[:,2])//2;mg=m[:,1]-(m[:,0]+m[:,2])//2
    bright=(cy>=160)&(cy-my>=48);colour=(c.max(1)>=160)&((np.abs(co-mo)>=48)|(np.abs(cg-mg)>=48))
    event=~line&(coh.sum(1)>=5)&(np.abs(c-m).max(1)>=64)&(bright|colour)
    return event,ix,m,line
formal=[]
for hh in range(1,5):
 for ww in range(1,5):
  cy,cx=np.indices((hh,ww));cy=cy.ravel();cx=cx.ravel()
  inside=(cy[:,None]+OFF[:,0]>=0)&(cy[:,None]+OFF[:,0]<hh)&(cx[:,None]+OFF[:,1]>=0)&(cx[:,None]+OFF[:,1]<ww)
  assert inside.sum(1).max()<=4
  continuation=np.logical_or.reduce([inside[:,i]&inside[:,j] for i,j in [(0,8),(1,7),(2,6),(3,5)]])
  assert not continuation.any()
  formal.append(dict(height=hh,width=ww,centres=hh*ww,maximum_hot_samples=int(inside.sum(1).max()),opposite_hot_pair=False))
shapes=[(1,1),(1,2),(2,2),(2,4),(4,4),(5,5)]
colours={'yellow':[255,255,0],'white':[255,255,255],'red':[255,0,0],
         'green':[0,255,0],'blue':[0,0,255],'cyan':[0,255,255],'magenta':[255,0,255]}
backgrounds=[[64,64,64],[112,82,62],[192,192,192]];rng=np.random.default_rng(20261105);coverage=[]
for hh,ww in shapes:
 for colour,hot in colours.items():
  for bg in backgrounds:
   for sigma in [0,4,8]:
    fixed=0;total=0;hot_medians=0;lines=0
    for py,px in [(0,0),(0,1),(1,0),(1,1)]:
     truth=np.clip(np.array(bg)+rng.normal(0,sigma,(hh+12,ww+12,1))+rng.normal(0,0 if sigma==0 else 1,(hh+12,ww+12,3)),0,255).round().astype(np.uint8)
     im=truth.copy();im[4+py:4+py+hh,4+px:4+px+ww]=hot
     cy,cx=np.indices((hh,ww));cy=cy.ravel()+4+py;cx=cx.ravel()+4+px
     p=im[cy[:,None]+OFF[:,0],cx[:,None]+OFF[:,1]]
     event,ix,m,line=classify(p)
     inside=(cy[:,None]+OFF[:,0]>=4+py)&(cy[:,None]+OFF[:,0]<4+py+hh)&(cx[:,None]+OFF[:,1]>=4+px)&(cx[:,None]+OFF[:,1]<4+px+ww)
     fixed+=int(event.sum());total+=len(event);hot_medians+=int(inside[np.arange(len(ix)),ix].sum());lines+=int(line.sum())
    eligible_flat=max(abs(int(hot[k])-bg[k]) for k in range(3))>=64
    if sigma==0 and hh<=4 and ww<=4 and eligible_flat:assert fixed==total,(hh,ww,colour,bg,fixed,total)
    coverage.append(dict(shape=[hh,ww],colour=colour,background=bg,noise_sigma=sigma,
        tested_bad_pixels=total,repaired_pixels=fixed,repair_fraction=fixed/total,median_was_hot=hot_medians,
        line_guarded=lines,flat_contrast_at_least64=eligible_flat))
# Actual stream model exercises full-window border/metadata, baseline-clear
# identity outside events, all protected modes, and global cartoon cleanup.
w,h,ht,vt=128,96,160,128;y,x=np.indices((vt,ht));de=(x<w)&(y<h);over=np.zeros_like(de)
roi=(48,80,32,64);features=[]
for mode in [0,0x20,0x28,0x30,0x38,0x40,0x60]:
 for kind in ['horizontal1','horizontal2','vertical1','vertical2','diag1','diag2','anti_diag1','anti_diag2','edge','yellow_point','white_point','yellow_2x2']:
  im=np.full((*de.shape,3),64,np.uint8)
  if kind.startswith('horizontal'):mask=(y>=47)&(y<47+int(kind[-1]))
  elif kind.startswith('vertical'):mask=(x>=63)&(x<63+int(kind[-1]))
  elif kind.startswith('anti_diag'):mask=(x+y>=111)&(x+y<111+int(kind[-1]))
  elif kind.startswith('diag'):mask=(x-y>=16)&(x-y<16+int(kind[-1]))
  elif kind=='edge':mask=x>=64
  elif kind=='yellow_2x2':mask=(x>=63)&(x<65)&(y>=47)&(y<49)
  else:mask=(x==64)&(y==48)
  im[mask]=[255,255,255] if kind=='white_point' else [255,255,0]
  ctrl=np.full(de.size,mode,np.uint8)
  out,event,d=filter_rgb(im.reshape(-1,3),de.ravel(),over.ravel(),ctrl,ht,w,h,roi=roi,diagnostics=True)
  if kind not in ['yellow_point','white_point','yellow_2x2']:assert not event.any(),(mode,kind,int(event.sum()))
  if mode in [0x30,0x38]:assert np.array_equal(out,im.reshape(-1,3)) and not event.any()
  assert np.array_equal(out[~event],d['baseline'][~event])
  features.append(dict(mode=hex(mode),feature=kind,events=int(event.sum()),dpc_events=int(d['dpc_event'].sum()),cartoon_events=int(d['cartoon_event'].sum()),non_event_exact=True))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
result={'tests':{'all_rectangles_up_to4x4_geometry':{'pass':True,'cases':len(formal)},
                 'flat_highcontrast_RGB_rectangles':{'pass':True},'long_fine_lines_steps_and_protected_modes':{'pass':True,'cases':len(features)}},
 'rectangle_geometry':formal,'coverage':coverage,'features':features,
 'limits':['A real isolated bright/coloured point or <=4x4 punctuation inside the DPC gate is indistinguishable from the same sampled defect.',
           '5x5 and larger patches may span opposite taps; line preservation and median majority deliberately leave a residual counterexample.',
           'With noisy nearly equal-luma coloured foreground/background the luma median can still be a hot vector despite RGB background majority; the coherence requirement rejects it instead of inventing a colour.',
           'Cartoon global cleanup intentionally removes tiny isolated legitimate categories as well as noise; it is enabled only in cartoon, selects an existing vector, and never averages RGB.'],
 'scope':'Synthetic known-truth model evidence, not captured FPGA RGB. Flat separated-value <=4x4 guarantee is not extended to arbitrary noisy/equal-luma colours.',
 'source_sha256':{'user_source/hdl_source/display_denoise_v11.v':sha(R/'user_source/hdl_source/display_denoise_v11.v')},
 'oracle_sha256':{p.relative_to(R).as_posix():sha(p) for p in [Path(__file__),R/'tools/display_v11_model.py',R/'tools/display_v9_model.py']}}
(V/'quality_result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
lines=['# Combined V11 display-stage known-truth quality','',result['scope'],'',
       '| Yellow on grey64 | noise0 repaired/total | noise4 repaired/total | noise8 repaired/total |', '|---|---:|---:|---:|']
for shape in shapes:
 cases=[next(a for a in coverage if a['shape']==list(shape) and a['colour']=='yellow' and a['background']==[64,64,64] and a['noise_sigma']==s) for s in [0,4,8]]
 lines.append('|'+str(shape)+'|'+'|'.join(f"{a['repaired_pixels']}/{a['tested_bad_pixels']}" for a in cases)+'|')
lines+=['','All16 rectangle dimensions1..4 and every center position have at most4 hot samples in the nine-point grid and cannot form an opposite radius-two continuation. Every eligible noiseless RGB colour/background fixture is repaired. Independent noisy R/G/B/white/yellow cases and their misses remain in quality_result.json.','',
        'The four-direction continuation guard preserves long one/two-pixel horizontal, vertical and diagonal lines and steps in all tested pages. It does not preserve an isolated true point/short punctuation indistinguishable from the source defect. Sketch/edge and overlay remain exact; SW2 display repairs only qualified ROI events after detection.','',
        'Normal clear uses its own one-pixel V9 window independently of outer-grid validity. Outside actual DPC/cleanup events the complete output is asserted equal to the original clear oracle or exact non-clear input. Cartoon cleanup is the explicitly authorized global7/8-coherent vector selection, not an RGB blur.','']+result['limits']
(V/'quality_report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8');print('\n'.join(lines))
