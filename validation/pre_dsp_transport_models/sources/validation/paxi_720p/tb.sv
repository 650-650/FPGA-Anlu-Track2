`timescale 1ns/1ps
module latency_video_tb;
parameter integer LEAD=0;
parameter integer FULL=0;
parameter integer STYLE=0,ALIGN=24,SPARSE=0;
parameter integer LINES=720;
parameter integer FAULT_VS_RETURN=0,STRONG_STALL=0;
localparam W=1280,H=LINES,N=W*H*3/16;
reg sys=0,cam=0,ddr=0,hdmi=0;
always #10 sys=~sys;
always #8.334 cam=~cam;
always #7.5 ddr=~ddr;
always #6.6665 hdmi=~hdmi;
reg rst=0;
reg raw_user=0,raw_valid=0;
reg [95:0] raw_data=0;
reg [95:0] pipe_data[0:63];
reg [63:0] pipe_valid=0,pipe_user=0;
reg [5:0] pipe_pointer=0;
wire[95:0] style_data;wire style_valid,style_user;
generate if(STYLE)begin
 stylize_v5_96 #(.IMG_WIDTH(W),.IMG_HEIGHT(H),.EXTERNAL_EDGE(0)) real_style(
 .I_clk(cam),.I_rst_n(rst),.I_mode(2'd0),.I_level(3'd2),.I_tlast(1'b0),.I_tuser(raw_user),.I_tdata(raw_data),
 .I_edge_data(96'd0),.I_tvalid(raw_valid),.I_tready(1'b1),.O_tlast(),.O_tuser(style_user),.O_tdata(style_data),.O_tvalid(style_valid),.O_tready());
end else begin
 assign style_data=pipe_data[pipe_pointer];assign style_valid=pipe_valid[63];assign style_user=pipe_user[63-LEAD];
end endgenerate
wire p_user,p_valid;wire[127:0] p_data;
data_96bit_to_128bit packer(.I_clk(cam),.I_rst_n(rst),
 .I_96b_frame_start(style_user),.I_96b_valid(style_valid),.I_96b_data(style_data),
 .O_128b_frame_start(p_user),.O_128b_valid(p_valid),.O_128b_data(p_data));
integer k;
always @(posedge cam)begin
 if(!rst)begin pipe_valid<=0;pipe_user<=0;pipe_pointer<=0;for(k=0;k<64;k=k+1)pipe_data[k]<=0;end
 else if(!STYLE)begin
  pipe_valid<={pipe_valid[62:0],raw_valid};pipe_user<={pipe_user[62:0],raw_user};
  pipe_data[pipe_pointer]<=raw_data;pipe_pointer<=pipe_pointer+1'b1;
 end
end
wire wr_en,wr_busy,rd_en,rd_busy,user_ready,ret_valid;
wire [24:0] wr_addr,rd_addr;
wire [127:0] wr_data,ret_data;
wire[1:0] rp;
video_in #(.INPUT_ALIGN_CYCLES(ALIGN)) vi(.I_rst_n(rst),.I_camera_clk(cam),.I_camera_frame_start(p_user),.I_camera_valid(p_valid),
 .I_camera_data(p_data),.I_mipi_rx_error(1'b0),.I_ddr_clk(ddr),.I_display_pause(1'b0),
 .I_video_out_rd_busy(FULL?rd_busy:1'b0),.O_video_in_wr_busy(wr_busy),.O_video_out_rp(rp),
 .O_ddr_user_wr_en(wr_en),.O_ddr_user_addr(wr_addr),.O_ddr_user_wr_data(wr_data),.I_ddr_user_ready(user_ready));
wire out_vs,out_de;
 uivtc #(.H_ActiveSize(1280),.H_FrameSize(1650),.H_SyncStart(1390),.H_SyncEnd(1430),.V_ActiveSize(H),.V_FrameSize(H+30),.V_SyncStart(H+5),.V_SyncEnd(H+10)) actual_vtc(.I_vtc_rstn(rst),.I_vtc_clk(hdmi),.O_vtc_vs(out_vs),.O_vtc_hs(),.O_vtc_de_valid(out_de),.O_vtc_user(),.O_vtc_last());
wire [23:0] output_rgb;
video_out vo(.I_rst_n(rst),.I_ddr_clk(ddr),.O_video_out_rd_busy(rd_busy),
 .I_video_in_wr_busy(wr_busy),.I_video_out_rp(rp),.O_ddr_user_rd_en(rd_en),.O_ddr_user_addr(rd_addr),
 .I_ddr_user_ready(user_ready),.I_ddr_user_rd_valid(ret_valid),.I_ddr_user_rd_data(ret_data),
 .I_dsi_clk(hdmi),.I_video_vsync(~out_vs),.I_video_rd_en(FULL?out_de:1'b0),.O_vdieo_data(output_rgb));
wire mc_en,mc_wren,mc_wend;wire[24:0]mc_addr;wire[2:0]mc_cmd;wire[127:0]mc_wdata;
wire[31:0] mc_mask;
wire mc_rdy,mc_wrdy;
mc_to_user_interface mc(.I_clk(ddr),.I_rst_n(rst),.I_ddr_user_wr_en(wr_en),
 .I_ddr_user_rd_en(FULL?rd_en:1'b0),.I_ddr_user_addr(wr_en?wr_addr:rd_addr),.I_ddr_user_wr_data(wr_data),
 .O_ddr_user_ready(user_ready),.O_ddr_user_rd_valid(ret_valid),.O_ddr_user_rd_data(ret_data),
 .O_mc_app_en(mc_en),.O_mc_app_addr(mc_addr),.O_mc_app_cmd(mc_cmd),.I_mc_app_rdy(mc_rdy),
 .O_mc_app_wdf_wren(mc_wren),.O_mc_app_wdf_data(mc_wdata),.O_mc_app_wdf_end(mc_wend),.O_mc_app_wdf_mask(mc_mask),
 .I_mc_app_wdf_rdy(mc_wrdy),.I_mc_app_rd_data(rdata),.I_mc_app_rd_data_end(rlast),.I_mc_app_rd_data_valid(rvalid));
wire[127:0]rdata;wire rvalid,rlast;
ph1p35_324_ddr_wrapper actual_ddr_wrapper(
 .I_sys_clk(ddr),.I_sys_rst_n(rst),.O_ddr_clk(),.O_init_calib_complete(),
 .I_mc_app_addr(mc_addr),.I_mc_app_cmd(mc_cmd),.I_mc_app_en(mc_en),
 .I_mc_app_wdf_data(mc_wdata),.I_mc_app_wdf_end(mc_wend),.I_mc_app_wdf_mask(mc_mask[15:0]),.I_mc_app_wdf_wren(mc_wren),
 .O_mc_app_rd_data(rdata),.O_mc_app_rd_data_end(rlast),.O_mc_app_rd_data_valid(rvalid),.O_mc_app_rdy(mc_rdy),.O_mc_app_wdf_rdy(mc_wrdy));
function integer addr_slot;input[24:0] a;begin addr_slot=a<7000000?0:a<14000000?1:a<21000000?2:3;end endfunction
integer packed_words=0,wr_count[0:3],total_wr=0,claims=0;
integer full_hits=0,under_hits=0,read_sessions=0,read_requests=0;
integer mismatch=0,identity_mismatch=0,checked_pixels=0,first_errors=0;
integer claim_words[0:15],claim_slot[0:15],claim_frame;
reg[127:0]first_word[0:15];
reg [31:0] delay_us;wire[31:0]measured;wire[15:0]mid;wire mvalid,mrepeat,mskip;
reg[3312:0] dp=0,vp=0;
wire de2=dp[3312],vs2=vp[3312];
always @(posedge hdmi)begin dp<={dp[3311:0],out_de};vp<={vp[3311:0],out_vs};end
wire input_full=vi.U_w128_d512_fifo.full_flag;
wire output_under=vo.S_fifo_rd_en && vo.S_fifo_emtpy;
frame_latency_monitor #(.WIDTH(W),.HEIGHT(H)) dut(.sys_clk(sys),.cam_clk(cam),.ddr_clk(ddr),.hdmi_clk(hdmi),.rst_n(rst),
 .raw_user(raw_user),.raw_valid(raw_valid),.raw_error(1'b0),.packed_user(p_user),.input_overflow(vi.O_observe_overflow),
 .write_start(vi.S_frame_start),.write_slot(vi.S_video_in_wp),.write_en(wr_en),.write_address(wr_addr),
 .read_start(FULL?vo.S_video_frame_start:1'b0),.read_slot(rp),.read_en(FULL?rd_en:1'b0),.read_address(rd_addr),
 .read_return(ret_valid),.read_fifo_reset(vo.O_observe_fifo_reset),.raw_hdmi_vs(out_vs),.final_hdmi_vs(vs2),.final_hdmi_de(FULL?de2:1'b0),
 .output_underflow(output_under),.O_latency_us(measured),.O_frame_id(mid),.O_valid(mvalid),.O_repeat(mrepeat),.O_skip(mskip));
integer active_claim=-1;
realtime capture_ns[0:15],first_display_ns=0.0;
integer captures=0,timestamp_checks=0,expected_us;
always @(posedge cam)if(rst)begin
 if(raw_user && raw_valid)begin captures=captures+1;capture_ns[captures]=$realtime;end
 if(p_valid)packed_words=packed_words+1;
 if(p_valid && input_full)full_hits=full_hits+1;
end
always @(posedge ddr)if(rst)begin
 if(vi.S_frame_start)begin
  if(active_claim>=0)$display("WRITE_FRAME index=%0d slot=%0d words=%0d first=%h",active_claim,claim_slot[active_claim],claim_words[active_claim],first_word[active_claim]);
  active_claim=claims;claim_slot[claims]=vi.S_video_in_wp;claim_words[claims]=0;first_word[claims]=0;claims=claims+1;
 end
 if(wr_en)begin
  total_wr=total_wr+1;wr_count[addr_slot(wr_addr)]=wr_count[addr_slot(wr_addr)]+1;
  if(active_claim>=0)begin if(claim_words[active_claim]==0)first_word[active_claim]=wr_data;claim_words[active_claim]=claim_words[active_claim]+1;end
 end
 if(FULL && vo.S_video_frame_start)begin read_sessions=read_sessions+1;read_requests=0;end
 if(FULL && rd_en)read_requests=read_requests+1;
end
integer oh=0,ov=0,out_frame=0,display_index=0,expected_frame=0;
integer mvalid_frames=0,observed_updates=0;
reg old_valid=0;reg[15:0] old_mid=0;
reg rd_d1=0,rd_d2=0;integer output_pixel=0,stable_frame=-1;
reg [23:0] wanted;reg[3:0] seen_id;
always @(posedge hdmi)begin
 if(FULL && de2 && first_display_ns==0.0)first_display_ns=$realtime;
 if(output_under)under_hits=under_hits+1;
 rd_d1<=out_de;rd_d2<=rd_d1;
 #1;
 if(FULL && rst && (FULL==2 || out_frame>=3) && rd_d2)begin
  // Pixel identity encoded in high nibble; coordinate in low twenty bits.
  seen_id=output_rgb[23:20];
  if(output_pixel==0)begin stable_frame=seen_id;expected_frame=seen_id;end
  wanted={expected_frame[3:0],output_pixel[19:0]};
  checked_pixels=checked_pixels+1;
  if(output_rgb!==wanted)begin mismatch=mismatch+1;if(first_errors<8)begin $display("PIXEL_MISMATCH f=%0d p=%0d got=%h expected=%h",out_frame,output_pixel,output_rgb,wanted);first_errors=first_errors+1;end end
  if(seen_id!==expected_frame[3:0])identity_mismatch=identity_mismatch+1;
  if(output_pixel==W*H-1)output_pixel=0;else output_pixel=output_pixel+1;
 end
 if(FULL && mvalid && (!old_valid || mid!=old_mid))begin
  mvalid_frames=mvalid_frames+1;observed_updates=observed_updates+1;
  if(FULL==2)begin
   if(mid!=1 || first_display_ns==0.0)$fatal(1,"same-frame identity did not match completed source1");
   expected_us=(first_display_ns-capture_ns[mid])/1000.0;
   if(measured+2<expected_us || measured>expected_us+2)$fatal(1,"physical fixture timestamp mismatch got=%0d expected=%0d",measured,expected_us);
   timestamp_checks=timestamp_checks+1;
  end
  $display("MEASUREMENT id=%0d us=%0d repeat=%0d skip=%0d",mid,measured,mrepeat,mskip);
 end
 old_valid=mvalid;old_mid=mid;
end

integer frame,line,g,c,p;
initial begin
 for(c=0;c<4;c=c+1)wr_count[c]=0;
 for(c=0;c<16;c=c+1)begin claim_words[c]=0;claim_slot[c]=0;first_word[c]=0;end
 #1000;rst=1;
 for(frame=1;frame<=9;frame=frame+1)begin
  for(line=0;line<H;line=line+1)begin
   for(g=0;g<320;g=g+1)begin
    @(negedge cam);raw_valid=1;raw_user=line==0 && g==0;for(p=0;p<4;p=p+1)raw_data[95-24*p-:24]={frame[3:0],20'(line*W+g*4+p)};
   end
   @(negedge cam);raw_valid=0;raw_user=0;raw_data=0;repeat(679)@(negedge cam);
  end
  repeat(280000)@(negedge cam);
 end
 repeat(3000000)@(negedge cam);
 $display("VTC_RESULT valid=%0d updates=%0d id=%0d under=%0d claims=%0d words=%0d",mvalid,mvalid_frames,mid,under_hits,claims,total_wr);
 if(mvalid_frames<5 || (!FAULT_VS_RETURN && under_hits!=0))$fatal(1,"Native VTC flow/identity did not validate");
 for(c=1;c<9;c=c+1)if(claim_words[c]!=N)$fatal(1,"Complete source write lost words");
 if(checked_valid<4 || checked_hud<4)$fatal(1,"Too few externally verified full frames");
 
bad_pixel_frames=0;
for(verify_init=1;verify_init<512;verify_init=verify_init+1)begin
 if(verified_pixel_count[verify_init]!=0 && verified_pixel_errors[verify_init]!=0)begin
  bad_pixel_frames=bad_pixel_frames+1;
  if(verified_valid[verify_init])$fatal(1,"bad pixel frame was marked VALID seq=%0d",verify_init);
 end
end
if(!STRONG_STALL && !FAULT_VS_RETURN && output_fifo_overflows!=0)$fatal(1,"normal transport overflowed output FIFO");
if(STRONG_STALL && (output_fifo_overflows==0 || bad_pixel_frames==0))$fatal(1,"strong-stall overflow fixture was not exercised");
$display("PAXI_PIXEL_SUMMARY valid_frames=%0d bad_pixel_frames_rejected=%0d output_fifo_overflows=%0d",checked_valid,bad_pixel_frames,output_fifo_overflows);
if(actual_ddr_wrapper.u_ddr2.split_aw_first==0 || actual_ddr_wrapper.u_ddr2.split_w_first==0 || actual_ddr_wrapper.u_ddr2.ready_mismatch==0)
 $fatal(1,"PAXI independent channel conditions were not exercised");
if(FAULT_VS_RETURN && (!actual_ddr_wrapper.u_ddr2.fault_injected || actual_ddr_wrapper.u_ddr2.returns_during_fifo_reset==0))
 $fatal(1,"late-return/FIFO-reset negative fixture was not exercised");
$display("PAXI_PROTOCOL_COUNTS AW=%0d W=%0d commits=%0d AR=%0d R=%0d aw_first=%0d w_first=%0d blocked_AR_with_AWready=%0d returns_in_reset=%0d",actual_ddr_wrapper.u_ddr2.aw_count,actual_ddr_wrapper.u_ddr2.w_count,actual_ddr_wrapper.u_ddr2.write_count,actual_ddr_wrapper.u_ddr2.ar_count,actual_ddr_wrapper.u_ddr2.return_count,actual_ddr_wrapper.u_ddr2.split_aw_first,actual_ddr_wrapper.u_ddr2.split_w_first,actual_ddr_wrapper.u_ddr2.ready_mismatch,actual_ddr_wrapper.u_ddr2.returns_during_fifo_reset);

 $display("PAXI_TRANSPORT_PASS source_frames=9 measured=%0d hud=%0d",checked_valid,checked_hud);$finish;
end
always @(posedge ddr)if(rst && vo.S_video_frame_start)
 $display("READ_BEGIN seq=%d slot=%d snapshot=%b claimed=%b meta=%b raw=%b wr=%b bad=%b outstanding=%d prevwords=%d prevbad=%b",dut.read_sequence,rp,dut.snapshot_good,dut.claimed,dut.metadata_ready,dut.raw_complete,dut.write_complete,dut.slot_bad,dut.outstanding,dut.read_words,dut.session_bad);
initial begin #250000000;$fatal(1,"watchdog");end

reg oracle_old_valid=0;
integer ext_pixel=0,checked_valid=0,checked_hud=0;
integer origin_by_sequence[0:511];
realtime final_start_ns[0:511];
reg raw_vs_prev=0,final_vs_prev=0,raw_first_pending=0,final_first_pending=0;
integer seq,oracle_age;
always @(posedge hdmi)begin
 // Native VTC emits DE while its internal reset holds h/v counters at zero.
 // Start an independent frame at an observed VS edge; counting pixels from
 // global reset includes those startup cycles and drifts by a partial row.
 if(rst && raw_vs_prev && !out_vs)raw_first_pending=1;
 if(rst && final_vs_prev && !vs2)final_first_pending=1;
 raw_vs_prev=out_vs;final_vs_prev=vs2;
 if(rst && de2 && final_first_pending)begin
  final_start_ns[dut.hdmi_sequence]=$realtime;final_first_pending=0;
 end
 #1;
 if(rst && rd_d2)begin
  if(raw_first_pending)begin
   origin_by_sequence[dut.hdmi_sequence]=output_rgb[23:20];
   raw_first_pending=0;
   $display("PIXEL_ORIGIN seq=%0d id=%0h first_rgb=%h",dut.hdmi_sequence,output_rgb[23:20],output_rgb);
  end
 end
 if(rst && mvalid && !oracle_old_valid)begin
  seq=dut.pending_sequence;
   verified_valid[seq]=1;
   if(seq==actual_ddr_wrapper.u_ddr2.fault_old_sequence || seq==actual_ddr_wrapper.u_ddr2.fault_new_sequence)
    $fatal(1,"late/reset response generation was incorrectly declared VALID seq=%0d",seq);
   if(verified_pixel_count[seq]!=W*H || verified_pixel_errors[seq]!=0)
    $fatal(1,"VALID frame pixel mismatch seq=%0d count=%0d errors=%0d",seq,verified_pixel_count[seq],verified_pixel_errors[seq]);
   $display("PIXEL_SCOREBOARD_PASS seq=%0d pixels=%0d",seq,verified_pixel_count[seq]);
  if(mid!==origin_by_sequence[seq])$fatal(1,"Valid frame ID differs from actual DDR pixel origin seq=%0d id=%0d rgb_id=%0d",seq,mid,origin_by_sequence[seq]);
  oracle_age=(final_start_ns[seq]-capture_ns[mid])/1000.0;
  if(measured+2<oracle_age || measured>oracle_age+2)$fatal(1,"Real event time mismatch got=%0d expected=%0d",measured,oracle_age);
  checked_valid=checked_valid+1;
  $display("EXTERNAL_ORACLE_PASS seq=%0d id=%0d us=%0d event_us=%0d",seq,mid,measured,oracle_age);
 end
 if(rst && actual_vtc.O_vtc_user && mvalid)begin
  if(dut.O_status!==0)$fatal(1,"Valid HUD snapshot status nonzero");
  checked_hud=checked_hud+1;
 end
 oracle_old_valid=mvalid;
end


integer bad_pixel_frames=0;
integer verified_pixel_count[0:511],verified_pixel_errors[0:511];
reg verified_valid[0:511];
integer verify_init,verify_index=0,verify_seq=0;
integer output_fifo_overflows=0,max_outstanding=0;
integer session_fifo_overflows=0,session_reset_returns=0;
always @(posedge ddr)if(rst)begin
 if(ret_valid && vo.U_w128_d512_fifo.full_flag)begin
  output_fifo_overflows=output_fifo_overflows+1;
  session_fifo_overflows=session_fifo_overflows+1;
  if(output_fifo_overflows<9)$display("OUTPUT_FIFO_OVERFLOW readseq=%0d fifo_words=%0d outstanding=%0d",dut.read_sequence,vo.S_fifo_wr_num,dut.outstanding);
 end
 if(dut.outstanding>max_outstanding)max_outstanding=dut.outstanding;
 if(ret_valid && vo.S_fifo_rst)session_reset_returns=session_reset_returns+1;
 if(vo.S_video_frame_start)begin
  $display("PAXI_READ_SNAPSHOT seq=%0d read_en=%0d return=%0d outstanding=%0d words=%0d bad=%0d fifo_overflows=%0d reset_returns=%0d",dut.read_sequence,rd_en,ret_valid,dut.outstanding,dut.read_words,dut.session_bad,session_fifo_overflows,session_reset_returns);
  session_fifo_overflows=0;session_reset_returns=0;
 end
end
reg verify_pending=0,verify_vs=0;
reg [3:0] verify_id;
reg [23:0] verify_wanted;
always @(posedge hdmi)if(rst && dut.pending && dut.hv_sequence==dut.pending_sequence && !dut.completing_frame && !dut.incomplete_boundary)begin
 #1;
 if(!mvalid)$display("PAXI_REJECTED seq=%0d id=%0d status=%02h reason=%04h",dut.pending_sequence,mid,dut.O_status,dut.O_debug_reason);
end
initial for(verify_init=0;verify_init<512;verify_init=verify_init+1)begin
 verified_pixel_count[verify_init]=0;verified_pixel_errors[verify_init]=0;
 verified_valid[verify_init]=0;
end
always @(posedge hdmi)begin
 if(rst && verify_vs && !out_vs)verify_pending=1;
 verify_vs=out_vs;
 #1;
 if(rst && rd_d2)begin
  if(verify_pending)begin verify_seq=dut.hdmi_sequence;verify_index=0;verify_id=output_rgb[23:20];verify_pending=0;end
  if(verify_seq!=0 && verify_index<W*H)begin
   verify_wanted={verify_id,verify_index[19:0]};
   verified_pixel_count[verify_seq]=verified_pixel_count[verify_seq]+1;
   if(output_rgb!==verify_wanted)begin
    verified_pixel_errors[verify_seq]=verified_pixel_errors[verify_seq]+1;
    if(verified_pixel_errors[verify_seq]<5)$display("PAXI_PIXEL_ERROR seq=%0d pixel=%0d got=%h wanted=%h fifo_overflows=%0d max_outstanding=%0d",verify_seq,verify_index,output_rgb,verify_wanted,output_fifo_overflows,max_outstanding);
   end
   verify_index=verify_index+1;
  end
 end
end

endmodule
