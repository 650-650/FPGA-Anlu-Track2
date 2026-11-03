`timescale 1ns/1ps
module sketch_rom_gate_tb;
 reg clk=0,enable=0;always #5 clk=~clk;
 reg[10:0]a=0,b=0;wire[7:0]qa,qb,qa2,qb2;reg[7:0]expected_a,expected_b,held_a,held_b;
 integer i,checks=0;
 gate_ink_rom_pair_01 dut01(clk,enable,a,b,qa,qb);
 gate_ink_rom_pair_23 dut23(clk,enable,a,b,qa2,qb2);
 PH1P_PHY_GSR GSR();
 function[7:0]oracle;
 input[10:0]address;integer level,mag,floor_value,gain,dm,ink;
 begin
  level=address>>8;mag=address&255;
  case(level)0:begin floor_value=64;gain=8;end 1:begin floor_value=32;gain=20;end
  3:begin floor_value=6;gain=80;end 4:begin floor_value=2;gain=128;end
  default:begin floor_value=12;gain=49;end endcase
  dm=mag>floor_value?mag-floor_value:0;ink=dm*gain/16;oracle=ink>255?255:ink;
 end endfunction
 initial begin
  #100;@(negedge clk);
  for(i=0;i<2048;i=i+1)begin
   enable=1;a=i;b=2047-i;expected_a=oracle(a);expected_b=oracle(b);
   @(posedge clk);#1;checks=checks+4;
   if(qa!==expected_a || qb!==expected_b || qa2!==expected_a || qb2!==expected_b)$fatal(1,"ROM_ENTRY_OR_LATENCY_FAIL a=%d b=%d",a,b);
   held_a=qa;held_b=qb;
   @(negedge clk);
   if(i%17==0)begin
    enable=0;a=(i+413)%2048;b=(i+1709)%2048;
    @(posedge clk);#1;checks=checks+4;
    if(qa!==held_a || qb!==held_b || qa2!==held_a || qb2!==held_b)$fatal(1,"ROM_CE_HOLD_FAIL address=%d",i);
    @(negedge clk);
   end
  end
  $display("GATE_PHYSICAL_ROM_PASS checks=%0d entries=2048 ports=4 levels5_7_default=1 one_clock_read=1 CE_hold=1",checks);$finish;
 end
endmodule
