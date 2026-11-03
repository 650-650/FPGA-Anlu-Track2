"""Full native1280x720 processing BEFORE display-only preview resize.

Neutral gains4096/4096 and trim0 make real color_luma_preserve exact identity;
cartoon display_contrast is exact bypass. Candidate finishes are either the
old real integer STRIDE4 filter or proposed exact packet delay (no RGB mix).
Monitor-phone frames are illustrative inputs, not raw sensor ground truth.
"""
from pathlib import Path
import json,hashlib,time
import numpy as np
from PIL import Image,ImageDraw
import cartoon_v10_model as old,cartoon_v11_model as new,guide_v8_model as gm
from denoise_v8_model import filter_rgb
R=Path(__file__).resolve().parents[1];V=R/'validation/cartoon_v11';V.mkdir(parents=True,exist_ok=True);start=time.time()
def finish(im):
 h,w=im.shape[:2];ht=1650;vt=h+30;a=np.zeros((vt,ht,3),np.uint8);a[:h,:w]=im;de=np.zeros((vt,ht),bool);de[:h,:w]=True;ov=np.zeros_like(de);ctrl=np.full(de.size,40,np.uint8)
 return filter_rgb(a.reshape(-1,3),de.ravel(),ov.ravel(),ctrl,h_total=ht,th_dark=32,max_correction=6).reshape(vt,ht,3)[:h,:w]
inputs=[]
for name in ['test_photo','board_real_bakery','board_like_cast','board_like_lowcontrast']:
 im=np.fromfile(R.parent/'05_stylize_on_v5/sim'/f'{name}.raw',np.uint8).reshape(720,1280,3);inputs.append((name,im,'old full-native RGB sample'))
for name in ['video1_21.10s','video1_28.13s']:
 im=np.asarray(Image.open(R/'validation/supplied_videos'/f'{name}.jpg').convert('RGB'));assert im.shape==(720,1280,3);inputs.append((name,im,'phone monitor frame, illustration only'))
rows=[];metrics=[]
for name,im,source in inputs:
 assert im.shape==(720,1280,3);a,fa=old.render(im,1,gm.guide);a=finish(a)
 variants=[('input',im),('v10_actualfinish',a)]
 for label,levels,cs in [('six_chroma0',6,0),('six_chroma8',6,8),('six_chroma16',6,16),('eight_chroma16',8,16)]:
  q,f=new.render(im,1,gm.guide,levels=levels,chroma_step=cs)
  variants.append((label,q));Image.fromarray(q).save(V/(name+'_'+label+'_native.png'))
  roi=(slice(12,-12),slice(24,-24));fill=f['fill'];flat=float(np.all(np.diff(fill,axis=1)==0,axis=-1).mean());tone_count=len(np.unique(f['tones']))
  metrics.append({'name':name,'source':source,'candidate':label,'native_shape':list(im.shape),'label_tones':tone_count,'flat_rgb_horizontal':flat,'distinct_fill_colours':len(np.unique(fill[roi].reshape(-1,3),axis=0)),'median_changes':int(np.count_nonzero(f['labels']!=f['median']))})
  if label=='six_chroma16':
   filtered=finish(q);Image.fromarray(filtered).save(V/(name+'_six_chroma16_oldfinish_native.png'))
   metrics[-1]['old_finish_changed_pixels']=int(np.count_nonzero(np.any(filtered!=q,axis=-1)))
   # 100% pixels, no resize, actual crop of each already full-native result.
   boxes=[('center',(440,190,1080,510))] if name=='test_photo' else [('center',(300,160,940,480))]
   for suffix,box in boxes:
    ims=[Image.fromarray(z).crop(box) for z in [im,a,q,filtered]];c=Image.new('RGB',(640*4,348),'white');d=ImageDraw.Draw(c)
    for j,(z,title) in enumerate(zip(ims,['INPUT native crop','V10 whole chain','V11 6/chroma16 exact finish','V11 palette + OLD RGB finish'])):c.paste(z,(640*j,28));d.text((640*j+8,7),title,fill='black')
    c.save(V/(name+'_'+suffix+'_100pct.png'))
  print('PREVIEW_NATIVE',name,label,flush=True)
 # Resize only the FINAL already processed images for the contact sheet.
 thumbs=[Image.fromarray(z).resize((384,216),Image.Resampling.BILINEAR) for _,z in variants]
 row=Image.new('RGB',(384*len(thumbs),244),'white');d=ImageDraw.Draw(row)
 for j,((label,_),z) in enumerate(zip(variants,thumbs)):row.paste(z,(j*384,28));d.text((j*384+6,7),name+' '+label,fill='black')
 rows.append(row)
canvas=Image.new('RGB',(rows[0].width,sum(a.height for a in rows)),'white');y=0
for row in rows:canvas.paste(row,(0,y));y+=row.height
canvas.save(V/'native_model_candidates.png')
res={'scope':'Native1280x720 style processing before preview resize; neutral color calibration gains4096/4096 trim0 is identity; cartoon tone table bypass. V10 includes real oldfinish32/6; V11 displayed candidates use proposed exact4clock packet finish, with oldfinish separately shown. Phone frames already include screen/camera effects and are illustration only.','metrics':metrics,'model_sha256':hashlib.sha256((R/'tools/cartoon_v11_model.py').read_bytes()).hexdigest(),'seconds':round(time.time()-start,2)}
(V/'native_preview_metrics.json').write_text(json.dumps(res,indent=2),encoding='utf-8');print('NATIVE_PREVIEW_DONE',res['seconds'],flush=True)
