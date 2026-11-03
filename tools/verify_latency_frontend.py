from pathlib import Path
import subprocess,json,time,hashlib,sys,re
R=Path(__file__).resolve().parents[1]
H=R/'user_source/hdl_source'; V=R/'validation/latency_frontend'; V.mkdir(parents=True,exist_ok=True)
IV=Path(r'D:\anlu\iverilog\bin\iverilog.exe'); VVP=IV.with_name('vvp.exe')
tb=r'''`timescale 1ns/1ps
module frontend_tb;
reg clk=0,sys=0,ddr=0,hdmi=0;always #8.333 clk=~clk;always #10 sys=~sys;always #2.5 ddr=~ddr;always #6.667 hdmi=~hdmi;
reg rst=0,start=0,valid=0;reg[39:0]data=40'h8af39de801;
wire uv,uu,ul;wire[39:0]ud;
uial2axis #(.IMG_WIDTH(1280),.IMG_HEIGHT(720),.INPUT_DATA_WIDTH(40)) adapter(.I_native_clk(clk),.I_rst_n(rst),.I_data(data),.I_data_valid(valid),.I_data_start(start),.I_data_end(1'b0),.axis_tvalid(uv),.axis_tdata(ud),.axis_tuser(uu),.axis_tlast(ul));
wire pv,pu;wire[127:0]pd;
isp_top isp(.I_wb_allow(1'b1),.I_wb_relearn(1'b0),.I_mode_req(2'd0),.O_wb_locked(),.O_color_gain_r(),.O_color_gain_b(),.O_meter_data(),.O_meter_valid(),.O_meter_sof(),.axi4s_video_aclk(clk),.I_rst_n(rst),.I_tlast(ul),.I_tuser(uu),.I_tdata(ud),.I_tvalid(uv),.I_tdest(10'd0),.O_tready(1'b1),.O_tdata(pd),.O_tlast(),.O_tuser(pu),.O_tvalid(pv),.I_tready());
frame_latency_monitor mon(.sys_clk(sys),.cam_clk(clk),.ddr_clk(ddr),.hdmi_clk(hdmi),.rst_n(rst),.raw_user(uu),.raw_valid(uv),.raw_error(1'b0),.packed_user(pu),.input_overflow(1'b0),.write_start(1'b0),.write_slot(2'd0),.write_en(1'b0),.write_address(25'd0),.read_start(1'b0),.read_slot(2'd0),.read_en(1'b0),.read_address(25'd0),.read_return(1'b0),.read_fifo_reset(1'b0),.raw_hdmi_vs(1'b0),.final_hdmi_vs(1'b0),.final_hdmi_de(1'b0),.output_underflow(1'b0),.O_latency_us(),.O_frame_id(),.O_valid(),.O_repeat(),.O_skip());
integer rawcount=0,dcount=0,acount=0,scount=0,pcount=0,rawsofs=0,packsofs=0;
integer cyc=0,sofcyc=0;reg waiting=0;
reg pu_d=0;integer frame,line,c;
always @(posedge clk)if(rst)begin
 cyc=cyc+1;
 if(pu && !pu_d)begin sofcyc=cyc;waiting=1;end
 if(pv && waiting)begin waiting=0;$display("PACK_VALID_GAP frame=%0d gap=%0d clocks",packsofs,cyc-sofcyc);end
 if(uv)rawcount=rawcount+1;
 if(uu)rawsofs=rawsofs+1;
 if(isp.m_aixs_tvalid)dcount=dcount+1;
 if(isp.awb_O_tvalid)acount=acount+1;
 if(isp.sty_valid)scount=scount+1;
 if(pv)pcount=pcount+1;
 if(pu && !pu_d)begin packsofs=packsofs+1;$display("PACK_SOF %0d raw_id=%0d qcount=%0d raw_count=%0d t=%0t",packsofs,mon.raw_id,mon.qcount,mon.raw_count,$time);end
 pu_d<=pu;
end
initial begin
 repeat(20)@(negedge clk);rst=1;repeat(20)@(negedge clk);
 for(frame=0;frame<2;frame=frame+1)begin
  start=1;@(negedge clk);start=0;repeat(20)@(negedge clk);
  for(line=0;line<720;line=line+1)begin
   // RAW10 extractor: four groups in every ten camera clocks.
   for(c=0;c<1000;c=c+1)begin valid=(c<800 && c%10==0 || c<800 && c%10==2 || c<800 && c%10==4 || c<800 && c%10==6);@(negedge clk);end
   $display("ROW_DONE frame=%0d row=%0d raw=%0d packed=%0d",frame,line,rawcount,pcount);$fflush();
  end
  valid=0;repeat(10000)@(negedge clk);
  $display("FRAME %0d cumulative raw=%0d demosaic=%0d awb=%0d style=%0d packed=%0d rawid=%0d done=%0d good=%b faults=%b queue=%0d pack_id=%0d packgood=%b",frame,rawcount,dcount,acount,scount,pcount,mon.raw_id,mon.done_id,mon.done_good,mon.raw_fault_seen,mon.qcount,mon.pack_id,mon.pack_good);
 end
 if(pcount!=345600 || dcount!=460800 || acount!=460800 || scount!=460800 || rawcount!=460800 || rawsofs!=2 || packsofs!=2 || mon.pack_good!==1 || mon.raw_fault_seen!==0 || mon.done_good!==1)$fatal(1,"front end identity/count failure");
 $display("FRONTEND_IDENTITY_PASS raw=%0d packed=%0d",rawcount,pcount);$finish;
end
endmodule
// Timing-only one-clock read RAM models. Pixel values are not used to validate colour here.
module blk_mem_gen_zhenghe(input clka,wea,input[10:0]addra,input[31:0]dia,input clkb,input[10:0]addrb,output reg[31:0]dob);
reg[31:0]mem[0:2047];always @(posedge clka)if(wea)mem[addra]<=dia;always @(posedge clkb)dob<=mem[addrb];endmodule
module blk_mem_gen_demosaic(input clka,wea,input[10:0]addra,input[32:0]dia,input clkb,input[10:0]addrb,output reg[32:0]dob);
reg[32:0]mem[0:2047];always @(posedge clka)if(wea)mem[addra]<=dia;always @(posedge clkb)dob<=mem[addrb];endmodule
'''
if '--fast' in sys.argv:
    V=V/'gap_fast';V.mkdir(exist_ok=True)
    tb=tb.replace('line<720','line<8')
    tb=tb.replace('if(pcount!=345600 || dcount!=460800 || acount!=460800 || scount!=460800 || rawcount!=460800 || rawsofs!=2 || packsofs!=2 || mon.pack_good!==1 || mon.raw_fault_seen!==0 || mon.done_good!==1)$fatal(1,"front end identity/count failure");','if(packsofs!=2 || mon.pack_good!==1)$fatal(1,"front end SOF failure");')
