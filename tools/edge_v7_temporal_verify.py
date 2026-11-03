"""Independent noise every frame: exact V6/V7 RTL and temporal snow metrics.

This is a supplemental synthetic test. It never edits the production kernel and
does not overwrite the previously accepted static-fixture verification result.
"""
from pathlib import Path
import hashlib,json,subprocess,time,sys,re
import numpy as np
from PIL import Image
from edge_v7_verify import core,original,R
sys.stdout.reconfigure(encoding='utf-8')
T=R/'validation/edge_v7/temporal';T.mkdir(parents=True,exist_ok=True)
RTL=R/'user_source/hdl_source/isp/edge_detect_96.v'
V6=R.parent/'07_stylize_flame_fusion_v6_visual_aid/user_source/hdl_source/isp/edge_detect_96.v'
IV=Path(r'D:\anlu\iverilog\bin\iverilog.exe')

TB='''`timescale 1ns/1ps
module temporal_tb;
parameter W=320,H=96,F=12;localparam N=W*H/4;
reg clk=0;always #5 clk=~clk;
reg rst=0,v=0,u=0,l=0;reg [95:0] rgb=0;
wire nv,nu,nl,ov,ou,ol;wire [95:0] np,op;
reg [95:0] image[0:N*F-1];reg pv=0,pu=0,pl=0;
integer f,b,fd7,fd6,checks=0,seed=20261028;
reg [1023:0] inf,out7,out6;
edge_detect_96 #(.IMG_WIDTH(W),.IMG_HEIGHT(H),.EDGE_TH(40)) current(
.I_clk(clk),.I_rst_n(rst),.I_tvalid(v),.I_tuser(u),.I_tlast(l),.I_tdata(rgb),.I_tready(1'b1),
.O_tvalid(nv),.O_tuser(nu),.O_tlast(nl),.O_tdata(np));
edge_v6_temporal_reference #(.IMG_WIDTH(W),.IMG_HEIGHT(H),.EDGE_TH(40)) prior(
.I_clk(clk),.I_rst_n(rst),.I_tvalid(v),.I_tuser(u),.I_tlast(l),.I_tdata(rgb),.I_tready(1'b1),
.O_tvalid(ov),.O_tuser(ou),.O_tlast(ol),.O_tdata(op));
task tick;begin @(posedge clk);#1;
if(rst)begin
if({nv,nu,nl}!=={pv,pu,pl} || {ov,ou,ol}!=={pv,pu,pl})$fatal(1,"metadata/frame boundary changed");
if(nv)begin $fdisplay(fd7,"%024h",np);$fdisplay(fd6,"%024h",op);checks=checks+1;end
end
pv=v;pu=u;pl=l;@(negedge clk);end endtask
initial begin
if(!$value$plusargs("in=%s",inf))inf="input.hex";
if(!$value$plusargs("out7=%s",out7))out7="v7.hex";
if(!$value$plusargs("out6=%s",out6))out6="v6.hex";
$readmemh(inf,image);fd7=$fopen(out7,"w");fd6=$fopen(out6,"w");repeat(4)tick;rst=1;
for(f=0;f<F;f=f+1)begin
v=0;u=f%2==0;l=0;tick;u=0;repeat(7)tick;
for(b=0;b<N;b=b+1)begin
v=1;u=f%2==1&&b==0;l=b%(W/4)==W/4-1;rgb=image[f*N+b];tick;
if(($random(seed)&15)==0)begin v=0;u=0;l=0;rgb={$random(seed),$random(seed),$random(seed)};repeat(1+($random(seed)&1))tick;end
if(b%(W/4)==W/4-1)begin v=0;u=0;l=0;repeat(3+($random(seed)&3))tick;end
end v=0;u=0;l=0;repeat(20)tick;
$display("TEMPORAL_FRAME %0d th7=%0d th6=%0d",f,current.threshold,prior.threshold);
end
$fclose(fd7);$fclose(fd6);if(checks!=F*N)$fatal(1,"frame beat count changed");
$display("EDGE_TEMPORAL_RTL_PASS beats=%0d distinct_frames metadata random_gaps both_SOF",checks);$finish;
end endmodule
'''

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def align(edge,offset):
 a=np.zeros_like(edge,dtype=bool);a[:-offset,:-offset]=edge[offset:,offset:]>0;return a
