"""Startup frame-generation regression and actual-VTC native transport test.

The isolated tests inject a complete known buffer to prove that latency VALID
is not lost merely because DDR starts after global reset. The transport test
uses native generated FIFOs and actual uivtc, controlled SOF lead55 (observed
full ISP interface shape), ALIGN0 and 3313-clock final VS/DE delay. This is not
physical DDR, DPHY, full ISP or board acceptance.
"""
from pathlib import Path
import importlib.util, subprocess, hashlib, json, time
R=Path(__file__).resolve().parents[1]
H=R/'user_source/hdl_source'; IP=R/'user_source/ip_source'
V=R/'validation/latency_startup'; IV=Path(r'D:\anlu\iverilog\bin\iverilog.exe'); VVP=IV.with_name('vvp.exe')
UNIT=r'''`timescale 1ns/1ps
module tb;
parameter DDR_RUN_RESET=0,VS_HIGH=0,EXPECT_FAIL=0;
reg sys=0,cam=0,ddr=0,hdmi=0,rst=1;
always #10 sys=~sys;always #8.333 cam=~cam;always #2.5 if(DDR_RUN_RESET || rst)ddr=~ddr;always #6.666 hdmi=~hdmi;
reg vs=VS_HIGH,de=0;
wire read_start;wire unused_busy,unused_ren;wire[24:0]unused_addr;wire[23:0]unused_rgb;
video_out vo(.I_rst_n(rst),.I_ddr_clk(ddr),.O_video_out_rd_busy(unused_busy),.I_video_in_wr_busy(1'b1),
 .I_video_out_rp(2'd0),.O_ddr_user_rd_en(unused_ren),.O_ddr_user_addr(unused_addr),
 .I_ddr_user_ready(1'b0),.I_ddr_user_rd_valid(1'b0),.I_ddr_user_rd_data(128'd0),
 .I_dsi_clk(hdmi),.I_video_vsync(~vs),.I_video_rd_en(1'b0),.O_vdieo_data(unused_rgb),.O_observe_read_start(read_start));
reg [3312:0]vp=0,dp=0;
always @(posedge hdmi)begin vp<={vp[3311:0],vs};dp<={dp[3311:0],de};end
reg ren=0;reg[24:0]addr=0;reg[7:0]rn=12;reg[7:0]retpipe=0;
always @(posedge ddr)begin
 retpipe<={retpipe[6:0],ren};
 if(read_start)begin rn<=0;ren<=0;addr<=0;end
 else if(rn<12)begin ren<=1;rn<=rn+1'b1;if(ren)addr<=addr+8;end
 else begin ren<=0;if(ren)addr<=addr+8;end
end
wire[31:0]delay;wire[15:0]id;wire valid,rep,skip;
frame_latency_monitor #(.WIDTH(16),.HEIGHT(4)) dut(.sys_clk(sys),.cam_clk(cam),.ddr_clk(ddr),.hdmi_clk(hdmi),.rst_n(rst),
 .raw_user(1'b0),.raw_valid(1'b0),.raw_error(1'b0),.packed_user(1'b0),.input_overflow(1'b0),
 .write_start(1'b0),.write_slot(2'd0),.write_en(1'b0),.write_address(25'd0),
 .read_start(read_start),.read_slot(2'd0),.read_en(ren),.read_address(addr),.read_return(retpipe[7]),.read_fifo_reset(1'b0),
 .raw_hdmi_vs(vs),.final_hdmi_vs(vp[3312]),.final_hdmi_de(dp[3312]),.output_underflow(1'b0),
 .O_latency_us(delay),.O_frame_id(id),.O_valid(valid),.O_repeat(rep),.O_skip(skip));
integer good=0,candidates=0,mismatches=0,i,f;
always @(posedge hdmi)if(rst)begin
 if(valid)good=good+1;
 if(dut.armed && dp[3312])begin
  candidates=candidates+1;
  if(dut.hd_sequence!=dut.hdmi_sequence)mismatches=mismatches+1;
 end
end
initial begin
 // Model legal physical power-on zero in V12's unreset FFs. V13's reset
 // intentionally overrides this model before the first DDR clock exists.
 vo.S_video_vsync_1d=0;vo.S_video_vsync_2d=0;vo.S_video_vsync_3d=0;
 #1;rst=0;#999;rst=1;#1;
 dut.claimed=4'b1111;dut.metadata_ready=4'b1111;dut.raw_complete=4'b1111;dut.write_complete=4'b1111;dut.slot_bad=0;
 // Inject the same complete 12-word fixture using V13's absolute counter
 // representation; its decoded relative words[] view is intentionally wire.
 for(i=0;i<4;i=i+1)begin dut.slot_claim[i]=1;dut.slot_id[i]=1;dut.slot_time[i]=0;dut.write_word_cursor[i]=dut.base_word_address(i)+22'd12;end
 for(f=0;f<4;f=f+1)begin
  repeat(32)@(negedge hdmi);vs=1;
  repeat(32)@(negedge hdmi);vs=0;
  repeat(400)@(negedge hdmi);
  repeat(64)begin @(negedge hdmi);de=1;end
  @(negedge hdmi);de=0;
  repeat(4000)@(negedge hdmi);
 end
 $display("STARTUP_RESULT ddr_reset=%d initial_vs=%d expect_fail=%d candidates=%d mismatches=%d valid_cycles=%d source=%d valid=%b",DDR_RUN_RESET,VS_HIGH,EXPECT_FAIL,candidates,mismatches,good,id,valid);
 if(EXPECT_FAIL && (good!=0 || mismatches!=candidates))$fatal(1,"legacy startup mismatch was not reproduced");
 if(!EXPECT_FAIL && (good==0 || mismatches!=0 || id!=1))$fatal(1,"fixed generation/source validation failed");
 $display("STARTUP_CASE_PASS");$finish;
end
initial begin #2000000;$fatal(1,"watchdog");end
endmodule
'''

