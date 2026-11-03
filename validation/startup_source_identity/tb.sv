`timescale 1ns/1ps
module startup_sequence_tb;
 parameter MODE=0, DDR_HALF_PS=7500, PHASE_PS=0;
 reg sys=0,cam=0,ddr=0,hdmi=0;
 reg ddr_enabled=0,rst=1;
 always #10 sys=~sys;
 always #8.334 cam=~cam;
 initial begin #(PHASE_PS/1000.0);forever #(DDR_HALF_PS/1000.0)if(ddr_enabled)ddr=~ddr;end
 always #6.6665 hdmi=~hdmi;
 reg ru=0,rv=0,pu=0,pv=0;reg[127:0]pd=0;
 wire we;wire[24:0]wa;wire[127:0]wd;wire[1:0]rp,ws;
 wire wstart,overflow;
 video_in vi(.I_rst_n(rst),.I_camera_clk(cam),.I_camera_frame_start(pu),.I_camera_valid(pv),.I_camera_data(pd),
  .I_mipi_rx_error(1'b0),.I_ddr_clk(ddr),.I_display_pause(1'b0),.I_video_out_rd_busy(1'b0),
  .O_video_in_wr_busy(),.O_video_out_rp(rp),.O_ddr_user_wr_en(we),.O_ddr_user_addr(wa),.O_ddr_user_wr_data(wd),.I_ddr_user_ready(1'b1),
  .O_observe_frame_start(wstart),.O_observe_write_slot(ws),.O_observe_overflow(overflow));
 frame_latency_monitor #(.WIDTH(1280),.HEIGHT(1)) mon(
  .sys_clk(sys),.cam_clk(cam),.ddr_clk(ddr),.hdmi_clk(hdmi),.rst_n(rst),
  .raw_user(ru),.raw_valid(rv),.raw_error(1'b0),.packed_user(pu),.input_overflow(overflow),
  .write_start(wstart),.write_slot(ws),.write_en(we),.write_address(wa),
  .read_start(1'b0),.read_slot(2'd0),.read_en(1'b0),.read_address(25'd0),.read_return(1'b0),.read_fifo_reset(1'b0),
  .raw_hdmi_vs(1'b0),.final_hdmi_vs(1'b0),.final_hdmi_de(1'b0),.output_underflow(1'b0));
 integer source_frames=0,write_sofs=0,writes=0,meta_hits=0,frame,cy;
 reg [15:0] stored_frame[0:3];
 integer wrong_bindings,check_slot;
 always @(posedge ddr)if(rst)begin
  if(wstart)begin write_sofs=write_sofs+1;$display("WRITE_SOF source_pack=%0d local_claim=%0d cp=%0d slot=%0d",mon.pack_sequence,mon.claim_sequence+1,mon.cp_sequence,ws);end
  if(we)begin
   writes=writes+1;
   case(wa)
    0:stored_frame[0]=wd[127:112];7000000:stored_frame[1]=wd[127:112];
    14000000:stored_frame[2]=wd[127:112];21000000:stored_frame[3]=wd[127:112];
   endcase
  end
  if(mon.metadata_ready!=0)meta_hits=meta_hits+1;
 end
 task source_frame;input integer id,skip_pack;
  begin
   source_frames=source_frames+1;
   for(cy=0;cy<1000;cy=cy+1)begin
    @(negedge cam);ru=cy==0;rv=cy<320;pu=cy==64 && !skip_pack;pv=cy>=119 && cy<359 && !skip_pack;
    pd={16'(id),112'(cy-119)};
   end
   @(negedge cam);ru=0;rv=0;pu=0;pv=0;
  end
 endtask
 task report;
  begin
   repeat(1000)@(negedge cam);
   $display("STATE mode=%0d packs=%0d claims=%0d cp=%0d meta=%b complete=%b bad=%b qcount=%0d qfault=%0d pack_good=%0d writes=%0d",MODE,mon.pack_sequence,mon.claim_sequence,mon.cp_sequence,mon.metadata_ready,mon.write_complete,mon.slot_bad,mon.qcount,mon.queue_fault,mon.pack_good,writes);
  end
 endtask
 initial begin
  #1;rst=0;#999;rst=1;
  if(MODE==0 || MODE==2)ddr_enabled=1;
  for(frame=1;frame<=12;frame=frame+1)begin
   if((MODE==1 || MODE==3) && frame==3)ddr_enabled=1;
   if(MODE==4 && frame==2)ddr_enabled=1;
   source_frame(frame,MODE==2 && frame<=2);
  end
  report;
  if(MODE==0)begin
   if(mon.metadata_ready!==4'b1111 || mon.slot_bad!==0 || mon.write_complete!==4'b1111)$fatal(1,"normal control did not form valid metadata/full writes");
   $display("NORMAL_SEQUENCE_PASS");
  end
  if(MODE==1 || MODE==3)begin
   if(mon.pack_sequence!=12 || mon.claim_sequence!=10 || mon.metadata_ready!==4'b1111 || mon.write_complete!==4'b1111 || mon.slot_bad!==0)
    $fatal(1,"late DDR metadata did not recover autonomously");
   $display("LATE_DDR_AUTONOMOUS_METADATA_RECOVERY_PASS");
  end
  if(MODE==2)begin
   if(mon.qcount!=1 || !mon.queue_fault || mon.pack_good || mon.slot_bad!==4'b1111)$fatal(1,"missing packed SOF queue fault did not remain latched");
   $display("MISSING_PACKED_SOF_STICKY_FAULT_REPRODUCED");
  end
  if(MODE==4)begin
   wrong_bindings=0;
   for(check_slot=0;check_slot<4;check_slot=check_slot+1)begin
    $display("SOURCE_BINDING slot=%0d metadata_id=%0d actual_first_word_frame=%0d",check_slot,mon.slot_id[check_slot],stored_frame[check_slot]);
    if(mon.slot_id[check_slot]!==stored_frame[check_slot])wrong_bindings=wrong_bindings+1;
   end
   if(mon.metadata_ready!==4'b1111 || mon.slot_bad!==0 || mon.write_complete!==4'b1111 || wrong_bindings!=0)
    $fatal(1,"one lost DDR SOF caused a wrong source identity");
   $display("ONE_LOST_SOF_CORRECT_SOURCE_IDENTITY_PASS");
  end
  if(MODE==3)begin
   @(negedge cam);rst=0;ru=0;rv=0;pu=0;pv=0;
   repeat(64)@(negedge cam);rst=1;
   for(frame=1;frame<=12;frame=frame+1)source_frame(frame,0);
   report;
   if(mon.metadata_ready!==4'b1111 || mon.slot_bad!==0 || mon.write_complete!==4'b1111)$fatal(1,"warm reset did not recover metadata alignment");
   $display("WARM_RESET_RECOVERY_PASS");
  end
  $display("IDENTITY_CHECKS %0d",identity_checks);
  $display("STARTUP_SEQUENCE_AUDIT_PASS mode=%0d",MODE);$finish;
 end
 initial begin #3000000;$fatal(1,"watchdog");end

real origin_time[0:15],reset_epoch=0;
integer identity_checks=0,si,sid,age_error;
always @(posedge rst)reset_epoch=$realtime;
always @(posedge cam)if(rst && ru && rv)origin_time[source_frames%12==0?12:source_frames%12]=$realtime;
always @(negedge ddr)if(rst)begin
 for(si=0;si<4;si=si+1)if(mon.metadata_ready[si] && mon.write_complete[si] && !mon.slot_bad[si])begin
  identity_checks=identity_checks+1;sid=mon.slot_id[si];
  if(mon.slot_id[si]!==stored_frame[si])$fatal(1,"wrong apparently-valid frame identity slot=%0d metadata=%0d pixel=%0d",si,mon.slot_id[si],stored_frame[si]);
  if(sid>=1 && sid<=12)begin
   age_error=$rtoi(($itor(mon.slot_time[si])*1000.0-(origin_time[sid]-reset_epoch))/1000.0);
   if(age_error>2 || age_error< -2)$fatal(1,"wrong source timestamp id=%0d error=%0d",sid,age_error);
  end
 end
end

endmodule
