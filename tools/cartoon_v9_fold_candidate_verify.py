"""Create and verify an isolated 504-FF-saving V9 row-sum candidate.

Never changes the production style, project, model, or existing result JSON.
The candidate retains original module names so the parent can explicitly copy
it into production later, after making its own placement/timing decision.
"""
from pathlib import Path
import hashlib,json,re,subprocess,time
import numpy as np
from PIL import Image
R=Path(__file__).resolve().parents[1];V=R/'validation/cartoon_v9/fold_candidate';V.mkdir(exist_ok=True)
S=R/'user_source/hdl_source/isp/stylize_v5_96.v';G=R/'user_source/hdl_source/isp/style_guide_v8.v'
EXPECTED='1b2741d42dd9bf41180f9e81d769a076b8af63b540b68602f36adc0dc156dbc7'
IV=Path(r'D:\anlu\iverilog\bin\iverilog.exe')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(S)==EXPECTED,'production is no longer the authorized frozen source'
original=S.read_text(encoding='utf-8')
functions='''function [89:0] cartoon_rows;
 input [215:0] neighbours;
 reg [9:0] row0,row1,row2;
 integer ch;
 begin
  for(ch=0;ch<3;ch=ch+1)begin
   row0={2'd0,neighbours[215-8*ch-:8]}+{1'd0,neighbours[191-8*ch-:8],1'd0}+{2'd0,neighbours[167-8*ch-:8]};
   row1={2'd0,neighbours[143-8*ch-:8]}+{1'd0,neighbours[119-8*ch-:8],1'd0}+{2'd0,neighbours[95-8*ch-:8]};
   row2={2'd0,neighbours[71-8*ch-:8]}+{1'd0,neighbours[47-8*ch-:8],1'd0}+{2'd0,neighbours[23-8*ch-:8]};
   cartoon_rows[89-10*ch-:10]=row0;
   cartoon_rows[59-10*ch-:10]=row1;
   cartoon_rows[29-10*ch-:10]=row2;
  end
 end
endfunction
function [23:0] cartoon_gaussian_rows;
 input [89:0] rows;
 reg [11:0] sum;
 integer ch;
 begin
  for(ch=0;ch<3;ch=ch+1)begin
   sum={2'd0,rows[89-10*ch-:10]}+{1'd0,rows[59-10*ch-:10],1'd0}+{2'd0,rows[29-10*ch-:10]};
   cartoon_gaussian_rows[23-8*ch-:8]=sum[11:4];
  end
 end
endfunction'''
candidate,n=re.subn(r'(?ms)^function \[23:0\] cartoon_gaussian;.*?^endfunction',functions,original)
assert n==1
old_lines=[
 'reg[863:0]c1_neighbours;reg[3:0]c1_protect;',
 'c1_neighbours[863-216*k-:216]<=cartoon_selected[863-216*k-:216];c1_protect[3-k]<=cartoon_protected[3-k];',
 'default:c2_px[95-24*k-:24]<=cartoon_gaussian(c1_neighbours[863-216*k-:216]);']
new_lines=[
 'reg[359:0]c1_rows;reg[3:0]c1_protect;',
 'c1_rows[359-90*k-:90]<=cartoon_rows(cartoon_selected[863-216*k-:216]);c1_protect[3-k]<=cartoon_protected[3-k];',
 'default:c2_px[95-24*k-:24]<=cartoon_gaussian_rows(c1_rows[359-90*k-:90]);']
for a,b in zip(old_lines,new_lines):
 assert candidate.count(a)==1,a
 candidate=candidate.replace(a,b)
