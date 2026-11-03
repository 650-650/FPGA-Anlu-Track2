from pathlib import Path
import hashlib,json,subprocess,sys,time
import numpy as np
from display_v11_model import filter_rgb
sys.stdout.reconfigure(encoding='utf-8')
R=Path(__file__).resolve().parents[1];V=R/'validation/display_v11';V.mkdir(exist_ok=True);H=R/'user_source/hdl_source'
IV=Path(r'D:/anlu/iverilog/bin/iverilog.exe');MS=Path(r'D:/anlu/altera/14.1S/modelsim_ase/win32aloem')
L=Path(r'D:/anlu/TD_6.2.1_Engineer_6.2.168.116/sim_release/ph1p');start=time.time();tests={}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def fixture(w,h,ht,vt,frames,roi,uniform=False):
 rng=np.random.default_rng(20261104+w);y,x=np.indices((vt*frames,ht));fy=y%vt;frame=y//vt
 de=(fy<h)&(x<w);hs=(x>=w+8)&(x<w+12);vs=(fy>=h+2)&(fy<h+5)
 modes=np.array([0,0x20,0x28,0x30,0x38,0x40,0x48,0x50,0x58,0x60,0x80,0xe0],np.uint8)
 control=(modes[frame%len(modes)] if frames>1 else np.zeros(y.shape,np.uint8))|((x//17+fy//11)%8).astype(np.uint8)
 if uniform:rgb=np.full((*y.shape,3),64,np.uint8)
 else:
  block=rng.normal(0,3,((vt*frames+3)//4,(ht+3)//4,1));noise=np.repeat(np.repeat(block,4,0),4,1)[:vt*frames,:ht]
  rgb=np.clip(np.array([64,60,52])+noise+rng.normal(0,1,(*y.shape,3)),0,255).round().astype(np.uint8)
  x0,x1,y0,y1=roi
  # Identical defect fixtures occur in every page in small frames. Full-width
  # test exercises true production ROI and a retained 5x5 counterexample.
  if w<1280:placements=[(x0+5,y0+5,2,4),(x1-6,y1-6,4,4)]
  else:placements=[(676,148,1,1),(688,148,2,4),(706,155,4,4),(694,168,5,5)]
  for xx,yy,dh,dw in placements:rgb[(x>=xx)&(x<xx+dw)&(fy>=yy)&(fy<yy+dh)]=[255,255,0]
  # Real long coloured strokes are protected by the opposite-tap rule.
  line=(fy==max(5,y0-5))&(x>=12)&(x<w-8);rgb[line]=[255,255,255]
  rgb[(x-fy==w//4)&de]=[224,180,40]
  rgb[(x==w//3)&(fy==h//3)]=[192,192,192]
 overlay=de&(((x>=w//5)&(x<w//5+9)&(fy>=h//8)&(fy<h//8+5))|((fy%47<2)&(x%53<3)))
 rgb[overlay]=[255,40,10]
 return tuple(a.reshape(-1,3) if a is rgb else a.ravel() for a in [rgb,de,overlay,control,hs,vs])
def write_case(d,data,ht,w,h,roi):
 d.mkdir(exist_ok=True);rgb,de,over,ctrl,hs,vs=data
 out,event,details=filter_rgb(rgb,de,over,ctrl,ht,w,h,vs,roi,True)
 pixel=(rgb[:,0].astype(np.uint64)<<16)|(rgb[:,1].astype(np.uint64)<<8)|rgb[:,2]
 head=(ctrl.astype(np.uint64)<<28)|(over.astype(np.uint64)<<27)|(de.astype(np.uint64)<<26)|(hs.astype(np.uint64)<<25)|(vs.astype(np.uint64)<<24)
 expected=head|(out[:,0].astype(np.uint64)<<16)|(out[:,1].astype(np.uint64)<<8)|out[:,2]
 for name,a in [('input.hex',head|pixel),('expected.hex',expected)]:
  (d/name).write_text(''.join(f'{int(p):09x}\n' for p in a),encoding='ascii')
 protected=over|(((ctrl>>5)==1)&((ctrl&0x10)!=0))
 assert np.array_equal(out[protected],rgb[protected]) and not event[protected].any()
 assert np.array_equal(out[~event],details['baseline'][~event])
 cartoon=(ctrl>>5==1)&((ctrl&0x18)==8)
 def rgb_keys(a):return (a[:,0].astype(np.uint32)<<16)|(a[:,1].astype(np.uint32)<<8)|a[:,2].astype(np.uint32)
 if cartoon.any():assert np.isin(rgb_keys(out[cartoon]),np.unique(rgb_keys(rgb[cartoon]))).all(),'cartoon vector set not closed'
 return len(rgb),int(event.sum()),int(np.any(out!=rgb,1)[de].sum())
def run(name,cmd,d,timeout=900):
 p=subprocess.run(list(map(str,cmd)),cwd=d,capture_output=True,text=True,timeout=timeout);log=p.stdout+p.stderr
 (d/(name+'.log')).write_text(log,encoding='utf-8')
 assert p.returncode==0 and '** Error' not in log and '** Fatal' not in log,(name,p.returncode,log[-3500:]);return log
cases=[('small',96,64,128,80,12,(40,64,24,44),False),
       ('full',1280,720,1650,750,1,(672,720,144,176),False),
       ('uniform_full',1280,720,1650,750,1,(672,720,144,176),True)]
if '--small-only' in sys.argv:cases=cases[:1]
for name,w,h,ht,vt,frames,roi,uniform in cases:
 d=V/name;data=fixture(w,h,ht,vt,frames,roi,uniform);n,events,changed=write_case(d,data,ht,w,h,roi)
 params={'N':n,'HT':ht,'W':w,'H':h,'X0':roi[0],'X1':roi[1],'Y0':roi[2],'Y1':roi[3]}
 cmd=[IV,'-g2012','-s','display_v11_tb']
 for key,value in params.items():cmd+=['-P',f'display_v11_tb.{key}={value}']
 cmd+=['-o',d/'test.vvp',V/'display_v11_tb.v',H/'display_denoise_v11.v']
 run('compile',cmd,d);log=run('run',[IV.with_name('vvp.exe'),d/'test.vvp'],d)
 assert 'DISPLAY_V11_PASS' in log;print(name,log[-450:],flush=True)
 tests[name]={'pass':True,'packets':n,'active':int(data[1].sum()),'dpc_events':events,'changed_active':changed,'h_total':ht,
              'width':w,'height':h,'frames':frames,'sample_edge_lag':2*ht+6,'registered_stages':2*ht+7,'log':str((d/'run.log').relative_to(R))}
 if name=='full':full_data=data
if '--small-only' in sys.argv:
 result={'tests':tests,'production_sample_edge_lag':3306,'production_registered_stages':3307,
         'sample_edge_lag':3306,'registered_stages':3307,
         'source_sha256':{'user_source/hdl_source/display_denoise_v11.v':sha(H/'display_denoise_v11.v')},
         'oracle_sha256':{p.relative_to(R).as_posix():sha(p) for p in [R/'tools/display_v11_model.py',R/'tools/display_v9_model.py',Path(__file__),V/'display_v11_tb.v']}}
 (V/'small_result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('DISPLAY_V11_SMALL_PASS',flush=True);sys.exit(0)
d=V/'native';n,events,changed=write_case(d,full_data,1650,1280,720,(672,720,144,176))
for name,cmd in [('vmap_init',[MS/'vmap.exe','-c']),('vlib',[MS/'vlib.exe','work']),('vmap',[MS/'vmap.exe','work','work']),
 ('vlog',[MS/'vlog.exe','-sv','-work','work',L/'ph1p_phy_gsr.v',L/'ph1p_logic_eram.v',V/'display_v11_tb.v',H/'display_denoise_v11.v']),
 ('vsim',[MS/'vsim.exe','-c','-do',f'vsim -gN={n} -gHT=1650 -gW=1280 -gH=720 -gX0=672 -gX1=720 -gY0=144 -gY1=176 work.PH1P_PHY_GSR work.display_v11_tb; onfinish stop; run -all; quit -f'])]:
 log=run(name,cmd,d)
 if name=='vsim':assert 'DISPLAY_V11_PASS' in log;print(log[-650:],flush=True)
tests['native_production_ram']={'pass':True,'packets':n,'dpc_events':events,'h_total':1650,'width':1280,'height':720,
 'sample_edge_lag':3306,'registered_stages':3307,'native_vendor_model':True,'log':str((d/'vsim.log').relative_to(R))}
result={'tests':tests,'production_sample_edge_lag':3306,'production_registered_stages':3307,
 'sample_edge_lag':3306,'registered_stages':3307,'native_vendor_model':True,
 'source_sha256':{p.relative_to(R).as_posix():sha(p) for p in [H/'display_denoise_v11.v']},
 'oracle_sha256':{p.relative_to(R).as_posix():sha(p) for p in [R/'tools/display_v11_model.py',R/'tools/display_v9_model.py',Path(__file__),V/'display_v11_tb.v']},
 'seconds':round(time.time()-start,2),
 'scope':'36-bit complete stream equality with independent NumPy vector-median oracle; small all-page/multiframe, full true timing/ROI, uniform no-dot, native full ERAM. Normal non-event RGB equals accepted V9 clear cross or exact non-clear pass. No board test or whole-camera/DDR simulation.'}
(V/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('DISPLAY_V11_ALL_PASS',flush=True)
