`timescale 1ns/1ps
module cartoon_output_math_tb;
function[7:0] old_output;
 input[7:0]c,mag;input is_edge;input[2:0]level;reg[7:0]drop;
 begin
   if(!is_edge || level==0)drop=0;
   else if(level==1)drop=mag<64?(c>>3):(c>>2);
   else if(level==3)drop=mag<64?(c>>1):c-(c>>2);
   else if(level==4)drop=c;
   else drop=mag<64?(c>>2):(c>>1);
   old_output=c-drop;
 end endfunction
function[7:0] new_output;
 input[7:0]c,mag;input is_edge;input[2:0]level;reg[7:0]drop;
 begin
   drop=0;
   if(!is_edge || level==0)new_output=c;
   else if(level==4)new_output=8'd0;
   else if(level==3 && mag>=64)new_output=c>>2;
   else begin
    if(level==1)drop=mag<64?(c>>3):(c>>2);
    else if(level==3)drop=c>>1;
    else drop=mag<64?(c>>2):(c>>1);
    new_output=c-drop;
   end
 end endfunction
reg[7:0]c,mag,a,b;reg[2:0]level;reg edge_value;integer ci,li,ei,mi,checks=0;
 initial begin
  for(ci=0;ci<256;ci=ci+1)for(li=0;li<8;li=li+1)for(ei=0;ei<2;ei=ei+1)for(mi=0;mi<256;mi=mi+1)begin
   c=ci;level=li;edge_value=ei;mag=mi;
   a=old_output(c,mag,edge_value,level);b=new_output(c,mag,edge_value,level);checks=checks+1;
   if(a!==b)$fatal(1,"CARTOON_OUTPUT_EQ_FAIL c=%0d level=%0d edge=%0d mag=%0d old=%0d new=%0d",ci,li,ei,mi,a,b);
  end
  $display("CARTOON_OUTPUT_BYPASS_EQ_PASS checks=%0d colours=256 levels=8 edge_states=2 magnitudes=256",checks);$finish;
 end
endmodule
