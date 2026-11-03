"""Cycle-exact coarse Sobel retiming regression; no wall-clock timeout.

Reference sources are the accepted pre-retime snapshot in validation/reference_v13.
The production window outputs and LAT16 are untouched; only early gradient work
moves onto the same edge as the original window registers. Full is four complete
720p frames in modes0..3; quick covers EXTERNAL_EDGE=0/1, gaps and resets.
"""
from pathlib import Path
import argparse,hashlib,json,re,subprocess,time
R=Path(__file__).resolve().parents[1];H=R/'user_source/hdl_source/isp';V=R/'validation/style_retiming'
IV=Path(r'D:\anlu\iverilog\bin\iverilog.exe');VVP=IV.with_name('vvp.exe')
TB=r'''`timescale 1ns/1ps
module style_retime_tb;
parameter W=64,H=16,F=12,EXT=0;
localparam N=W*H/4;
reg clk=0;always #5 clk=~clk;
reg rst=0,v=0,u=0,l=0,ready=1;reg[95:0]rgb=0,edge_data=0;reg[1:0]mode=0;
wire nv,nu,nl,nr,rv,ru,rl,rr;wire[95:0]nq,rq;
stylize_v5_96 #(.IMG_WIDTH(W),.IMG_HEIGHT(H),.EXTERNAL_EDGE(EXT)) dut(
 .I_clk(clk),.I_rst_n(rst),.I_mode(mode),.I_tvalid(v),.I_tuser(u),.I_tlast(l),.I_tdata(rgb),.I_edge_data(edge_data),.I_tready(ready),
 .O_tvalid(nv),.O_tuser(nu),.O_tlast(nl),.O_tdata(nq),.O_tready(nr));
reference_stylize_v5_96 #(.IMG_WIDTH(W),.IMG_HEIGHT(H),.EXTERNAL_EDGE(EXT)) prior(
 .I_clk(clk),.I_rst_n(rst),.I_mode(mode),.I_tvalid(v),.I_tuser(u),.I_tlast(l),.I_tdata(rgb),.I_edge_data(edge_data),.I_tready(ready),
 .O_tvalid(rv),.O_tuser(ru),.O_tlast(rl),.O_tdata(rq),.O_tready(rr));
reg[15:0]vh=0,uh=0,lh=0;
integer cycles=0,pixels=0,frames=0,mode_pixels[0:3],resets=0,f,j,p,x,y,lead;
function [23:0] scene_pixel;
 input integer frame,xx,yy;
 reg[31:0]h;reg[7:0]r,g,b;
 begin
  h=(xx*32'h45d9f3b)^(yy*32'h119de1f3)^(frame*32'h27d4eb2d);
  case((xx*4)/W)
   0:begin r=8+(h&15);g=16+((h>>4)&15);b=40+((h>>8)&31);end
   1:begin r=190+((h>>3)&31);g=145+((h>>10)&31);b=110+((h>>17)&31);end
   2:begin r=((xx/3+yy/3+frame)%2)?255:0;g=r;b=r;end
   default:begin r=h[7:0];g=h[15:8];b=h[23:16];end
  endcase
  if(xx%31==0 && yy%17==0)begin r=255;g=255;b=255;end
  if(xx%37==0 && yy%19==0)begin r=0;g=0;b=0;end
  scene_pixel={r,g,b};
 end
endfunction
task tick;
 begin
  @(posedge clk);#1;cycles=cycles+1;
  if(!rst)begin vh=0;uh=0;lh=0;end
  else begin
   vh={vh[14:0],v};uh={uh[14:0],u};lh={lh[14:0],l};
   if({nv,nu,nl}!=={vh[15],uh[15],lh[15]})$fatal(1,"LAT16_CHANGED cycle=%0d",cycles);
   if({nv,nu,nl,nq,nr}!=={rv,ru,rl,rq,rr})begin
    $display("DIFF cycle=%0d inputmode=%0d valid=%b/%b data=%024h/%024h tag=%h/%h",cycles,mode,nv,rv,nq,rq,dut.c2_tag,prior.c2_tag);
    $fatal(1,"ACCEPTED_BASELINE_OUTPUT_CHANGED");
   end
   if(dut.w3_v && {dut.w3_x,dut.w3_tag}!=={prior.w3_x,prior.w3_tag})$fatal(1,"window tag changed");
   if(dut.c1_v && dut.c1_tag!==prior.c1_tag)$fatal(1,"C1 tag changed");
   if(dut.c2_v && dut.c2_tag!==prior.c2_tag)$fatal(1,"C2 tag changed");
   if(nv)begin pixels=pixels+4;mode_pixels[dut.mode_o]=mode_pixels[dut.mode_o]+4;end
   if(nu)frames=frames+1;
  end
  @(negedge clk);
 end
endtask
task do_reset;
 begin
  rst=0;v=0;u=0;l=0;ready=1;rgb=0;edge_data=0;
  repeat(5)tick;rst=1;resets=resets+1;repeat(20)tick;
 end
endtask
genvar gp;
generate for(gp=0;gp<4;gp=gp+1)begin: gradient_oracle
 integer checks=0;
 always @(posedge clk)begin
  #1;
  if(rst && dut.w3_v && (^prior.guides[gp].u_guide.gx)!==1'bx && (^prior.guides[gp].u_guide.gy)!==1'bx)begin
   if(dut.guides[gp].coarse_gradient_r!=={prior.guides[gp].u_guide.gx,prior.guides[gp].u_guide.gy})
    $fatal(1,"retimed gradient misaligned lane%0d cycle%0d",gp,cycles);
   checks=checks+1;
  end
 end
end endgenerate
initial begin
 for(p=0;p<4;p=p+1)mode_pixels[p]=0;
 do_reset;
 // Partial row then asynchronous reset exercises an interrupted stream epoch.
 for(j=0;j<11;j=j+1)begin v=1;u=j==0;mode=2;rgb={4{24'h18324f}};tick;end
 v=0;u=0;tick;do_reset;
 for(f=0;f<F;f=f+1)begin
  lead=(f%2)?52:0;v=0;u=lead!=0;l=0;mode=3-f%4;tick;u=0;
  repeat(lead)begin mode=mode+1'b1;tick;end
  for(j=0;j<N;j=j+1)begin
   v=1;u=lead==0 && j==0;l=j%(W/4)==W/4-1;
   mode=j==0?f%4:((j*3+f)&3);ready=(j%7)!=0;
   y=j/(W/4);x=(j%(W/4))*4;
   for(p=0;p<4;p=p+1)begin
    rgb[95-24*p-:24]=scene_pixel(f,x+p,y);
    edge_data[95-24*p-:24]={8'hc3^x[7:0],8'h5a^y[7:0],8'h96^j[7:0]};
   end
   tick;
   if((j+f)%19==0)begin v=0;u=0;l=0;mode=mode^3;rgb=~rgb;edge_data=~edge_data;tick;end
   if(j%(W/4)==W/4-1)begin v=0;u=0;l=0;repeat(3)tick;end
  end
  v=0;u=0;l=0;ready=1;repeat(40)tick;
 end
 if(pixels!=F*W*H)$fatal(1,"output count changed got%0d expected%0d",pixels,F*W*H);
 for(p=0;p<4;p=p+1)if(mode_pixels[p]<W*H)$fatal(1,"mode missing %0d",p);
 $display("STYLE_RETIME_PASS W=%0d H=%0d F=%0d EXT=%0d cycles=%0d pixels=%0d mode0=%0d mode1=%0d mode2=%0d mode3=%0d resets=%0d gradients=%0d",W,H,F,EXT,cycles,pixels,mode_pixels[0],mode_pixels[1],mode_pixels[2],mode_pixels[3],resets,
 gradient_oracle[0].checks+gradient_oracle[1].checks+gradient_oracle[2].checks+gradient_oracle[3].checks);
 $finish;
end
initial begin #50000000;$fatal(1,"RTL watchdog");end
endmodule
'''
MATH=r'''`timescale 1ns/1ps
module gradient_math_tb;
reg[71:0]ys=0,ms=0;wire[21:0]grad=balanced_gradient(ys);
wire[7:0]om,dm,em;wire oe,os,de,ds,ee,es;
reference_style_guide_v8 old(.I_y2(ys),.I_fine(ms),.O_mag(om),.O_edge(oe),.O_support(os));
style_guide_v8 def(.I_y2(ys),.I_fine(ms),.I_gx(11'sh3ab),.I_gy(-11'sh2a1),.O_mag(dm),.O_edge(de),.O_support(ds));
style_guide_v8 #(.EXTERNAL_GRADIENT(1)) ext(.I_y2(ys),.I_fine(ms),.I_gx(grad[21:11]),.I_gy(grad[10:0]),.O_mag(em),.O_edge(ee),.O_support(es));
__FUNCTION__
integer n,j,yy[0:8],gx,gy,minx=9999,maxx=-9999,miny=9999,maxy=-9999;reg[31:0]prng=32'h58eaf71b;
initial begin
 for(n=0;n<20512;n=n+1)begin
  for(j=0;j<9;j=j+1)begin
   prng={prng[30:0],prng[31]^prng[21]^prng[1]^prng[0]};
   yy[j]=n<512?(n[j]?255:0):prng[7:0];ys[71-8*j-:8]=yy[j];ms[71-8*j-:8]=prng[15:8];
  end
  #1;
  gx=yy[2]+2*yy[5]+yy[8]-yy[0]-2*yy[3]-yy[6];
  gy=yy[6]+2*yy[7]+yy[8]-yy[0]-2*yy[1]-yy[2];
  if(grad!=={gx[10:0],gy[10:0]})$fatal(1,"balanced signed arithmetic differs");
  if({om,oe,os}!=={dm,de,ds} || {om,oe,os}!=={em,ee,es})$fatal(1,"guide branch differs");
  if(gx<minx)minx=gx;if(gx>maxx)maxx=gx;if(gy<miny)miny=gy;if(gy>maxy)maxy=gy;
 end
 if(minx!=-1020 || maxx!=1020 || miny!=-1020 || maxy!=1020)$fatal(1,"extreme range proof missing");
 $display("GRADIENT_MATH_PASS checks=%0d gx=%0d..%0d gy=%0d..%0d default_and_external_outputs_equal",n,minx,maxx,miny,maxy);$finish;
end
endmodule
'''
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def prepare_refs():
 V.mkdir(exist_ok=True)
 paths=[R/'validation/reference_v13/isp/stylize_v5_96.v',R/'validation/reference_v13/isp/style_guide_v8.v']
 ref=paths[0].read_text(encoding='utf-8');names=re.findall(r'(?m)^module\s+(\w+)',ref)+['style_guide_v8']
 for name in sorted(names,key=len,reverse=True):ref=re.sub(r'\b'+name+r'\b','reference_'+name,ref)
 (V/'reference_style.v').write_text(ref,encoding='utf-8')
 ref=paths[1].read_text(encoding='utf-8').replace('module style_guide_v8(','module reference_style_guide_v8(',1)
 (V/'reference_guide.v').write_text(ref,encoding='utf-8')
 return paths