def run_sim(name,tb,files,params=None,timeout=180):
 d=V/name;d.mkdir(parents=True,exist_ok=True); (d/'tb.sv').write_text(tb,encoding='utf-8')
 sha={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
 top='latency_video_tb' if 'module latency_video_tb' in tb else 'tb'
 command=[str(IV),'-g2012','-s',top,*[f'-P{top}.{k}={v}' for k,v in (params or {}).items()],'-o',str(d/'sim.vvp'),str(d/'tb.sv'),*[str(f) for f in files]]
 c=subprocess.run(command,capture_output=True,text=True,timeout=45);(d/'compile.log').write_text(c.stdout+c.stderr,encoding='utf-8')
 if c.returncode:raise RuntimeError(c.stderr[-3000:])
 start=time.monotonic()
 # Write stdout immediately so an interrupted host/session still leaves the
 # last completed source/read generation available for diagnosis.
 with (d/'run.log').open('w',encoding='utf-8') as log:
  p=subprocess.run([str(VVP),str(d/'sim.vvp')],stdout=log,stderr=subprocess.STDOUT,text=True,timeout=timeout)
 output=(d/'run.log').read_text(encoding='utf-8')
 result={'case':name,'returncode':p.returncode,'seconds':round(time.monotonic()-start,3),'source_sha256':sha,'sources_still_current':sha=={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in files},'summary':[x for x in output.splitlines() if 'RESULT' in x or 'PASS' in x]}
 (d/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False),flush=True)
 if p.returncode or not result['sources_still_current']:raise RuntimeError(name+' failed: '+output[-3000:])
 return result

