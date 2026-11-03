"""V11 selected HARD6 style + FINAL combined display model, native pixels.

All natural photographs are processed at full1280x720 BEFORE any display-only
thumbnail. Neutral colour gains4096/4096 trim0 are an explicit reference
scenario, not guessed board AWB. The final display model uses the real {Y,RGB}
vector-median tie key and enabled categorical cleanup; no old RGB finish.
"""
from pathlib import Path
import hashlib,json,time
import numpy as np
from PIL import Image,ImageDraw
import cartoon_v11_model as new,cartoon_v10_model as old,guide_v8_model as gm
from display_v11_model import filter_rgb as final_display
from denoise_v8_model import filter_rgb as prior_finish
R=Path(__file__).resolve().parents[1];V=R/'validation/cartoon_v11';H=R/'user_source/hdl_source';start=time.time()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
source_names=['isp/stylize_v5_96.v','isp/style_guide_v8.v','display_denoise_v11.v','color_luma_preserve.v','display_contrast.v']
sources={(H/f).relative_to(R).as_posix():sha(H/f) for f in source_names}
model_names=['cartoon_v11_model.py','cartoon_v10_model.py','guide_v8_model.py','model_baseline.py','model_denoise.py','display_v11_model.py','display_v9_model.py','denoise_v8_model.py']
oracles={(R/'tools'/f).relative_to(R).as_posix():sha(R/'tools'/f) for f in model_names};oracles[Path(__file__).relative_to(R).as_posix()]=sha(Path(__file__))
assert sources['user_source/hdl_source/isp/stylize_v5_96.v']=='637a49d66485bd46b881823d59314a54e76c82055a304b057cc8e11b334e058f'
assert 'localparam GUARD_DISABLED=1' in (H/'isp/stylize_v5_96.v').read_text(encoding='utf-8')
# Vectorised exact colour_luma_preserve reference. Neutral gr/gb return the
# original pixel; the non-neutral scenario checks that constant cel regions
# remain constant and exact weighted luma is retained under that calibration.
def calibrate(rgb,gr=4096,gb=4096):
 c=np.asarray(rgb,dtype=np.int64);pr=(c[...,0]*gr+2048)//4096;pb=(c[...,2]*gb+2048)//4096
 rawr=pr-c[...,0];rawb=pb-c[...,2];dr=(3*rawr-rawb)//4;db=(3*rawb-rawr)//4
 chosen=np.zeros_like(c);found=np.zeros(c.shape[:-1],bool)
 for shift in range(4):
  rr=dr//(1<<shift);bb=db//(1<<shift);odd=(rr&1)!=(bb&1)
  bb=np.where(odd&(bb>0),bb-1,np.where(odd&(bb<0),bb+1,bb));rr=np.where(odd&(bb==0)&(db//(1<<shift)==0),np.where(rr>0,rr-1,rr+1),rr)
  gg=-(rr+bb)//2;d=np.stack([rr,gg,bb],-1);candidate=c+d;valid=np.all((candidate>=0)&(candidate<=255),axis=-1)&~found
  chosen=np.where(valid[...,None],d,chosen);found|=valid
 out=c+chosen;assert np.array_equal(c[...,0]+2*c[...,1]+c[...,2],out[...,0]+2*out[...,1]+out[...,2])
 return out.astype(np.uint8)
def display(im,prior=False,diagnostics=False):
 h,w=im.shape[:2];ht=1650 if w==1280 else w+32;vt=h+30
 rgb=np.zeros((vt,ht,3),np.uint8);rgb[:h,:w]=im;de=np.zeros((vt,ht),bool);de[:h,:w]=True;ov=np.zeros_like(de);control=np.full(vt*ht,40,np.uint8)
 if prior:
  out=prior_finish(rgb.reshape(-1,3),de.ravel(),ov.ravel(),control,h_total=ht,th_dark=32,max_correction=6)
  return out.reshape(vt,ht,3)[:h,:w]
 out,event,details=final_display(rgb.reshape(-1,3),de.ravel(),ov.ravel(),control,h_total=ht,width=w,height=h,diagnostics=True)
 img=out.reshape(vt,ht,3)[:h,:w]
 if diagnostics:return img,{'event_count':int(event.sum()),'dpc_count':int(details['dpc_event'].sum()),'cartoon_count':int(details['cartoon_event'].sum())}
 return img
tests={};inputs={}
# A physically native1280 ramp, not resized photo pixels. All gradual slopes
# reduce to six hard labels and six actual neutral RGB cel levels.
ramp=np.repeat(np.tile(np.arange(256,dtype=np.uint8).repeat(5),(96,1))[...,None],3,-1)
out,f=new.render(ramp,1,gm.guide);out=calibrate(out);final=display(out)
assert np.array_equal(out,calibrate(out));assert np.array_equal(final[:,:,0],final[:,:,1]) and np.array_equal(final[:,:,1],final[:,:,2])
levels=np.unique(final[18:-12,36:-24,0]).tolist();assert levels==[0,51,102,153,204,255],levels
assert np.unique(f['tones']).tolist()==levels
tests['native_six_category_ramp']={'pass':True,'width':1280,'levels':levels,'scope':'actual final integer display model, neutral calibration, no image pre-resize'}
# Known dark blue/brown/skin colours must not be mapped to grey or white.
colours=[]
for name,colour in [('deep_blue',[18,32,70]),('brown',[86,52,29]),('skin',[210,160,130]),('red',[70,18,12]),('green',[18,72,32]),('purple',[62,28,70]),('cyan',[20,65,80])]:
 for factor in [1,0.6,0.35,0.15]:
  c=np.floor(np.asarray(colour)*factor).astype(np.uint8);im=np.empty((48,128,3),np.uint8);im[:]=c;q,f=new.render(im,1,gm.guide)
  rgb=f['rgb'];fill=f['fill'];assert np.all(fill-fill[0,0]==0)
  assert np.all(fill[...,0]-fill[...,1]==rgb[...,0]-rgb[...,1]) and np.all(fill[...,1]-fill[...,2]==rgb[...,1]-rgb[...,2])
  z=display(calibrate(q));sample=z[24,64].astype(int);assert np.ptp(c)==0 or np.ptp(sample)>0,(name,c,sample)
  colours.append({'name':name,'factor':factor,'input':c.tolist(),'final_pixel':sample.tolist()})
tests['dark_colours_and_skin_retained']={'pass':True,'cases':len(colours),'details':colours}
# Gamut limits: original RGB channel differences remain exactly intact before
# bounded ink, including saturated samples and every target endpoint.
rng=np.random.default_rng(117);palette=np.array([0,51,102,153,204,255]);points=np.concatenate([rng.integers(0,256,(100000,3)),np.array([[0,0,0],[255,255,255],[0,0,255],[255,0,0],[0,255,0],[1,2,3],[254,255,253]])],0)
for target in palette:
 q=new.tint(points,np.full(len(points),target));assert np.all((q>=0)&(q<=255));assert np.array_equal(q[:,0]-q[:,1],points[:,0]-points[:,1]);assert np.array_equal(q[:,1]-q[:,2],points[:,1]-points[:,2])
tests['shared_gamut_preserves_rgb_differences']={'pass':True,'samples':len(points)*len(palette),'palette_endpoints':palette.tolist()}
# Non-neutral fixed calibration cannot introduce texture inside a constant
# colour label region and preserves the exact 10bit weighted-luma sum.
q=calibrate(points.reshape(-1,1,3).astype(np.uint8),4608,3584)
assert np.array_equal(points[:,0]+2*points[:,1]+points[:,2],q[:,0,0].astype(int)+2*q[:,0,1].astype(int)+q[:,0,2].astype(int))
tests['fixed_calibration_luma_invariant']={'pass':True,'samples':len(points),'gain_r':4608,'gain_b':3584,'scope':'independent vectorised source-equation model; calibration RTL itself unchanged and tested separately'}
# Native source->style->calibration->FINAL display, then optional thumbnails.
rows=[];native=[];normal_names=['test_photo','board_real_bakery','board_like_cast','board_like_lowcontrast']
for name in normal_names+['video1_21.10s','video1_28.13s']:
 path=R/'validation/supplied_videos'/f'{name}.jpg' if name.startswith('video') else R.parent/'05_stylize_on_v5/sim'/f'{name}.raw'
 im=np.asarray(Image.open(path).convert('RGB')) if name.startswith('video') else np.fromfile(path,np.uint8).reshape(720,1280,3)
 assert im.shape==(720,1280,3);inputs[str(path)]={'sha256':sha(path),'shape':list(im.shape),'scope':'already processed phone-monitor frame, illustration only' if name.startswith('video') else 'full-size RGB input sample'}
 prior,_=old.render(im,1,gm.guide);prior=display(calibrate(prior),prior=True)
 hard,f=new.render(im,1,gm.guide);cal=calibrate(hard);assert np.array_equal(cal,hard);final,events=display(cal,diagnostics=True)
 assert final.shape==(720,1280,3)
 # Final cartoon processing can only choose existing RGB vectors. This would
 # fail if any old RGB averaging filter were accidentally reintroduced.
 keys=(cal[...,0].astype(np.uint32)<<16)|(cal[...,1].astype(np.uint32)<<8)|cal[...,2].astype(np.uint32)
 outkeys=(final[...,0].astype(np.uint32)<<16)|(final[...,1].astype(np.uint32)<<8)|final[...,2].astype(np.uint32)
 seen=np.zeros(1<<24,bool);seen[keys.ravel()]=True;assert np.all(seen[outkeys.ravel()])
 Image.fromarray(final).save(V/(name+'_production_final_native.png'))
 fy=(f['fill'][...,0]+2*f['fill'][...,1]+f['fill'][...,2])//4
 native.append({'name':name,'phone_illustration_only':name.startswith('video'),'shape':list(final.shape),'label_histogram':np.bincount(f['median'].ravel(),minlength=6).tolist(),'exact_palette_fill_fraction':float(np.mean(fy==f['tones'])),'final_modified_pixels':int(np.count_nonzero(np.any(final!=hard,axis=-1))),**events})
 row=Image.new('RGB',(384*3,244),'white');draw=ImageDraw.Draw(row)
 for j,(img,label) in enumerate([(im,'INPUT RGB reference'),(prior,'V10 complete model'),(final,'V11 complete model')]):
  assert img.shape==(720,1280,3);row.paste(Image.fromarray(img).resize((384,216),Image.Resampling.BILINEAR),(j*384,28));draw.text((j*384+8,7),name+' '+label,fill='black')
 rows.append(row)
 if name in ['test_photo','video1_21.10s']:
  box=(300,180,940,500);crop=Image.new('RGB',(1920,348),'white');draw=ImageDraw.Draw(crop)
  for j,(img,label) in enumerate([(im,'INPUT RGB native100%'),(prior,'V10 native100% complete'),(final,'V11 native100% complete')]):crop.paste(Image.fromarray(img).crop(box),(j*640,28));draw.text((j*640+8,7),label,fill='black')
  crop.save(V/(name+'_production_final_100pct.png'))
canvas=Image.new('RGB',(1152,244*len(rows)),'white')
for j,row in enumerate(rows):canvas.paste(row,(0,j*244))
canvas.save(V/'production_native_comparison.png')
tests['native_processing_before_thumbnail']={'pass':True,'normal_rgb_samples':4,'phone_illustrations':2,'input_shapes':[[720,1280,3]]*6,'output_native_shapes':[[720,1280,3]]*6}
tests['cartoon_final_rgb_vector_set_closed']={'pass':True,'native_images':6,'scope':'with actual new display model and {Y,RGB} ties, final RGB set is subset of source-style RGB set; no RGB averaging invented intermediate colours'}
# FULL256 greys, correlated noise and eight frames find classification-cut
# noise rather than selecting flattering levels. These diagnostics are never
# an all-noise-lower PASS assertion. Physical pixel fixtures are NOT resized.
w,h=96,72;roi=(slice(18,-12),slice(36,-24));rng=np.random.default_rng(20261101);noise=[]
for level in range(256):
 for block in [1,3,4]:
  samples={k:[] for k in ['v10','v11_before_cleanup','v11_final']}
  for frame in range(8):
   ns=((h+block-1)//block,(w+block-1)//block,3);n=rng.integers(-12,13,ns);n=np.repeat(np.repeat(n,block,0),block,1)[:h,:w];im=np.clip(level+n,0,255).astype(np.uint8)
   a,_=old.render(im,1,gm.guide);z,_=new.render(im,1,gm.guide)
   for key,q in [('v10',display(calibrate(a),prior=True)),('v11_before_cleanup',z),('v11_final',display(calibrate(z)))]:samples[key].append(q[roi].astype(float))
  std={key:float(np.asarray(values).std(0).mean()) for key,values in samples.items()};noise.append({'gray':level,'block':block,**std})
 if level%32==31:print('V11_FINAL_QUALITY_GREY',level,flush=True)
noise_summary={'cases':len(noise),'mean_v10_std':float(np.mean([a['v10'] for a in noise])),'mean_v11_raw_std':float(np.mean([a['v11_before_cleanup'] for a in noise])),'mean_v11_final_std':float(np.mean([a['v11_final'] for a in noise])),'cleanup_improved_or_equal':sum(a['v11_final']<=a['v11_before_cleanup'] for a in noise),'worst_final_std':max(noise,key=lambda a:a['v11_final']),'worst_extra_vs_v10':max(noise,key=lambda a:a['v11_final']-a['v10']),'worst_extra_cleanup':max(noise,key=lambda a:a['v11_final']-a['v11_before_cleanup'])}
# Actual MODEL_ONLY probes are retained separately, never passed off as this
# production evidence. Root independently verifies whole display RTL/native RAM.
assert sources=={p:sha(R/p) for p in sources},'Production source changed during quality run'
assert oracles=={p:sha(R/p) for p in oracles},'Quality oracle changed during quality run'
result={'tests':tests,'source_sha256':sources,'oracle_sha256':oracles,'input_files':inputs,'native_metrics':native,'noise_summary':noise_summary,'noise_details':noise,'seconds':round(time.time()-start,2),'scope':'Selected HARD6 cartoon style plus actual new display_v11_model including enabled vector cleanup and {Y,RGB} ties; neutral calibration reference explicitly applied. Full1280x720 before display thumbnail. Separate96x72 physicalpixel all-grey/noise fixtures are not resized natural images. Does not model sensor, DDR, monitor, phone, actual learned AWB or prove all visual/noise conditions improve.'}
(V/'quality_result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('CARTOON_V11_FINAL_QUALITY_DONE',result['seconds'],flush=True);print(json.dumps(noise_summary,indent=2),flush=True)