# Keep the selector, including all colour-line decisions, byte-for-byte.
module=lambda s:re.search(r'(?ms)^module style_cartoon_select_v9\b.*?^endmodule',s).group(0)
assert module(candidate)==module(original)
C=V/'stylize_v5_96.v';C.write_text(candidate,encoding='utf-8')
reference=original
for name in sorted(re.findall(r'(?m)^module\s+(\w+)',reference),key=len,reverse=True):reference=re.sub(r'\b'+name+r'\b',name+'_current_ref',reference)
(V/'current_reference.v').write_text(reference,encoding='utf-8')
tb=r'''`timescale 1ns/1ps
module fold_candidate_tb;
parameter W=160,H=90,F=8;localparam N=W*H/4;
reg clk=0;always #5 clk=~clk;reg rst=0,v=0,u=0,l=0;reg[95:0]rgb=0;reg[1:0]mode=0;
wire nv,nu,nl,ov,ou,ol;wire[95:0]nq,oq;reg[95:0]images[0:N*F-1];
reg[15:0]vd=0,ud=0,ld=0;integer f,j,pixels=0,clocks=0;integer mode_pixels[0:3];
stylize_v5_96 #(.IMG_WIDTH(W),.IMG_HEIGHT(H),.EXTERNAL_EDGE(0)) candidate(.I_clk(clk),.I_rst_n(rst),.I_mode(mode),.I_tvalid(v),.I_tuser(u),.I_tlast(l),.I_tdata(rgb),.I_edge_data(96'd0),.I_tready(1'b1),.O_tvalid(nv),.O_tuser(nu),.O_tlast(nl),.O_tdata(nq));
stylize_v5_96_current_ref #(.IMG_WIDTH(W),.IMG_HEIGHT(H),.EXTERNAL_EDGE(0)) current(.I_clk(clk),.I_rst_n(rst),.I_mode(mode),.I_tvalid(v),.I_tuser(u),.I_tlast(l),.I_tdata(rgb),.I_edge_data(96'd0),.I_tready(1'b1),.O_tvalid(ov),.O_tuser(ou),.O_tlast(ol),.O_tdata(oq));
task tick;begin
@(posedge clk);#1;vd={vd[14:0],v};ud={ud[14:0],u};ld={ld[14:0],l};
if(rst)begin
clocks=clocks+1;
if({nv,nu,nl}!=={ov,ou,ol}||{nv,nu,nl}!=={vd[15],ud[15],ld[15]})$fatal(1,"sync16 changed");
if(nv)begin
if(candidate.mode_o!==current.mode_o)$fatal(1,"frame mode changed");
if(nq!==oq)$fatal(1,"candidate pixel mismatch f=%0d pixel=%0d new=%h old=%h",f,pixels,nq,oq);
pixels=pixels+4;mode_pixels[candidate.mode_o]=mode_pixels[candidate.mode_o]+4;
end end
@(negedge clk);end endtask
initial begin
for(f=0;f<4;f=f+1)mode_pixels[f]=0;
$readmemh("frames.hex",images);repeat(4)tick;rst=1;
for(f=0;f<F;f=f+1)begin
v=0;u=f%2==0;l=0;mode=$random;tick;u=0;repeat(28)tick;
for(j=0;j<N;j=j+1)begin
v=1;u=f%2==1&&j==0;l=j%(W/4)==W/4-1;mode=j==0?f%4:$random;rgb=images[f*N+j];tick;
if((j+f)%19==0)begin v=0;u=0;l=0;mode=$random;tick;end
if(j%(W/4)==W/4-1)begin v=0;u=0;l=0;repeat(3)tick;end
end v=0;u=0;l=0;repeat(40)tick;
end
if(pixels!=W*H*F)$fatal(1,"coverage");
$display("CARTOON_V9_FOLD_EQ_PASS pixels=%0d clocks=%0d mode0=%0d mode1=%0d mode2=%0d mode3=%0d fixed16 real_guide SOF_lead_and_firstvalid random_gaps",pixels,clocks,mode_pixels[0],mode_pixels[1],mode_pixels[2],mode_pixels[3]);$finish;
end
endmodule
'''
(V/'fold_candidate_tb.v').write_text(tb,encoding='utf-8')
sources={p.relative_to(R).as_posix():sha(p) for p in [S,C,G]};oracles={Path(__file__).relative_to(R).as_posix():sha(Path(__file__))}
start=time.time();tests={};rng=np.random.default_rng(20261030)
photo=np.fromfile(R.parent/'05_stylize_on_v5/sim/test_photo.raw',np.uint8).reshape(720,1280,3)
def run(label,args):
 p=subprocess.run(list(map(str,args)),cwd=V,capture_output=True,text=True,timeout=600);log=p.stdout+p.stderr
 (V/(label+'.log')).write_text(log,encoding='utf-8');assert p.returncode==0,(label,p.returncode,log[-1600:]);return log
for label,w,h,F in [('all_modes',160,90,8),('full_width',1280,48,4)]:
 im=np.asarray(Image.fromarray(photo).resize((w,h),Image.Resampling.BILINEAR))
 with (V/'frames.hex').open('w') as fd:
  for f in range(F):
   a=np.clip(im.astype(float)*(0.35 if f%2 else 1),0,255).astype(int)
   if f%4==1:
    a[:,w//4:w//2]=[18,32,70];a[:,w//2:3*w//4]=[86,52,29]
    a=np.clip(a+rng.integers(-20,21,a.shape),0,255)
   for beat in a.astype(np.uint8).reshape(-1,12):fd.write(beat.tobytes().hex()+'\n')
 run(label+'_compile',[IV,'-g2012','-s','fold_candidate_tb','-P',f'fold_candidate_tb.W={w}','-P',f'fold_candidate_tb.H={h}','-P',f'fold_candidate_tb.F={F}','-o',V/'test.vvp',V/'fold_candidate_tb.v',C,V/'current_reference.v',G])
 log=run(label,[IV.with_name('vvp.exe'),V/'test.vvp']);assert 'CARTOON_V9_FOLD_EQ_PASS' in log
 tests[label]={'pass':True,'width':w,'height':h,'frames':F,'pixels':w*h*F,'each_mode_pixels':w*h*F//4,'log':log.strip()};print(log.strip(),flush=True)
assert sources=={p:sha(R/p) for p in sources};assert oracles=={p:sha(R/p) for p in oracles};assert sha(S)==EXPECTED
result={'tests':tests,'source_sha256':sources,'oracle_sha256':oracles,'seconds':round(time.time()-start,2),'register_bits_before':864,'register_bits_candidate':360,'register_bits_saved':504,'scope':'Isolated candidate only: current production source is untouched. Real old/current versus candidate RTL with unchanged real guide, all modes, full1280 width, mode latch, sync16, random valid gaps. No TD synthesis/place/route or board claim.'}
(V/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('CARTOON_V9_FOLD_CANDIDATE_PASS',sha(C),flush=True)
