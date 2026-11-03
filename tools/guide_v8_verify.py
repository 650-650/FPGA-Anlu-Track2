"""Exact local RTL, realistic B1/B2 preprocessing, and scene-independent ink."""
from pathlib import Path
import hashlib,json,subprocess,time,sys
import numpy as np
from PIL import Image
import model_baseline as b
import model_denoise as d
import guide_v8_model as model
sys.stdout.reconfigure(encoding='utf-8')
R=Path(__file__).resolve().parents[1];V=R/'validation/guide_v8';V.mkdir(exist_ok=True)
RTL=R/'user_source/hdl_source/isp/style_guide_v8.v';IV=Path(r'D:\anlu\iverilog\bin\iverilog.exe')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def old_phi(M,w,h):
 s=M[:,0::4][:,:w//4-2].ravel();n=(w//4-2)*(h-4);phi=128
 for _ in range(108):
  count=np.count_nonzero(s>=phi)
  if count>n*4//100:phi=min(phi+2,255)
  elif count<n*2//100:phi=max(phi-2,48)
 return phi
def old_sketch(Y,M,phi):
 yy,_,_,_,mag=d.guide(Y,M);floor=phi//8;gain=b.gain16(phi-floor)
 return np.maximum(224+yy//8-np.minimum(np.maximum(mag-floor,0)*gain//16,255),0).astype(np.uint8)
def prepared(rgb):
 h,w=rgb.shape[:2];b.set_size(w,h);B,Y,M=b.core(rgb);ys=d.windows(Y);ms=d.windows(M)
 return Y,M,np.stack(ys),np.stack(ms)
def trace_points(mag,edge,y2,orientation,delta):
 # Source columns map directly to this style oracle; source row r maps to r-3.
 h,w=mag.shape;rows=range(12,h-12)
 if orientation=='vertical':points=[(r,70) for r in rows]
 elif orientation=='horizontal':points=[(57,c) for c in range(24,w-24)]
 elif orientation=='diag+':points=[(r,r+33) for r in rows if r+33<w-8]
 else:points=[(r,197-r) for r in rows if 8<=197-r<w-8]
 sketch=model.sketch(mag,y2);ep=[];sp=[]
 for rr,cc in points:
  a=(slice(rr-1,rr+2),slice(cc-4,cc+5)) if orientation!='horizontal' else (slice(rr-4,rr+5),slice(cc-1,cc+2))
  ep.append(bool(np.any(edge[a])));sp.append(bool(np.any(sketch[a]<210)))
 return {'contrast':delta,'orientation':orientation,'edge_nearby_fraction':float(np.mean(ep)),
  'sketch_nearby_fraction':float(np.mean(sp)),'points':len(points)}

def main():
 before=sha(RTL);rng=np.random.default_rng(843);h,w=96,240;y,x=np.mgrid[:h,:w]
 vectors_y=[];vectors_m=[];metrics={};line_metrics=[];temporal=[]
 for kind in ['iid4','iid8','block2_8','block3_8','block4_8','phase2quiet_other20']:
  noise=rng.normal(0,4 if kind=='iid4' else 8,(h,w))
  if kind.startswith('block'):
   q=int(kind[5]);noise=np.repeat(np.repeat(rng.normal(0,8,((h+q-1)//q,(w+q-1)//q)),q,0),q,1)[:h,:w]
  if kind.startswith('phase'):
   noise=rng.normal(0,20,(h,w));noise[:,2::4]=rng.normal(0,2,(h,w//4))
  rgb=np.clip(np.array([36,48,64])[None,None,:]+noise[...,None]+rng.normal(0,1,(h,w,3)),0,255).astype(np.uint8)
  Y,M,ys,ms=prepared(rgb);mag,edge,support,coarse=model.guide(ys,ms);sk=model.sketch(mag,ys[4]);phi=old_phi(M,w,h);old=old_sketch(Y,M,phi)
  vectors_y.append(ys.reshape(9,-1));vectors_m.append(ms.reshape(9,-1))
  metrics[kind]={'old_adapted_phi':phi,'edge_white_fraction':float(np.mean(edge)),
   'sketch_under210_fraction':float(np.mean(sk<210)),'v7_sketch_under210_fraction':float(np.mean(old<210)),
   'v8_mean_ink':float(np.mean((224+ys[4]//8)-sk)),'oracle_pixel_vectors':int(mag.size)}
  assert np.mean(sk<210)<np.mean(old<210)*.8,(kind,metrics[kind])
  canvas=np.concatenate([np.repeat(old[...,None],3,-1),np.repeat(sk[...,None],3,-1),np.repeat((edge*255).astype(np.uint8)[...,None],3,-1)],axis=1)
  Image.fromarray(canvas).save(V/(kind+'_verified_model.png'))
 for delta in [8,12,17,32,64]:
  for orientation in ['vertical','horizontal','diag+','diag-']:
   rgb=np.full((h,w,3),48,np.uint8)
   if orientation=='vertical':rgb[12:h-12,70:72]=48+delta
   elif orientation=='horizontal':rgb[60:62,20:w-20]=48+delta
   elif orientation=='diag+':rgb[((x-y)>=30)&((x-y)<32)]=48+delta
   else:rgb[((x+y)>=200)&((x+y)<202)]=48+delta
   Y,M,ys,ms=prepared(rgb);mag,edge,_,_=model.guide(ys,ms)
   case=trace_points(mag,edge,ys[4],orientation,delta);line_metrics.append(case)
   assert case['edge_nearby_fraction']>=.95 and case['sketch_nearby_fraction']>=.95,case
   vectors_y.append(ys.reshape(9,-1));vectors_m.append(ms.reshape(9,-1))
 # Strong remote texture is not allowed to change the left weak-line result.
 scene_outputs=[]
 for textured in [False,True]:
  rgb=np.full((h,w,3),48,np.uint8);rgb[12:h-12,70:72]=65;rgb[60:62,20:w//2]=76
  if textured:
   right=(x>=w*2//3)&(y<h//2);checker=((x//3+y//3)&1)*255;rgb[right]=np.repeat(checker[...,None],3,-1)[right]
  Y,M,ys,ms=prepared(rgb);mag,edge,_,_=model.guide(ys,ms);left=model.sketch(mag,ys[4])[:,:w//2-12]
  scene_outputs.append(left);vectors_y.append(ys.reshape(9,-1));vectors_m.append(ms.reshape(9,-1))
 assert np.array_equal(*scene_outputs),'remote texture changed local line strength'
 # Every frame gets new sensor-like grain, then the actual B1/B2 processing.
 for sigma in [4,8]:
  previous7=previous8=None;frames=[]
  for f in range(8):
   noise=rng.normal(0,sigma,(h,w));rgb=np.clip(48+noise[...,None]+rng.normal(0,1,(h,w,3)),0,255).astype(np.uint8)
   rgb[12:h-12,70:72]=np.clip(80+noise[12:h-12,70:72,None],0,255).astype(np.uint8)
   Y,M,ys,ms=prepared(rgb);mag,edge,_,_=model.guide(ys,ms);s8=model.sketch(mag,ys[4]);s7=old_sketch(Y,M,96)
   background=np.ones(s8.shape,bool);background[:,60:86]=False
   row={'sigma':sigma,'frame':f,'v7_dark_fraction':float(np.mean((s7<210)[background])),
    'v8_dark_fraction':float(np.mean((s8<210)[background])),
    'v7_flip':None if previous7 is None else float(np.mean(((s7<210)^(previous7<210))[background])),
    'v8_flip':None if previous8 is None else float(np.mean(((s8<210)^(previous8<210))[background]))}
   frames.append(row);previous7=s7;previous8=s8
   vectors_y.append(ys.reshape(9,-1));vectors_m.append(ms.reshape(9,-1))
  summary={'sigma':sigma,'v7_mean_dark_fraction':float(np.mean([a['v7_dark_fraction'] for a in frames])),
   'v8_mean_dark_fraction':float(np.mean([a['v8_dark_fraction'] for a in frames])),
   'v7_mean_flip':float(np.mean([a['v7_flip'] for a in frames[1:]])),
   'v8_mean_flip':float(np.mean([a['v8_flip'] for a in frames[1:]]))}
  assert summary['v8_mean_dark_fraction']<summary['v7_mean_dark_fraction']*.8,summary
  assert summary['v8_mean_flip']<summary['v7_mean_flip']*.8,summary
  temporal.append({'summary':summary,'frames':frames})
 # All physical frame windows plus adversarial arbitrary local combinations.
 vectors_y.append(rng.integers(0,256,(9,30000)));vectors_m.append(rng.integers(0,256,(9,30000)))
 yy=np.concatenate(vectors_y,axis=1);mm=np.concatenate(vectors_m,axis=1)
 mag,edge,support,_=model.guide(yy,mm);expected=(mag.astype(int)<<2)|(edge.astype(int)<<1)|support.astype(int)
 with (V/'input.hex').open('w') as fi,(V/'expected.hex').open('w') as fe:
  for k in range(yy.shape[1]):
   fi.write(bytes(np.r_[yy[:,k],mm[:,k]].astype(np.uint8)).hex()+'\n');fe.write(f'{expected[k]:03x}\n')
 n=yy.shape[1]
 tb=f'''`timescale 1ns/1ps
module guide_v8_tb;
localparam N={n};reg [143:0] mem[0:N-1];reg [9:0] expected[0:N-1];
reg[71:0] y,m;wire[7:0] q;wire e,s;integer i;
style_guide_v8 dut(.I_y2(y),.I_fine(m),.O_mag(q),.O_edge(e),.O_support(s));
initial begin $readmemh("input.hex",mem);$readmemh("expected.hex",expected);
for(i=0;i<N;i=i+1)begin y=mem[i][143:72];m=mem[i][71:0];#1;
if({{q,e,s}}!==expected[i])$fatal(1,"local guide mismatch i=%0d got=%h expected=%h",i,{{q,e,s}},expected[i]);end
$display("GUIDE_V8_EXACT_PASS windows=%0d actual_B1_B2 correlated_phase_temporal_weak_lines",N);$finish;end endmodule
'''
 (V/'guide_v8_tb.v').write_text(tb,encoding='utf-8');start=time.time()
 for stage,cmd in [('compile',[IV,'-g2012','-s','guide_v8_tb','-o',V/'guide.vvp',V/'guide_v8_tb.v',RTL]),('run',[IV.with_name('vvp.exe'),V/'guide.vvp'])]:
  p=subprocess.run(list(map(str,cmd)),cwd=V,capture_output=True,text=True,timeout=240)
  log=p.stdout+p.stderr;(V/(stage+'.log')).write_text(log,encoding='utf-8');assert p.returncode==0,(stage,log[-1500:])
  if stage=='run':assert 'GUIDE_V8_EXACT_PASS' in log;print(log[-1000:],flush=True)
 assert sha(RTL)==before,'helper changed while verification was running'
 result={'pass':True,'exact_windows':n,'rtl_seconds':round(time.time()-start,2),'noise_cases':metrics,'clean_line_cases':line_metrics,
  'remote_texture_left_pixels_exact':True,'temporal_cases':temporal,'source_sha256':{RTL.relative_to(R).as_posix():before},
  'oracle_sha256':{p.relative_to(R).as_posix():sha(p) for p in [R/'tools/guide_v8_model.py',R/'tools/model_baseline.py',R/'tools/model_denoise.py',Path(__file__)]},
  'limits':['Synthetic models use actual B1/B2/fine preprocessing but do not measure the real sensor noise distribution.',
   'Strong spatially correlated noise still leaves texture; only fixed local calibration was claimed.',
   'This is a combinational helper test; parent style bench verifies its C1 packing, stream latency and mode0 preservation.']}
 (V/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('GUIDE_V8_VERIFICATION_PASS',json.dumps({'windows':n,'noise_cases':metrics,'temporal':temporal},ensure_ascii=False)[:2400],flush=True)
if __name__=='__main__':main()
