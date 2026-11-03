"""Check production cartoon-only finishing filter against original integer oracle."""
from pathlib import Path
import hashlib,json,subprocess,sys,time
import numpy as np
from denoise_v8_model import filter_rgb
sys.stdout.reconfigure(encoding='utf-8')
R=Path(__file__).resolve().parents[1];H=R/'user_source/hdl_source';V=R/'validation/cartoon_finish_v9';V.mkdir(exist_ok=True)
IV=Path(r'D:\anlu\iverilog\bin\iverilog.exe');MS=Path(r'D:\anlu\altera\14.1S\modelsim_ase\win32aloem');L=Path(r'D:\anlu\TD_6.2.1_Engineer_6.2.168.116\sim_release\ph1p')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
tb=(R/'validation/denoise_v8_tb.v').read_text(encoding='utf-8').replace('denoise_v8_tb','cartoon_finish_v9_tb').replace('display_denoise_v8','display_cartoon_finish_v9')
tb=tb.replace('input_data[j][35:33]>=2 || input_data[j][27] || (input_data[j][35:33]==1 && input_data[j][32])','input_data[j][35:33]!=1 || input_data[j][32:31]!=1 || input_data[j][27]')
tb=tb.replace('DENOISE_V8_PASS','CARTOON_FINISH_V9_PASS');(V/'testbench.v').write_text(tb,encoding='utf-8')
def run(name,cmd,d):
 p=subprocess.run(list(map(str,cmd)),cwd=d,capture_output=True,text=True,timeout=300);log=p.stdout+p.stderr;(d/(name+'.log')).write_text(log,encoding='utf-8')
 assert p.returncode==0 and '** Error' not in log and '** Fatal' not in log,(name,log[-2500:]);return log
tests={};start=time.time()
for label,ht,vt,w,h in [('small',128,160,96,140),('full',1650,750,1280,720)]:
 d=V/label;d.mkdir(exist_ok=True);rng=np.random.default_rng(20261030+ht);y,x=np.indices((vt,ht));de=(y<h)&(x<w)
 modes=np.array([0,0x20,0x28,0x30,0x38,0x50,0x58,0x60],np.uint8);ctl=modes[np.minimum(y*8//vt,7)]
 noise=rng.normal(0,6,((vt+3)//4,(ht+3)//4,3));noise=np.repeat(np.repeat(noise,4,0),4,1)[:vt,:ht]
 rgb=np.clip(60+(x//31)[...,None]%4*30+noise,0,255).round().astype(np.uint8)
 rgb[(x==w//2)&de]=[48,96,128];over=de&((y%83)<5)&((x%37)<9);rgb[over]=[255,40,10]
 hs=(x>=w+8)&(x<w+12);vs=y>=h+2
 out=filter_rgb(rgb.reshape(-1,3),de.ravel(),over.ravel(),ctl.ravel(),ht,4,32,16,6).reshape(vt,ht,3)
 selected=(ctl>>5==1)&((ctl&0x18)==8);out=np.where(selected[...,None],out,rgb)
 head=(ctl.astype(np.uint64)<<28)|(over.astype(np.uint64)<<27)|(de.astype(np.uint64)<<26)|(hs.astype(np.uint64)<<25)|(vs.astype(np.uint64)<<24)
 def pack(a):return head|(a[:,:,0].astype(np.uint64)<<16)|(a[:,:,1].astype(np.uint64)<<8)|a[:,:,2]
 for filename,a in [('input.hex',pack(rgb)),('expected.hex',pack(out))]:(d/filename).write_text(''.join(f'{int(p):09x}\n' for p in a.ravel()),encoding='ascii')
 n=vt*ht;run('compile',[IV,'-g2012','-s','cartoon_finish_v9_tb','-P',f'cartoon_finish_v9_tb.N={n}','-P',f'cartoon_finish_v9_tb.HT={ht}','-o',d/'test.vvp',V/'testbench.v',H/'display_cartoon_finish_v9.v'],d)
 log=run('run',[IV.with_name('vvp.exe'),d/'test.vvp'],d);assert 'CARTOON_FINISH_V9_PASS' in log;print(label,log[-420:],flush=True)
 tests[label]={'pass':True,'clocks':n,'h_total':ht,'scope':'only cartoon RGB filtering; all other pages exact; complete metadata4'}
 if label=='full':full=d
native=V/'native';native.mkdir(exist_ok=True)
for name in ['input.hex','expected.hex']:(native/name).write_bytes((full/name).read_bytes())
for name,cmd in [('vmap_init',[MS/'vmap.exe','-c']),('vlib',[MS/'vlib.exe','work']),('vmap',[MS/'vmap.exe','work','work']),
 ('vlog',[MS/'vlog.exe','-sv','-work','work',L/'ph1p_phy_gsr.v',L/'ph1p_logic_eram.v',V/'testbench.v',H/'display_cartoon_finish_v9.v']),
 ('vsim',[MS/'vsim.exe','-c','-do',f'vsim -gN={n} -gHT=1650 work.PH1P_PHY_GSR work.cartoon_finish_v9_tb; onfinish stop; run -all; quit -f'])]:
 log=run(name,cmd,native)
 if name=='vsim':assert 'CARTOON_FINISH_V9_PASS' in log
tests['native']={'pass':True,'clocks':n,'native_vendor_model':True}
result={'tests':tests,'source_sha256':{(H/'display_cartoon_finish_v9.v').relative_to(R).as_posix():sha(H/'display_cartoon_finish_v9.v')},
 'oracle_sha256':{p.relative_to(R).as_posix():sha(p) for p in [Path(__file__),R/'tools/denoise_v8_model.py',V/'testbench.v']},'native_vendor_model':True,'seconds':round(time.time()-start,2)}
(V/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('CARTOON_FINISH_V9_VERIFICATION_PASS',flush=True)
