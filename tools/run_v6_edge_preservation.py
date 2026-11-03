from pathlib import Path
import hashlib,json,subprocess,sys,time
import numpy as np
from PIL import Image
sys.stdout.reconfigure(encoding='utf-8')
R=Path(__file__).resolve().parents[1];V=R/'validation';H=R/'user_source/hdl_source';IV=Path(r'D:\anlu\iverilog\bin\iverilog.exe');tests={}
def run(name,files):
 start=time.time();binary=V/(name+'.vvp')
 for stage,cmd in [('compile',[IV,'-g2012','-s',name,'-o',binary,V/(name+'.v')]+files),('run',[IV.with_name('vvp.exe'),binary])]:
  p=subprocess.run(list(map(str,cmd)),cwd=V,capture_output=True,text=True,timeout=240)
  log=p.stdout+p.stderr;(V/(name+'_'+stage+'.log')).write_text(log,encoding='utf-8');assert p.returncode==0,(name,log[-1600:])
  if stage=='run':assert 'PASS' in log;print(log[-800:],flush=True)
 tests[name]={'pass':True,'seconds':round(time.time()-start,2)}
w,h=1280,96;y,x=np.mgrid[:h,:w];a=(80+(x//320)*20).astype(int)
# Identical weak, one-pixel and strong contours at both halves, plus low noise.
for c in [80,160,400,720,800,1040]:a[:,c:c+2]+=8
a[32:64,240:560]+=24;a[32:64,880:1200]+=24
a+=np.random.default_rng(23).integers(-1,2,a.shape);img=np.repeat(np.clip(a,0,255)[...,None],3,-1).astype(np.uint8)
with (V/'edge_input.hex').open('w') as f:
 for beat in img.reshape(-1,12):f.write(beat.tobytes().hex()+'\n')
run('edge_visual_v6_tb',[H/'isp/edge_detect_96.v'])
actual=np.frombuffer(bytes.fromhex(''.join((V/'edge_actual.hex').read_text().split())),np.uint8).reshape(8,h,w,3)
g=(img[...,0].astype(int)+2*img[...,1].astype(int)+img[...,2].astype(int))>>2
z=[g[dy:dy+h-2,dx:dx+w-2] for dy in range(3) for dx in range(3)]
rr=[z[2]-z[0],z[5]-z[3],z[8]-z[6]];cc=[z[6]-z[0],z[7]-z[1],z[8]-z[2]]
mag=np.abs(rr[0]+2*rr[1]+rr[2])+np.abs(cc[0]+2*cc[1]+cc[2])
coherent=np.all(np.stack(rr)>=2,axis=0)|np.all(np.stack(rr)<=-2,axis=0)|np.all(np.stack(cc)>=2,axis=0)|np.all(np.stack(cc)<=-2,axis=0)
th=40;thresholds=[]
for f in range(8):
 high=np.where(z[4]<64,th//2+8,np.where(z[4]<160,th-th//4,th));low=np.maximum(high//2,10)
 edge=(mag>=2*high)|(coherent&(mag>=low));expected=np.zeros((h,w),np.uint8);expected[2:,2:]=edge*255;expected[:,:4]=0
 assert np.array_equal(actual[f],np.repeat(expected[...,None],3,-1)),('edge oracle mismatch',f,int(np.any(actual[f]!=expected[...,None],axis=-1).sum()))
 thresholds.append(th);count=(h-2)*(w//4-1);n=np.count_nonzero(expected[2:,4::4]);th=th-2 if n<count//32 and th>28 else th+2 if n>count//8 and th<80 else th
weak_left=int(np.count_nonzero(actual[-1,4:28,76:86,0]));weak_right=int(np.count_nonzero(actual[-1,4:28,716:726,0]))
assert weak_left>0 and weak_right>0 and abs(weak_left-weak_right)<=8
Image.fromarray(actual[-1]).save(V/'model_predictions/verified_full_resolution_edge.png')
tests['edge_visual_v6_tb'].update(pixels=8*w*h,thresholds=thresholds,weak_left_pixels=weak_left,weak_right_pixels=weak_right)
run('style_v5_preservation_tb',[V/'style_v5_reference.v',H/'isp/stylize_v5_96.v'])
tests['style_v5_preservation_tb']['pixels']=6*1280*48
(V/'edge_preservation_result.json').write_text(json.dumps({'tests':tests,'source_sha256':{p.relative_to(R).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (R/'user_source').rglob('*') if p.is_file()}},indent=2),encoding='utf-8')
print('EDGE_AND_V5_PRESERVATION_PASS',flush=True)
