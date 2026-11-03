"""Multi-scene colour/noise and local-line composition experiments, not board capture."""
from pathlib import Path
import hashlib,importlib.util,json,sys
import numpy as np
from PIL import Image,ImageDraw,ImageFont
R=Path(__file__).resolve().parents[1];V=R/'validation/cartoon_v8';V.mkdir(exist_ok=True)
import model_baseline as b,cartoon_v7_model as old,cartoon_v8_model as new,model_denoise as d
gp=R/'tools/guide_v8_model.py';spec=importlib.util.spec_from_file_location('guide_quality',gp);gm=importlib.util.module_from_spec(spec);spec.loader.exec_module(gm)
W,H=384,216;rows=[];tests={};source_before=hashlib.sha256(gp.read_bytes()).hexdigest()
for name in ['test_photo','board_real_bakery','board_like_cast','board_like_lowcontrast']:
 raw=R.parent/'05_stylize_on_v5/sim'/f'{name}.raw';img=np.fromfile(raw,np.uint8).reshape(720,1280,3)
 img=np.asarray(Image.fromarray(img).resize((W,H),Image.Resampling.BILINEAR))
 for dark in [False,True]:
  name2=name+('_dark' if dark else '');im=np.clip(img.astype(float)*(0.35 if dark else 1),0,255).astype(np.uint8)
  b.set_size(W,H);B,Y,M=b.core(im);p=dict(b.P0)
  for n in range(160):p=old.update(p,B,Y,M)
  qo=old.render(B,Y,M,1,p,im);qn,features=new.render(im,1,gm.guide);qs,_=new.render(im,2,gm.guide);qe,_=new.render(im,3,gm.guide)
  fill=~features['edge'];assert np.array_equal(qn[6:,12:][fill],features['rgb'][fill]),'colour fill changed RGB'
  rows.append([(name2,im),('V7 cartoon',qo),('V8 cartoon model',qn),('V8 sketch model',qs),('V8 edge model',qe)])
  tests[name2]={'pass':True,'non_edge_rgb_exact_pixels':int(np.count_nonzero(fill))}

line_cases={};line_results=[]
for contrast in [8,12,17]:
 original=np.full((H,W,3),48,np.uint8);original[20:H-20,70:72]=48+contrast;original[60:62,20:W//2]=48+contrast
 variants={}
 for clutter in [False,True]:
  im=original.copy()
  if clutter:
   yy,xx=np.mgrid[:H//2,:W//3];block=np.where((yy//3+xx//3)%2,230,20).astype(np.uint8)
   im[10:10+H//2,W*2//3:W*2//3+W//3]=block[...,None]
  q,f=new.render(im,2,gm.guide);variants[clutter]=q
  line_results.append([(f'line delta={contrast} clutter={clutter}',im),('V8 local sketch',q)])
 mask=np.zeros((H,W),bool);mask[20:H-20,75:W//2]=True
 # Right-hand context is outside the entire local receptive field of this ROI.
 same=np.array_equal(variants[False][mask],variants[True][mask]);assert same,'right texture changed unchanged left scene'
 line_cases[str(contrast)]={'pass':True,'left_roi_pixels_exact_with_or_without_texture':int(mask.sum()),
  # A 2px bright rail has its Sobel outlines just outside its centre pixels.
  # NMS deliberately keeps these boundaries (x81/x84), not the rail centre.
  'vertical_below210':int(np.count_nonzero(variants[False][35:H-20,78:88,0]<210))}
 assert line_cases[str(contrast)]['vertical_below210']>0,'weak line lost'
tests['weak_line_composition']={'pass':True,'cases':line_cases}

# Former posterisation thresholds and skin/blue ranges: no hard bins remain.
noise_metrics={};rng=np.random.default_rng(29)
for level in [40,42,44,82,84,86,124,126,128,166,168,170,208,210,212]:
 rgb=[];col=[];false_edges=[]
 for n in range(12):
  im=np.clip(level+rng.integers(-20,21,(90,160,3)),0,255).astype(np.uint8);q,f=new.render(im,1,gm.guide)
  roi=(slice(10,-10),slice(12,-12));rgb.append(f['rgb'][roi].astype(float));col.append(q[6:,12:][roi].astype(float));false_edges.append(int(np.count_nonzero(f['edge'][roi])))
 rgb=np.array(rgb);col=np.array(col)
 noise_metrics[str(level)]={'fill_temporal_rgb_std':float(rgb.std(0).mean()),'cartoon_with_outline_temporal_rgb_std':float(col.std(0).mean()),'false_outline_pixels_12_frames':sum(false_edges)}
tests['former_threshold_noise_sweep']={'pass':True,'metrics':noise_metrics,'scope':'records full outline noise honestly; fill itself equals B2 and adds no quantisation noise'}

font=ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc',14)
def canvas(rows,path):
 c=Image.new('RGB',(len(rows[0])*W,len(rows)*(H+25)),(20,25,30));dr=ImageDraw.Draw(c)
 for y,row in enumerate(rows):
  for x,(label,im) in enumerate(row):dr.text((x*W+3,y*(H+25)+3),label,font=font,fill='white');c.paste(Image.fromarray(im),(x*W,y*(H+25)+25))
 c.save(path)
canvas(rows,V/'natural_preview.png');canvas(line_results,V/'weak_line_context.png')
assert source_before==hashlib.sha256(gp.read_bytes()).hexdigest(),'guide model changed during quality run'
result={'tests':tests,'guide_model_sha256':source_before,'source_sha256':hashlib.sha256((R/'user_source/hdl_source/isp/stylize_v5_96.v').read_bytes()).hexdigest(),'scope':'natural local RGB/synthetic low-light and noise models; not hardware observation'}
(V/'quality_result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('CARTOON_V8_QUALITY_PASS',json.dumps({k:v for k,v in result.items() if k!='tests'}),flush=True)
