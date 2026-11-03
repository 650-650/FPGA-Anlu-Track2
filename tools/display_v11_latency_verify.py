"""Fast actual-HT1650 marker measurement, separate from full/native evidence."""
from pathlib import Path
import hashlib,json,re,subprocess,time
import numpy as np
from display_v11_model import filter_rgb
R=Path(__file__).resolve().parents[1];V=R/'validation/display_v11';D=V/'latency_fast';D.mkdir(exist_ok=True)
H=R/'user_source/hdl_source';IV=Path(r'D:/anlu/iverilog/bin/iverilog.exe');n=12000;ht=1650;start=time.time()
tick=np.arange(n);x=tick%ht;de=x<1280;overlay=np.zeros(n,bool);ctrl=np.zeros(n,np.uint8)
hs=(x>=1390)&(x<1430);vs=(tick>=11000)&(tick<11006);rgb=np.full((n,3),64,np.uint8)
markers=[0,1,100,1649,1650,3299,3300,6601,11777]
for j,i in enumerate(markers):
 ctrl[i]=0xa5 if j==0 else 0x80+(j%8);rgb[i]=[18+j,52+3*j,86+7*j];overlay[i]=j%2==0
out=filter_rgb(rgb,de,overlay,ctrl,ht,1280,720,vs)
head=(ctrl.astype(np.uint64)<<28)|(overlay.astype(np.uint64)<<27)|(de.astype(np.uint64)<<26)|(hs.astype(np.uint64)<<25)|(vs.astype(np.uint64)<<24)
def pack(a):return head|(a[:,0].astype(np.uint64)<<16)|(a[:,1].astype(np.uint64)<<8)|a[:,2]
for name,a in [('input.hex',pack(rgb)),('expected.hex',pack(out))]:(D/name).write_text(''.join(f'{int(p):09x}\n' for p in a),encoding='ascii')
tb=(V/'display_v11_tb.v').read_text().replace('display_v11_tb','display_v11_latency_tb')
tb=tb.replace('integer i,j,checks=0,changed=0;', 'integer i,j,checks=0,changed=0,first_marker=-1;')
tb=tb.replace('actual={oc,oo,od,oh,ov,q};','actual={oc,oo,od,oh,ov,q}; if(actual===expected[0] && first_marker<0)first_marker=i;')
tb=tb.replace('if(checks!=N)$fatal', 'if(first_marker!=LAG)$fatal(1,"marker observed wrong lag=%0d expected=%0d",first_marker,LAG); $display("DISPLAY_V11_LATENCY_MARKER observed_sample_edge_lag=%0d",first_marker); if(checks!=N)$fatal')
(D/'latency_tb.v').write_text(tb,encoding='utf-8')
def run(name,cmd):
 p=subprocess.run(list(map(str,cmd)),cwd=D,capture_output=True,text=True,timeout=120);s=p.stdout+p.stderr
 (D/(name+'.log')).write_text(s,encoding='utf-8');assert p.returncode==0,(name,p.returncode,s[-2500:]);return s
run('compile',[IV,'-g2012','-s','display_v11_latency_tb','-P',f'display_v11_latency_tb.N={n}',
 '-P','display_v11_latency_tb.HT=1650','-P','display_v11_latency_tb.W=1280','-P','display_v11_latency_tb.H=720',
 '-P','display_v11_latency_tb.X0=672','-P','display_v11_latency_tb.X1=720','-P','display_v11_latency_tb.Y0=144','-P','display_v11_latency_tb.Y1=176',
 '-o',D/'latency.vvp',D/'latency_tb.v',H/'display_denoise_v11.v'])
log=run('run',[IV.with_name('vvp.exe'),D/'latency.vvp'])
observed=int(re.search(r'observed_sample_edge_lag=(\d+)',log).group(1));assert observed==3306 and 'DISPLAY_V11_PASS' in log
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
result={'tests':{'production_HT_marker_and_complete_packets':{'pass':True,'packets':n,'unique_markers':len(markers),
 'h_total':1650,'width':1280,'height':720,'observed_sample_edge_lag':observed,'registered_stages':observed+1,
 'log':str((D/'run.log').relative_to(R))}},'production_sample_edge_lag':observed,'production_registered_stages':observed+1,
 'sample_edge_lag':observed,'registered_stages':observed+1,
 'source_sha256':{'user_source/hdl_source/display_denoise_v11.v':sha(H/'display_denoise_v11.v')},
 'oracle_sha256':{p.relative_to(R).as_posix():sha(p) for p in [Path(__file__),R/'tools/display_v11_model.py',R/'tools/display_v9_model.py',D/'latency_tb.v']},
 'seconds':round(time.time()-start,2),'scope':'Actual RTL HT1650 marker observation and12000 full36-bit packets; independent fast latency evidence, not the separately required full-frame/native-RAM result.'}
(V/'production_latency_result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(log);print('PRODUCTION_LATENCY_VERIFIED',observed,observed+1,flush=True)