def max_gap(present):
 now=longest=0
 for p in present:now=0 if p else now+1;longest=max(longest,now)
 return longest
def visibility(a,points,orientation):
 present=[]
 for r,c in points:
  roi=(slice(r-3,r+4),slice(c-1,c+2)) if orientation=='horizontal' else (slice(r-1,r+2),slice(c-3,c+4))
  present.append(bool(np.any(a[roi])))
 return {'fraction':round(float(np.mean(present)),5),'max_missing_run':max_gap(present)}

def case(sigma):
 frames,h,w=12,96,320;y,x=np.mgrid[:h,:w];rng=np.random.default_rng(555000+sigma)
 clean=np.full((h,w),48.,float)
 clean[x==40]+=32;clean[y==30]+=64;clean[x-y==90]+=32;clean[x+y==240]+=64
 points={'vertical':[(r,40) for r in range(8,h-8)],'horizontal':[(30,c) for c in range(8,w-8)],
  'diag+':[(r,r+90) for r in range(8,h-8)],'diag-':[(r,240-r) for r in range(8,h-8)]}
 contrast={'vertical':32,'horizontal':64,'diag+':32,'diag-':64}
 # Shared luma grain models gain noise; independent small channel grain also
 # exercises production RGB-to-gray maths without collapsing all RGB words.
 rgb=np.clip(clean[None,...,None]+rng.normal(0,sigma,(frames,h,w,1))+
   rng.normal(0,sigma/4,(frames,h,w,3)),0,255).astype(np.uint8)
 gray=(rgb[...,0].astype(int)+2*rgb[...,1].astype(int)+rgb[...,2].astype(int))//4
 assert all(not np.array_equal(gray[f],gray[f-1]) for f in range(1,frames)),'noise frame unexpectedly repeated'
 name='sigma'+str(sigma)
 with (T/(name+'_input.hex')).open('w') as f:
  for beat in rgb.reshape(-1,12):f.write(beat.tobytes().hex()+'\n')
 cmd=[IV.with_name('vvp.exe'),T/'temporal.vvp',f'+in={name}_input.hex',f'+out7={name}_v7.hex',f'+out6={name}_v6.hex']
 start=time.time();p=subprocess.run(list(map(str,cmd)),cwd=T,capture_output=True,text=True,timeout=180)
 log=p.stdout+p.stderr;(T/(name+'.log')).write_text(log,encoding='utf-8');assert p.returncode==0 and 'EDGE_TEMPORAL_RTL_PASS' in log,log[-1800:]
 printed_thresholds=[tuple(map(int,m)) for m in re.findall(r'TEMPORAL_FRAME (\d+) th7=(\d+) th6=(\d+)',log)]
 assert len(printed_thresholds)==frames,('missing actual threshold traces',printed_thresholds)
 actual={version:np.frombuffer(bytes.fromhex(''.join((T/(name+'_'+version+'.hex')).read_text().split())),np.uint8).reshape(frames,h,w,3)
  for version in ['v6','v7']}
 background=(x>=8)&(x<w-8)&(y>=8)&(y<h-8)&(np.abs(x-40)>6)&(np.abs(y-30)>6)&(np.abs(x-y-90)>8)&(np.abs(x+y-240)>8)
 th7=th6=40;history=[];previous={};aligned_frames={k:[] for k in ['v6','v7']}
 for f in range(frames):
  assert printed_thresholds[f]==(f,th7,th6),('RTL frame-threshold mismatch',printed_thresholds[f],f,th7,th6)
  expected7,nxt7=core(gray[f],th7);expected6,nxt6=original(gray[f],th6)
  for version,expected in [('v7',expected7),('v6',expected6)]:
   assert np.array_equal(actual[version][f],expected[...,None].repeat(3,axis=-1)),(version,sigma,f,'oracle mismatch')
  aligned={'v7':align(expected7,2),'v6':align(expected6,1)}
  row={'frame':f,'threshold_v7':th7,'threshold_v6':th6,'measured_gray_noise_std':round(float(np.std(gray[f][background]-48)),3)}
  for version in ['v6','v7']:
   a=aligned[version];aligned_frames[version].append(a)
   row[version]={'background_white_density':round(float(np.mean(a[background])),6),
     'background_flip_rate':None if f==0 else round(float(np.mean((a^previous[version])[background])),6),
     'contours':{orientation:{'contrast':contrast[orientation],**visibility(a,pp,orientation)} for orientation,pp in points.items()}}
   previous[version]=a
  history.append(row);th7,th6=nxt7,nxt6
 summary={}
 for version in ['v6','v7']:
  summary[version]={'mean_background_white_density':round(float(np.mean([v[version]['background_white_density'] for v in history])),6),
   'mean_background_flip_rate':round(float(np.mean([v[version]['background_flip_rate'] for v in history[1:]])),6),
   'worst_contour_fraction':min(c['fraction'] for row in history for c in row[version]['contours'].values()),
   'worst_contour_missing_run':max(c['max_missing_run'] for row in history for c in row[version]['contours'].values()),
   'thresholds':[v['threshold_'+version] for v in history]}
 assert summary['v7']['mean_background_white_density']<summary['v6']['mean_background_white_density']*.7,summary
 assert summary['v7']['mean_background_flip_rate']<summary['v6']['mean_background_flip_rate']*.7,summary
 assert summary['v7']['worst_contour_fraction']>=.95,summary
 # Three model-verified frames per panel demonstrate changing noise, not a
 # repeated still. These are synthetic fixtures, not board photos.
 panels=[]
 for f in [0,frames//2,frames-1]:
  panels.append(np.concatenate([rgb[f],np.repeat((aligned_frames['v6'][f]*255).astype(np.uint8)[...,None],3,-1),
   np.repeat((aligned_frames['v7'][f]*255).astype(np.uint8)[...,None],3,-1)],axis=1))
 Image.fromarray(np.concatenate(panels,axis=0)).save(T/(name+'_synthetic_verified.png'))
 print(name,json.dumps(summary),flush=True)
 return {'pass':True,'frames':frames,'pixels_per_version':frames*h*w,'seconds':round(time.time()-start,2),
  'background_samples':int(np.count_nonzero(background)),'summary':summary,'history':history,
  'scope':'12 independent noisy input frames from cold reset, including adaptive convergence; not a steady-state field accuracy measurement.'}

def main():
 before=sha(RTL);source=V6.read_text(encoding='utf-8').replace('module edge_detect_96 #(', 'module edge_v6_temporal_reference #(')
 assert 'module edge_v6_temporal_reference #(' in source
 (T/'edge_v6_temporal_reference.v').write_text(source,encoding='utf-8');(T/'temporal_tb.v').write_text(TB,encoding='utf-8')
 cmd=[IV,'-g2012','-s','temporal_tb','-o',T/'temporal.vvp',T/'temporal_tb.v',RTL,T/'edge_v6_temporal_reference.v']
 p=subprocess.run(list(map(str,cmd)),cwd=T,capture_output=True,text=True,timeout=60)
 (T/'compile.log').write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0,p.stderr
 results={str(sigma):case(sigma) for sigma in [4,8]};assert sha(RTL)==before,'production source changed during verification'
 result={'tests':results,'source_sha256':{'user_source/hdl_source/isp/edge_detect_96.v':before},
  'oracle_sha256':{p.relative_to(R).as_posix():sha(p) for p in [R/'tools/edge_v7_verify.py',Path(__file__),T/'temporal_tb.v',T/'edge_v6_temporal_reference.v']},
  'v6_production_source_sha256':sha(V6),'source_untouched':True,'metadata_latency_clocks':2,'pixels_per_clock':4,
  'comparison_alignment':'V6 source centre offsets 1 row/1 column; V7 offsets 2 rows/2 columns; shared source-coordinate interior mask.',
  'metric_limit':'Neighborhood contour presence can include coincident noise, so it is reported together with background noise. Synthetic results do not prove board performance.'}
 (T/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('EDGE_V7_TEMPORAL_ALL_PASS',flush=True)
if __name__=='__main__':main()
