from pathlib import Path
import hashlib,json,subprocess,sys,time
import numpy as np
from PIL import Image
import model_baseline as b
import model_visual_v6 as model
from test_denoise import fixture
sys.stdout.reconfigure(encoding='utf-8')
R=Path(__file__).resolve().parents[1];V=R/'validation';H=R/'user_source/hdl_source';IV=Path(r'D:\anlu\iverilog\bin\iverilog.exe')
results={}
def run(name,cmd,timeout=240):
 p=subprocess.run(list(map(str,cmd)),cwd=V,capture_output=True,text=True,timeout=timeout)
 log=p.stdout+p.stderr;(V/(name+'.log')).write_text(log,encoding='utf-8');assert p.returncode==0,(name,log[-1400:]);return log
for w,h,frames,modes in [(160,90,45,[0,1,2]),(1280,96,3,[0,1,2])]:
 b.set_size(w,h);img=fixture(w,h);b.save_hex(img,V/'img_in.hex');B,Y,M=b.core(img)
 run('visual_compile',[IV,'-g2012','-s','tb_stylize_v5_96','-P',f'tb_stylize_v5_96.W={w}','-P',f'tb_stylize_v5_96.H={h}',
 '-o','visual.vvp','tb_stylize_v5_96.v',H/'isp/stylize_v5_96.v'])
 for mode in modes:
  name=f'visual_{w}_{mode}';start=time.time()
  log=run(name,[IV.with_name('vvp.exe'),'visual.vvp',f'+mode={mode}',f'+frames={frames}','+gap=1','+lead=52',f'+out={name}.hex'])
  assert 'TB_PASS' in log and 'ERROR:' not in log
  actual=b.load_hex(V/(name+'.hex'));assert len(actual)==frames;p=dict(b.P0)
  for f in range(frames):
   expected=model.render(B,Y,M,mode,p,img)
   if not np.array_equal(actual[f],expected):
    yy,xx=np.nonzero(np.any(actual[f]!=expected,axis=-1));y,x=int(yy[0]),int(xx[0])
    raise AssertionError((name,f,len(yy),(y,x),actual[f,y,x].tolist(),expected[y,x].tolist(),p))
   p=model.update(p,B,Y,M)
  results[name]={'pass':True,'pixels':w*h*frames,'seconds':round(time.time()-start,2)}
  preview=V/'model_predictions';preview.mkdir(exist_ok=True);Image.fromarray(actual[-1]).save(preview/(name+'.png'))
  print('VISUAL_MODEL_MATCH',name,results[name],flush=True)
(V/'visual_verification_result.json').write_text(json.dumps({'tests':results,'source_sha256':{p.relative_to(R).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (R/'user_source').rglob('*') if p.is_file()}},indent=2),encoding='utf-8')
print('VISUAL_V6_VERIFICATION_PASS',flush=True)
