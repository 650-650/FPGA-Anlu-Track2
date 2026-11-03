from pathlib import Path
import hashlib,json,subprocess,time,sys
import numpy as np
from denoise_v8_model import filter_rgb
sys.stdout.reconfigure(encoding='utf-8')
R=Path(__file__).resolve().parents[1];V=R/'validation/denoise_v8';V.mkdir(exist_ok=True);H=R/'user_source/hdl_source';IV=Path(r'D:\anlu\iverilog\bin\iverilog.exe')
MS=Path(r'D:\anlu\altera\14.1S\modelsim_ase\win32aloem');L=Path(r'D:\anlu\TD_6.2.1_Engineer_6.2.168.116\sim_release\ph1p');tests={};start=time.time()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def fixture(w,h,ht,vt):
 rng=np.random.default_rng(2800+w);y,x=np.mgrid[:vt,:ht];de=(y<h)&(x<w);hs=(x>=w+ht//8)&(x<w+ht//8+max(2,ht//40));vs=y>=h+2
 ctrl=np.array([0,0x20,0x28,0x30,0x38,0x50,0x58,0x60],np.uint8)[np.minimum(y*8//vt,7)]
 noise=rng.normal(0,8,((vt+3)//4,(ht+3)//4,1));noise=np.repeat(np.repeat(noise,4,0),4,1)[:vt,:ht]
 noise=noise+rng.normal(0,2,(vt,ht,3));base=np.array([48,42,32])+((x//32)%3)[...,None]*24
 rgb=np.clip(base+noise,0,255).round().astype(np.uint8)
 rgb[(x==w//3)&de]=[120,160,220];rgb[(y==h//3)&de]=[220,140,100]
 overlay=de&(((x>=20)&(x<60)&(y>=12)&(y<35))|((y%90<5)&(x%50<8)))
 rgb[overlay]=[255,40,10]
 return rgb.reshape(-1,3),de.ravel(),overlay.ravel(),ctrl.ravel(),hs.ravel(),vs.ravel()
def write_case(d,data,ht,n=None):
 d.mkdir(exist_ok=True);rgb,de,over,ctrl,hs,vs=data
 if n is not None:rgb,de,over,ctrl,hs,vs=[a[:n] for a in data]
 out=filter_rgb(rgb,de,over,ctrl,ht)
 pixel=(rgb[:,0].astype(np.uint64)<<16)|(rgb[:,1].astype(np.uint64)<<8)|rgb[:,2]
 head=(ctrl.astype(np.uint64)<<28)|(over.astype(np.uint64)<<27)|(de.astype(np.uint64)<<26)|(hs.astype(np.uint64)<<25)|(vs.astype(np.uint64)<<24)
 packed=head|pixel;expected=head|(out[:,0].astype(np.uint64)<<16)|(out[:,1].astype(np.uint64)<<8)|out[:,2]
 (d/'input.hex').write_text(''.join(f'{a:09x}\n' for a in packed),encoding='ascii');(d/'expected.hex').write_text(''.join(f'{a:09x}\n' for a in expected),encoding='ascii')
 # A centre overlay or recognition/status/sketch/edge page is exactly bypassed.
 bypass=over|(ctrl>>5>=2)|(((ctrl>>5)==1)&((ctrl&0x10)!=0))
 assert np.array_equal(out[bypass],rgb[bypass])
 return len(packed)
def run(name,cmd,d,timeout=300):
 p=subprocess.run(list(map(str,cmd)),cwd=d,capture_output=True,text=True,timeout=timeout);log=p.stdout+p.stderr
 (d/(name+'.log')).write_text(log,encoding='utf-8');assert p.returncode==0 and '** Error' not in log and '** Fatal' not in log,(name,log[-2200:]);return log
for name,w,h,ht,vt in [('small',96,64,128,80),('full',1280,720,1650,750)]:
 d=V/name;data=fixture(w,h,ht,vt);n=write_case(d,data,ht)
 run('compile',[IV,'-g2012','-s','denoise_v8_tb','-P',f'denoise_v8_tb.N={n}','-P',f'denoise_v8_tb.HT={ht}','-o',d/'test.vvp',R/'validation/denoise_v8_tb.v',H/'display_denoise_v8.v'],d)
 log=run('run',[IV.with_name('vvp.exe'),d/'test.vvp'],d);assert 'DENOISE_V8_PASS' in log;print(name,log[-600:],flush=True)
 tests[name]={'pass':True,'clocks':n,'frame_width':w,'frame_height':h,'h_total':ht,'log':str((d/'run.log').relative_to(R))}
 if name=='full':production_data=data
d=V/'native';n=write_case(d,production_data,1650,110000)
for name,cmd in [('vmap_init',[MS/'vmap.exe','-c']),('vlib',[MS/'vlib.exe','work']),('vmap',[MS/'vmap.exe','work','work']),
 ('vlog',[MS/'vlog.exe','-sv','-work','work',L/'ph1p_phy_gsr.v',L/'ph1p_logic_eram.v',R/'validation/denoise_v8_tb.v',H/'display_denoise_v8.v']),
 ('vsim',[MS/'vsim.exe','-c','-do',f'vsim -gN={n} -gHT=1650 work.PH1P_PHY_GSR work.denoise_v8_tb; onfinish stop; run -all; quit -f'])]:
 log=run(name,cmd,d)
 if name=='vsim':assert 'DENOISE_V8_PASS' in log;print(log[-1200:],flush=True)
tests['native_production_ram']={'pass':True,'clocks':n,'native_vendor_model':True,'h_total':1650,'depth':6600,'log':str((d/'vsim.log').relative_to(R))}
result={'tests':tests,'source_sha256':{p.relative_to(R).as_posix():sha(p) for p in [H/'display_denoise_v8.v']},
 'oracle_sha256':{p.relative_to(R).as_posix():sha(p) for p in [R/'tools/denoise_v8_model.py',R/'tools/denoise_v8_verify.py',R/'validation/denoise_v8_tb.v']},'native_vendor_model':True,'seconds':round(time.time()-start,2)}
(V/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('DENOISE_V8_ALL_PASS',flush=True)
