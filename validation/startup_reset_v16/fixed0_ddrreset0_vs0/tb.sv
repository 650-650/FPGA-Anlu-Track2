`timescale 1ns/1ps
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
