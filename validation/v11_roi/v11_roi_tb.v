`timescale 1ns/1ps
module v11_roi_tb;
 localparam HT=1650,N=369600,LAG=2*HT+6;
 reg clk=0;always #5 clk=~clk;
 reg rst=0,vs=0,hs=0,de=0,overlay=0;reg[23:0]rgb=0;reg[7:0]control=0;
 wire[35:0] old_packet,new_packet;
 reg[35:0] input_data[0:N-1],expected_old[0:N-1],expected_new[0:N-1];
 integer i,j,checks=0,old_changes=0,new_changes=0,different=0;
 display_denoise_v11 #(.H_TOTAL(1650)) original_roi(
  .clk(clk),.rst_n(rst),.vs(vs),.hs(hs),.de(de),.rgb(rgb),.overlay(overlay),.control(control),
  .O_control(old_packet[35:28]),.O_overlay(old_packet[27]),.O_de(old_packet[26]),
  .O_hs(old_packet[25]),.O_vs(old_packet[24]),.O_rgb(old_packet[23:0]));
 display_denoise_v11 #(.H_TOTAL(1650),.ROI_Y0(176),.ROI_Y1(208)) moved_roi(
  .clk(clk),.rst_n(rst),.vs(vs),.hs(hs),.de(de),.rgb(rgb),.overlay(overlay),.control(control),
  .O_control(new_packet[35:28]),.O_overlay(new_packet[27]),.O_de(new_packet[26]),
  .O_hs(new_packet[25]),.O_vs(new_packet[24]),.O_rgb(new_packet[23:0]));
 initial begin
  $readmemh("input.hex",input_data);
  $readmemh("expected_old.hex",expected_old);$readmemh("expected_new.hex",expected_new);
  repeat(24)@(negedge clk);rst=1;
  for(i=0;i<N+LAG;i=i+1)begin
   @(negedge clk);
   if(i<N){control,overlay,de,hs,vs,rgb}=input_data[i];
   else begin control=0;overlay=0;de=0;hs=0;vs=0;rgb=0;end
   @(posedge clk);#1;
   if(i<LAG)begin
    if(old_packet!==36'd0 || new_packet!==36'd0)$fatal(1,"startup mismatch tick=%0d",i);
   end else begin
    j=i-LAG;checks=checks+1;
    if(old_packet!==expected_old[j])$fatal(1,"old ROI mismatch pixel=%0d actual=%h expected=%h",j,old_packet,expected_old[j]);
    if(new_packet!==expected_new[j])$fatal(1,"new ROI mismatch pixel=%0d actual=%h expected=%h",j,new_packet,expected_new[j]);
    if(old_packet!==input_data[j])old_changes=old_changes+1;
    if(new_packet!==input_data[j])new_changes=new_changes+1;
    if(old_packet!==new_packet)different=different+1;
   end
  end
  if(checks!=N || old_changes!=3 || new_changes!=3 || different!=6)$fatal(1,"wrong checks/events");
  $display("V11_MOVED_ROI_PASS packets=%0d old_repairs=%0d moved_repairs=%0d differences=%0d overlay_sketch_protected=1",checks,old_changes,new_changes,different);
  $finish;
 end
endmodule