def run(name,tb,top,params=None):
 d=V/name;d.mkdir(exist_ok=True);(d/'tb.sv').write_text(tb,encoding='utf-8')
 files=[H/'stylize_v5_96.v',H/'style_guide_v8.v',V/'reference_style.v',V/'reference_guide.v']
 c=subprocess.run([str(IV),'-g2012','-s',top,*[f'-P{top}.{k}={v}' for k,v in (params or {}).items()],'-o',str(d/'sim.vvp'),str(d/'tb.sv'),*[str(p) for p in files]],capture_output=True,text=True)
 (d/'compile.log').write_text(c.stdout+c.stderr,encoding='utf-8')
 if c.returncode:raise RuntimeError(c.stderr[-3000:])
 start=time.monotonic()
 with (d/'run.log').open('w',encoding='utf-8') as log:p=subprocess.run([str(VVP),str(d/'sim.vvp')],stdout=log,stderr=subprocess.STDOUT,text=True)
 s=(d/'run.log').read_text(encoding='utf-8');print(s[-2500:],flush=True)
 if p.returncode or ('STYLE_RETIME_PASS' not in s and 'GRADIENT_MATH_PASS' not in s):raise RuntimeError(name+' dynamic verification failed')
 out={'pass':True,'seconds':time.monotonic()-start,'parameters':params or {},'summary':[x for x in s.splitlines() if '_PASS' in x],'testbench_sha256':sha(d/'tb.sv')}
 (d/'result.json').write_text(json.dumps(out,indent=2),encoding='utf-8');return out

