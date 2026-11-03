from pathlib import Path
import hashlib,json,subprocess,sys,time
import numpy as np
from display_v9_model import filter_rgb
sys.stdout.reconfigure(encoding='utf-8')
R=Path(__file__).resolve().parents[1];V=R/'validation/display_v9';V.mkdir(exist_ok=True);H=R/'user_source/hdl_source'
IV=Path(r'D:/anlu/iverilog/bin/iverilog.exe');MS=Path(r'D:/anlu/altera/14.1S/modelsim_ase/win32aloem')
L=Path(r'D:/anlu/TD_6.2.1_Engineer_6.2.168.116/sim_release/ph1p');start=time.time();tests={}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def fixture(w,h,ht,vt,frames):
 rng=np.random.default_rng(20261030+w);y,x=np.indices((vt*frames,ht));fy=y%vt;frame=y//vt
 de=(fy<h)&(x<w);hs=(x>=w+ht//8)&(x<w+ht//8+max(2,ht//40));vs=(fy>=h+2)&(fy<h+5)
 modes=np.array([0,0x20,0x28,0x30,0x38,0x40,0x48,0x50,0x58,0x60,0x80,0xe0],np.uint8)
 control=modes[np.minimum((fy*len(modes))//max(h,1),len(modes)-1)]
 control=np.broadcast_to(control,y.shape).copy();control|=((x//71+fy//13)%8).astype(np.uint8)
 block=rng.normal(0,8,((vt*frames+3)//4,(ht+3)//4,1))
 noise=np.repeat(np.repeat(block,4,axis=0),4,axis=1)[:vt*frames,:ht]+rng.normal(0,2,(*y.shape,3))
 base=np.array([64,60,52])+((x>=w//2+4*frame)[...,None])*32
 rgb=np.clip(base+noise+np.sin(x[...,None]*2*np.pi/8)*4,0,255).round().astype(np.uint8)
 # Different frames, moving/diagonal/horizontal detail and repeated frame cuts.
 rgb[(x==w//3+frame*3)&de]=[112,132,152]
 rgb[(x-fy==w//4+frame*2)&de]=[100,116,132]
 rgb[(fy==h//3)&de]=[180,160,140]
 if frames>1:rgb[(frame%2==1)&de]=255-rgb[(frame%2==1)&de]
 over=de&(((x>=w//5)&(x<w//5+11)&(fy>=h//8)&(fy<h//8+7))|((fy%37<2)&(x%43<3)))
 rgb[over]=[255,40,10]
 return tuple(a.reshape(-1,3) if a is rgb else a.ravel() for a in [rgb,de,over,control,hs,vs])
def write_case(d,data,ht):
 d.mkdir(exist_ok=True);rgb,de,over,ctrl,hs,vs=data;out=filter_rgb(rgb,de,over,ctrl,ht)
 pixel=(rgb[:,0].astype(np.uint64)<<16)|(rgb[:,1].astype(np.uint64)<<8)|rgb[:,2]
 head=(ctrl.astype(np.uint64)<<28)|(over.astype(np.uint64)<<27)|(de.astype(np.uint64)<<26)|(hs.astype(np.uint64)<<25)|(vs.astype(np.uint64)<<24)
 packed=head|pixel;expected=head|(out[:,0].astype(np.uint64)<<16)|(out[:,1].astype(np.uint64)<<8)|out[:,2]
 for name,values in [('input.hex',packed),('expected.hex',expected)]:
  (d/name).write_text(''.join(f'{int(a):09x}\n' for a in values),encoding='ascii')
 protected=over|((ctrl>>5)>=2)|(((ctrl>>5)==1)&((ctrl&0x18)!=0))
 assert np.array_equal(out[protected],rgb[protected])
 delta=np.abs(out.astype(np.int16)-rgb.astype(np.int16));assert delta.max()<=6
 return len(rgb),int(protected.sum()),int(np.any(delta,axis=1)[de].sum())
def run(name,cmd,d,timeout=600):
 p=subprocess.run(list(map(str,cmd)),cwd=d,capture_output=True,text=True,timeout=timeout);log=p.stdout+p.stderr
 (d/(name+'.log')).write_text(log,encoding='utf-8')
 assert p.returncode==0 and '** Error' not in log and '** Fatal' not in log,(name,log[-3000:]);return log
for name,w,h,ht,vt,frames in [('small',96,64,128,80,4),('full',1280,720,1650,750,1)]:
 d=V/name;data=fixture(w,h,ht,vt,frames);n,bypass,changed=write_case(d,data,ht)
 run('compile',[IV,'-g2012','-s','display_v9_tb','-P',f'display_v9_tb.N={n}','-P',f'display_v9_tb.HT={ht}','-o',d/'test.vvp',R/'validation/display_v9_tb.v',H/'display_denoise_v9.v'],d)
 log=run('run',[IV.with_name('vvp.exe'),d/'test.vvp'],d);assert 'DISPLAY_V9_PASS' in log;print(name,log[-450:],flush=True)
 tests[name]={'pass':True,'packets':n,'active':int(data[1].sum()),'exact_protected_packets':bypass,'changed_active':changed,'h_total':ht,'width':w,'height':h,'frames':frames,'sample_edge_lag':ht+5,'registered_stages':ht+6,'log':str((d/'run.log').relative_to(R))}
 if name=='full':full_data=data
d=V/'native';n,bypass,changed=write_case(d,full_data,1650)
for name,cmd in [('vmap_init',[MS/'vmap.exe','-c']),('vlib',[MS/'vlib.exe','work']),('vmap',[MS/'vmap.exe','work','work']),
 ('vlog',[MS/'vlog.exe','-sv','-work','work',L/'ph1p_phy_gsr.v',L/'ph1p_logic_eram.v',R/'validation/display_v9_tb.v',H/'display_denoise_v9.v']),
 ('vsim',[MS/'vsim.exe','-c','-do',f'vsim -gN={n} -gHT=1650 work.PH1P_PHY_GSR work.display_v9_tb; onfinish stop; run -all; quit -f'])]:
 log=run(name,cmd,d)
 if name=='vsim':assert 'DISPLAY_V9_PASS' in log;print(log[-650:],flush=True)
tests['native_production_ram']={'pass':True,'packets':n,'h_total':1650,'width':1280,'height':720,'sample_edge_lag':1655,'registered_stages':1656,'native_vendor_model':True,'log':str((d/'vsim.log').relative_to(R))}
result={'tests':tests,'source_sha256':{p.relative_to(R).as_posix():sha(p) for p in [H/'display_denoise_v9.v']},
 'oracle_sha256':{p.relative_to(R).as_posix():sha(p) for p in [R/'tools/display_v9_model.py',Path(__file__),R/'validation/display_v9_tb.v']},
 'production_sample_edge_lag':1655,'sample_edge_lag':1655,'registered_stages':1656,'native_vendor_model':True,'seconds':round(time.time()-start,2),
 'scope':'Whole 36-bit packets, startup, actual blanking, all control groups, mode changes, overlays, frame cuts/moving detail in small fixture; full 1280x720 stream in Icarus and native ERAM. Not camera/DDR/board validation.'}
(V/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('DISPLAY_V9_ALL_PASS',flush=True)