if '--video' in sys.argv:
    V=V/'native_video';V.mkdir(exist_ok=True)
    tb=tb.replace('integer rawcount=0,',r'''
integer wcount0=0,wcount24=0,overflow0=0,overflow24=0;
wire we0,we24,ov0,ov24;wire[24:0]a0,a24;
video_in #(.INPUT_ALIGN_CYCLES(0)) vi0(.I_rst_n(rst),.I_camera_clk(clk),.I_camera_frame_start(pu),.I_camera_valid(pv),.I_camera_data(pd),.I_mipi_rx_error(1'b0),.I_ddr_clk(ddr),.I_display_pause(1'b0),.I_video_out_rd_busy(1'b0),.O_video_in_wr_busy(),.O_video_out_rp(),.O_ddr_user_wr_en(we0),.O_ddr_user_addr(a0),.O_ddr_user_wr_data(),.I_ddr_user_ready(1'b1),.O_observe_frame_start(),.O_observe_write_slot(),.O_observe_overflow(ov0));
video_in #(.INPUT_ALIGN_CYCLES(24)) vi24(.I_rst_n(rst),.I_camera_clk(clk),.I_camera_frame_start(pu),.I_camera_valid(pv),.I_camera_data(pd),.I_mipi_rx_error(1'b0),.I_ddr_clk(ddr),.I_display_pause(1'b0),.I_video_out_rd_busy(1'b0),.O_video_in_wr_busy(),.O_video_out_rp(),.O_ddr_user_wr_en(we24),.O_ddr_user_addr(a24),.O_ddr_user_wr_data(),.I_ddr_user_ready(1'b1),.O_observe_frame_start(),.O_observe_write_slot(),.O_observe_overflow(ov24));
always @(posedge ddr)if(rst)begin
 if(we0)wcount0=wcount0+1;
 if(we24)wcount24=wcount24+1;
end
always @(posedge clk)if(rst)begin if(ov0)overflow0=overflow0+1;if(ov24)overflow24=overflow24+1;end
integer rawcount=0,''')
    tb=tb.replace('$display("FRONTEND_IDENTITY_PASS',r'''if(wcount0!=pcount || wcount24!=pcount || overflow0 || overflow24)$fatal(1,"native input words differ packed=%0d a0=%0d a24=%0d overflow=%0d/%0d",pcount,wcount0,wcount24,overflow0,overflow24);
 $display("NATIVE_VIDEO_INPUT_PASS packed=%0d align0=%0d align24=%0d overflow=%0d/%0d",pcount,wcount0,wcount24,overflow0,overflow24);
 $display("FRONTEND_IDENTITY_PASS''')
