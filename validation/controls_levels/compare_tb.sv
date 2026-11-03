`timescale 1ns/1ps
module compare_tb;
reg clk=0;always #10 clk=~clk;
reg [3:0]keys=15,sw=15;wire nr,orr,no,oo,nw,ow;wire[7:0]nc,oc;wire[5:0]nt,ot;wire[11:0]levels;
fusion_controls #(.BOOT_CYCLES(6),.DEBOUNCE_CYCLES(3),.RESET_CYCLES(9),.K3_HOLD_CYCLES(100),.K4_HOLD_CYCLES(80)) n(
 .I_clk(clk),.I_keys_n(keys),.I_switches(sw),.O_system_rst_n(nr),.O_control(nc),.O_osd_enable(no),.O_wb_toggle(nw),.O_color_control(nt),.O_style_levels(levels));
legacy_controls #(.BOOT_CYCLES(6),.DEBOUNCE_CYCLES(3),.RESET_CYCLES(9),.K3_HOLD_CYCLES(100),.K4_HOLD_CYCLES(80)) o(
 .I_clk(clk),.I_keys_n(keys),.I_switches(sw),.O_system_rst_n(orr),.O_control(oc),.O_osd_enable(oo),.O_wb_toggle(ow),.O_color_control(ot));
integer checks=0,i,j;reg[31:0]lfsr=32'h9ac74b13;
always @(posedge clk)begin
 #1;checks=checks+1;
 if({nr,nc,no,nw,nt}!=={orr,oc,oo,ow,ot})$fatal(1,"V15 control behavior regressed at check=%0d",checks);
 for(j=0;j<4;j=j+1)if(levels[j*3+:3]>4)$fatal(1,"illegal five-level state");
end
initial begin
 repeat(30)@(negedge clk);
 for(i=0;i<1000;i=i+1)begin
  lfsr={lfsr[30:0],lfsr[31]^lfsr[21]^lfsr[1]^lfsr[0]};
  sw=lfsr[11:8];keys=lfsr[3:0];repeat(7+(lfsr[15:12]*8))@(negedge clk);
  keys=15;repeat(13)@(negedge clk);
 end
 $display("V15_CONTROL_CYCLE_EQUIVALENCE_PASS checks=%0d",checks);$finish;
end
endmodule