def main():
 p=argparse.ArgumentParser();p.add_argument('--full',action='store_true');p.add_argument('--quick',action='store_true');args=p.parse_args()
 refs=prepare_refs();sources={p.relative_to(R).as_posix():sha(p) for p in [H/'stylize_v5_96.v',H/'style_guide_v8.v',*refs]}
 # Symbolic coefficient identity, independently expanded over y0..y8.
 a=[-1,0,0,0,0,0,0,0,1];b=[0,0,1,0,0,0,-1,0,0];d=[0,0,0,-1,0,1,0,0,0];e=[0,-1,0,0,0,0,0,1,0]
 nx=[aa+bb+2*dd for aa,bb,dd in zip(a,b,d)];ny=[aa-bb+2*ee for aa,bb,ee in zip(a,b,e)]
 assert nx==[-1,0,1,-2,0,2,-1,0,1] and ny==[-1,-2,-1,0,0,0,1,2,1]
 proof={'gx_coefficients':nx,'gy_coefficients':ny,'pair_difference_range':[-255,255],'pair_sum_difference_range':[-510,510],'gradient_range':[-1020,1020],'signed_widths':[9,10,11],'fixed_latency_clocks':16}
 tests={}
 if not args.full:
  text=(H/'stylize_v5_96.v').read_text(encoding='utf-8');fn=re.search(r'function \[21:0\] balanced_gradient;.*?endfunction',text,re.S)[0]
  tests['math']=run('math',MATH.replace('__FUNCTION__',fn),'gradient_math_tb')
  for ext in [0,1]:tests[f'quick_ext{ext}']=run(f'quick_ext{ext}',TB,'style_retime_tb',{'W':64,'H':16,'F':12,'EXT':ext})
 else:tests['full720p_ext0']=run('full720p_ext0',TB,'style_retime_tb',{'W':1280,'H':720,'F':4,'EXT':0})
 assert all(sha(R/q)==h for q,h in sources.items()),'Source changed during test'
 report={'pass':True,'scope':'Cycle-exact production/reference RTL equality; no image algorithm, line-memory, original window output, valid/user/last/tag or LAT16 change. Not physical hardware validation.','tests':tests,'source_sha256':sources,'tool_sha256':sha(Path(__file__)),'mathematical_identity':proof,
 'coverage':['all four modes','dark colours, skin/bright, checker edges, random noise and isolated white/black pixels','row borders and valid bubbles','early and coincident SOF','mid-frame mode changes and varying external edge data','interrupted partial row/reset','every-cycle data/valid/user/last/ready comparison','window/C1/C2 tag equality','registered gradient known-value alignment']}
 name='full_result.json' if args.full else 'quick_result.json';(V/name).write_text(json.dumps(report,indent=2),encoding='utf-8');print('STYLE_RETIME_VERIFICATION_PASS',name,flush=True)
if __name__=='__main__':main()