if '--csi' in sys.argv:
    V=V/'csi_unpack';V.mkdir(exist_ok=True)
    tb=tb.replace('uial2axis #',r'''wire native_valid,native_start;wire[39:0]native_data;
raw10_unpacket_2lane unpack(.I_clk(clk),.I_rst_n(rst),.I_csi_frame_start(start),.I_csi_frame_end(1'b0),.I_csi_valid(valid),.I_csi_data(32'h1a2b3c4d),.I_camera_black_level(10'd0),.O_raw10_frame_start(native_start),.O_raw10_frame_end(),.O_raw10_valid(native_valid),.O_raw10_data(native_data));
uial2axis #''',1)
    tb=tb.replace('.I_data(data),.I_data_valid(valid),.I_data_start(start)', '.I_data(native_data),.I_data_valid(native_valid),.I_data_start(native_start)')
    tb=tb.replace('(c<800 && c%10==0 || c<800 && c%10==2 || c<800 && c%10==4 || c<800 && c%10==6)', '(c<800 && c%2==0)')
if '--single' in sys.argv:
    assert '--video' in sys.argv
    V=V/'single_fifo';V.mkdir(exist_ok=True)
    tb=re.sub(r'video_in #\(\.INPUT_ALIGN_CYCLES\(24\)\) vi24\(.*?\);', '',tb,flags=re.S)
    tb=tb.replace('always #6.667 hdmi=~hdmi;', '')
    tb=tb.replace('if(wcount0!=pcount || wcount24!=pcount || overflow0 || overflow24)', 'if(wcount0!=pcount || overflow0)')
    tb=tb.replace('$display("NATIVE_VIDEO_INPUT_PASS packed=%0d align0=%0d align24=%0d overflow=%0d/%0d",pcount,wcount0,wcount24,overflow0,overflow24);', '$display("NATIVE_VIDEO_INPUT_SINGLE_PASS packed=%0d align0=%0d overflow=%0d",pcount,wcount0,overflow0);')