def main():
 V.mkdir(parents=True,exist_ok=True)
 fifo=[IP/'w128_d512_fifo/w128_d512_fifo.v',IP/'w128_d512_fifo/soft_fifo_al_4057d6b76aa6.v']
 current=(H/'video_out.v').read_text(encoding='utf-8')
 a=current.index('    // The input is the inverse'); b=current.index('    assign S_video_frame_start',a)
 legacy=current[:a]+'''    always @(posedge I_ddr_clk) begin
        S_video_vsync_1d <= I_video_vsync;
        S_video_vsync_2d <= S_video_vsync_1d;
        S_video_vsync_3d <= S_video_vsync_2d;
    end

'''+current[b:]
 old=V/'legacy_video_out.v';old.write_text(legacy,encoding='utf-8')
 results=[]
 for fixed in [0,1]:
  for running,high in [(0,0),(1,0),(0,1),(1,1)]:
   name=f"{'fixed' if fixed else 'legacy'}_ddrreset{running}_vs{high}"
   results.append(run_sim(name,UNIT,[H/'video_out.v' if fixed else old,H/'frame_latency_monitor.v',H/'fusion_controls.v',*fifo],{'DDR_RUN_RESET':running,'VS_HIGH':high,'EXPECT_FAIL':int(not fixed and not running and not high)}))
 # Native transport test: reuse the existing verification fixture's DDR model,
 # actual generated FIFO RTL, ordered command path and external source IDs.
 spec=importlib.util.spec_from_file_location('video_fixture',R/'tools/latency_v12_video_verify.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 t=m.TB
 t=t.replace('reg out_vs=0,out_de=0;','''wire out_vs,out_de;
 uivtc #(.H_ActiveSize(1280),.H_FrameSize(1650),.H_SyncStart(1390),.H_SyncEnd(1430),.V_ActiveSize(H),.V_FrameSize(H+30),.V_SyncStart(H+5),.V_SyncEnd(H+10)) actual_vtc(.I_vtc_rstn(rst),.I_vtc_clk(hdmi),.O_vtc_vs(out_vs),.O_vtc_hs(),.O_vtc_de_valid(out_de),.O_vtc_user(),.O_vtc_last());''')
 t=t.replace('reg de1=0,de2=0,vs1=0,vs2=0;\nalways @(posedge hdmi)begin de1<=out_de;de2<=de1;vs1<=out_vs;vs2<=vs1;end','reg[3312:0] dp=0,vp=0;\nwire de2=dp[3312],vs2=vp[3312];\nalways @(posedge hdmi)begin dp<={dp[3311:0],out_de};vp<={vp[3311:0],out_vs};end')
 a=t.index('always @(negedge hdmi)if(FULL==1 && rst)begin');b=t.index('reg rd_d1=0',a);t=t[:a]+t[b:]
 a=t.index('integer frame,line,g,pidx,c,oy,ox;');t=t[:a]+r'''
integer frame,line,g,c;
initial begin
 for(c=0;c<4;c=c+1)wr_count[c]=0;
 for(c=0;c<16;c=c+1)begin claim_words[c]=0;claim_slot[c]=0;first_word[c]=0;end
 #1000;rst=1;
 for(frame=1;frame<=9;frame=frame+1)begin
  for(line=0;line<H;line=line+1)begin
   for(g=0;g<320;g=g+1)begin
    @(negedge cam);raw_valid=1;raw_user=line==0 && g==0;raw_data={4{24'h123456}};
   end
   @(negedge cam);raw_valid=0;raw_user=0;raw_data=0;repeat(1791)@(negedge cam);
  end
  repeat(63360)@(negedge cam);
 end
 repeat(300000)@(negedge cam);
 $display("VTC_RESULT valid=%0d updates=%0d id=%0d under=%0d claims=%0d words=%0d",mvalid,mvalid_frames,mid,under_hits,claims,total_wr);
 if(mvalid_frames<5 || under_hits!=0 || mid!=7)$fatal(1,"Native VTC flow/identity did not validate");
 for(c=1;c<9;c=c+1)if(claim_words[c]!=1920)$fatal(1,"Complete source write lost words");
 $display("ACTUAL_VTC_PASS");$finish;
end
always @(posedge ddr)if(rst && vo.S_video_frame_start)
 $display("READ_BEGIN seq=%d slot=%d snapshot=%b claimed=%b meta=%b raw=%b wr=%b bad=%b outstanding=%d prevwords=%d prevbad=%b",dut.read_sequence,rp,dut.snapshot_good,dut.claimed,dut.metadata_ready,dut.raw_complete,dut.write_complete,dut.slot_bad,dut.outstanding,dut.read_words,dut.session_bad);
initial begin #20000000;$fatal(1,"watchdog");end
endmodule
'''
 results.append(run_sim('native_vtc_lead55_align0',t,[*m.FILES,H/'vtc/uivtc.v'],{'FULL':1,'STYLE':0,'LEAD':55,'ALIGN':0,'LINES':8},timeout=240))
 report={'scope':__doc__,'results':results,'passed':True}
 (V/'result.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
 print('LATENCY_STARTUP_ALL_PASS',flush=True)
if __name__=='__main__':main()
