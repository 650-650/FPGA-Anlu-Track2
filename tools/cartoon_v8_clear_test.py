"""Full-width V7/V8 raw transport regression, including switches through all modes.
The guide may be a test stub because it cannot feed mode0's dedicated bypass.
"""
from pathlib import Path
import hashlib,json,re,subprocess,sys,time
sys.stdout.reconfigure(encoding='utf-8')
R=Path(__file__).resolve().parents[1];V=R/'validation/cartoon_v8';V.mkdir(exist_ok=True)
H=R/'user_source/hdl_source';S=H/'isp/stylize_v5_96.v';B=R.parent/'07_stylize_flame_fusion_v7_shadow_clean'
IV=Path(r'D:\anlu\iverilog\bin\iverilog.exe')
src=(B/'user_source/hdl_source/isp/stylize_v5_96.v').read_text(encoding='utf-8')
for name in sorted(re.findall(r'(?m)^module\s+(\w+)',src),key=len,reverse=True):src=re.sub(r'\b'+name+r'\b',name+'_v7_ref',src)
(V/'style_v7_reference.v').write_text(src,encoding='utf-8')
guide=H/'isp/style_guide_v8.v';guide_stub=not guide.exists()
if guide_stub:
 guide=V/'guide_stub.v';guide.write_text('module style_guide_v8(input[71:0]I_y2,I_fine,output[7:0]O_mag,output O_edge,O_support);assign O_mag=0;assign O_edge=0;assign O_support=0;endmodule\n',encoding='utf-8')
tb=r'''`timescale 1ns/1ps
module raw_v7_v8_tb;
 localparam W=1280,H=48,F=8;
 reg clk=0;always #5 clk=~clk;reg rst=0,v=0,u=0,l=0;reg[1:0]mode=0;reg[95:0]rgb=0;
 wire nv,nu,nl,ov,ou,ol;wire[95:0]np,op;integer f,y,x,raw_checks=0,sync_checks=0;
 stylize_v5_96 #(.IMG_WIDTH(W),.IMG_HEIGHT(H),.EXTERNAL_EDGE(0)) current(.I_clk(clk),.I_rst_n(rst),.I_mode(mode),.I_tvalid(v),.I_tuser(u),.I_tlast(l),.I_tdata(rgb),.I_tready(1'b1),.I_edge_data(96'd0),.O_tvalid(nv),.O_tuser(nu),.O_tlast(nl),.O_tdata(np));
 stylize_v5_96_v7_ref #(.IMG_WIDTH(W),.IMG_HEIGHT(H),.EXTERNAL_EDGE(0)) prior(.I_clk(clk),.I_rst_n(rst),.I_mode(mode),.I_tvalid(v),.I_tuser(u),.I_tlast(l),.I_tdata(rgb),.I_tready(1'b1),.I_edge_data(96'd0),.O_tvalid(ov),.O_tuser(ou),.O_tlast(ol),.O_tdata(op));
 task tick;begin @(posedge clk);#1;if(rst)begin
  sync_checks=sync_checks+1;if({nv,nu,nl}!=={ov,ou,ol})$fatal(1,"V7 sync changed");
  if(nv)begin
   if(current.mode_o!==prior.mode_o)$fatal(1,"frame mode alignment changed");
   if(current.mode_o==0)begin raw_checks=raw_checks+1;if(np!==op)$fatal(1,"raw pixels changed beat=%d",raw_checks);end
  end
 end @(negedge clk);end endtask
 initial begin
  repeat(4)tick;rst=1;
  for(f=0;f<F;f=f+1)begin
   mode=f%2==0?0:f==1?1:f==3?2:3;v=0;u=f%2==0;l=0;tick;u=0;repeat(52)tick;
   for(y=0;y<H;y=y+1)begin for(x=0;x<W/4;x=x+1)begin
    v=1;u=f%2==1&&y==0&&x==0;l=x==W/4-1;rgb={$random,$random,$random};tick;
    if((x+y+f)%29==0)begin v=0;u=0;l=0;tick;end
   end v=0;u=0;l=0;repeat(3)tick;end repeat(24)tick;
  end
  if(raw_checks!=W*H*4/4)$fatal(1,"raw coverage");
  $display("CARTOON_V8_RAW_PRESERVATION_PASS pixels=%0d sync_clocks=%0d full_width all_mode_switches gaps both_SOF",raw_checks*4,sync_checks);$finish;
 end
endmodule
'''
(V/'raw_v7_v8_tb.v').write_text(tb,encoding='utf-8');start=time.time()
for label,cmd in [('compile',[IV,'-g2012','-s','raw_v7_v8_tb','-o',V/'raw.vvp',V/'raw_v7_v8_tb.v',S,V/'style_v7_reference.v',guide]),('run',[IV.with_name('vvp.exe'),V/'raw.vvp'])]:
 p=subprocess.run(list(map(str,cmd)),cwd=V,capture_output=True,text=True,timeout=360)
 log=p.stdout+p.stderr;(V/('clear_'+label+'.log')).write_text(log,encoding='utf-8');assert p.returncode==0,(label,log[-2000:]);print(log[-1000:],flush=True)
 if label=='run':assert 'CARTOON_V8_RAW_PRESERVATION_PASS' in log
result={'pass':True,'pixels':245760,'full_width':1280,'guide_stub_used':guide_stub,'source_sha256':hashlib.sha256(S.read_bytes()).hexdigest(),'seconds':round(time.time()-start,2),'scope':'mode0 direct pixels and all-mode sync/control only; guide does not affect dedicated raw bypass'}
(V/'clear_result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