(V/'frontend_tb.v').write_text(tb,encoding='utf-8')
files=[H/'isp/uial2axis.v',H/'isp/isp_top.v',H/'awb.v',H/'signal_delay_compact.v',H/'awb_line_memory.v',H/'isp/auto_black_96.v',H/'scene_color_control.v',H/'image_curve_rom.v',H/'isp/stylize_v5_96.v',H/'isp/style_guide_v8.v',H/'data_96bit_to_128bit.v',H/'frame_latency_monitor.v',H/'fusion_controls.v']
files+=list((H/'isp/demosaic_4x_2_0').glob('*.v'))
files += list((H/'isp/data128_96').glob('*.v'))
if '--video' in sys.argv:
    files += [H/'video_in.v',R/'user_source/ip_source/w128_d512_fifo/w128_d512_fifo.v',R/'user_source/ip_source/w128_d512_fifo/soft_fifo_al_4057d6b76aa6.v']
if '--csi' in sys.argv:files += [H/'isp/raw10_unpacket_2lane.v']
originals=files[:]
hashes={str(f.relative_to(R)):hashlib.sha256(f.read_bytes()).hexdigest()for f in originals}
for i,f in enumerate(files):
    if f.name=='demosaic.v':
        # TD accepts these malformed heading comments. Icarus does not.
        text=f.read_bytes().replace(b'/*//input',b'//input').replace(b'/*//output',b'//output')
        copy=V/'demosaic_comments_only.v';copy.write_bytes(text);files[i]=copy
t=time.time()
p=subprocess.run([str(IV),'-g2012','-s','frontend_tb','-o',str(V/'sim.vvp'),str(V/'frontend_tb.v'),*map(str,files)],capture_output=True,text=True)
(V/'compile.log').write_text(p.stdout+p.stderr,encoding='utf-8');print(p.stdout+p.stderr);assert p.returncode==0
print('RUNNING_NATIVE_FRONTEND',str(V),flush=True)
with (V/'run.log').open('w',encoding='utf-8') as log:
    # This host's clock can jump hours. Do not derive a subprocess deadline
    # from that clock. The active tool session supervises this finite bench.
    p=subprocess.Popen([str(VVP),'-i',str(V/'sim.vvp')],stdout=log,stderr=subprocess.STDOUT,text=True)
    rc=p.wait()
output=(V/'run.log').read_text(encoding='utf-8');print('\n'.join(output.splitlines()[-16:]),flush=True)
counts=re.search(r'FRONTEND_IDENTITY_PASS raw=(\d+) packed=(\d+)',output)
native_counts=re.search(r'NATIVE_VIDEO_INPUT_SINGLE_PASS packed=(\d+) align0=(\d+) overflow=(\d+)',output)
(V/'result.json').write_text(json.dumps({'pass':rc==0 and 'FRONTEND_IDENTITY_PASS' in output,'seconds_host_clock_may_jump':time.time()-t,'fast': '--fast' in sys.argv,'native_video': '--video' in sys.argv,'single_fifo':'--single' in sys.argv,'csi_unpack': '--csi' in sys.argv,'checked_raw_groups':int(counts[1]) if counts else None,'packed_words':int(counts[2]) if counts else None,'native_written_words_align0':int(native_counts[2]) if native_counts else None,'overflow_hits':int(native_counts[3]) if native_counts else None,'sof_to_valid_clocks':list(map(int,re.findall(r'PACK_VALID_GAP frame=\d+ gap=(\d+) clocks',output))),'testbench_sha256':hashlib.sha256((V/'frontend_tb.v').read_bytes()).hexdigest(),'scope':'production RAW adapter + whole ISP scheduling and optional CSI raw unpacker/native pixel FIFO; demosaic RAMs are timing-compatible one-clock models; no physical MIPI/DDR; demosaic comments only cleaned for Icarus; inactive HDMI clock disabled in single FIFO count test','source_sha256':hashes,'source_unchanged_during_test':hashes=={str(f.relative_to(R)):hashlib.sha256(f.read_bytes()).hexdigest()for f in originals}},indent=2),encoding='utf-8')
assert rc==0
