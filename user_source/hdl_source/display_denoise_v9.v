// Display-only, centered one-pixel cross. Detection inputs are upstream.
// Sampled input edge j corresponds to output edge j+H_TOTAL+5 on every page.
// The middle-row packet supplies RGB AND every output sideband.
module display_denoise_v9 #(
 parameter H_TOTAL=1650,
 parameter TH_DARK=32,TH_BRIGHT=16,MAX_CORRECTION=6
)(
 input clk,rst_n,vs,hs,de,input [23:0] rgb,input overlay,input [7:0] control,
 output O_vs,O_hs,O_de,output reg [23:0] O_rgb,
 output O_overlay,output [7:0] O_control
);
 localparam AB=$clog2(H_TOTAL),MEM_DEPTH=1<<AB;
 localparam WB=$clog2(2*H_TOTAL+3);
 wire [35:0] packet={control,overlay,de,hs,vs,rgb};
 reg [AB-1:0] pointer;
 wire [AB-1:0] ahead=pointer==H_TOTAL-1?0:pointer+1'b1;
 reg [WB-1:0] warm;
 wire [35:0] row1_q,row2_q;
 // An address is read one clock before its next write, avoiding mixed-port
 // same-address semantics. The shift registers below supply the missing tick.
 display_denoise_line_v9 #(.ADDR_BITS(AB),.MEM_DEPTH(MEM_DEPTH)) u_line1(
  .clk(clk),.write_address(pointer),.read_address(ahead),.data_in(packet),.data_out(row1_q));
 display_denoise_line_v9 #(.ADDR_BITS(AB),.MEM_DEPTH(MEM_DEPTH)) u_line2(
  .clk(clk),.write_address(pointer),.read_address(ahead),
  .data_in(warm>=H_TOTAL?row1_q:36'd0),.data_out(row2_q));
 reg [35:0] middle_a,middle_b,middle_c,upper_a,upper_b,bottom_a,bottom_b;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   pointer<=0;warm<=0;middle_a<=0;middle_b<=0;middle_c<=0;
   upper_a<=0;upper_b<=0;bottom_a<=0;bottom_b<=0;
  end else begin
   pointer<=pointer==H_TOTAL-1?0:pointer+1'b1;
   if(warm<2*H_TOTAL+2)warm<=warm+1'b1;
   middle_a<=warm>=H_TOTAL?row1_q:36'd0;
   middle_b<=middle_a;middle_c<=middle_b;
   upper_a<=warm>=2*H_TOTAL?row2_q:36'd0;upper_b<=upper_a;
   bottom_a<=packet;bottom_b<=bottom_a;
  end
 end
 wire [35:0] center=middle_b;
 wire [35:0] neighbour[0:3];
 assign neighbour[0]=middle_c; // left
 assign neighbour[1]=middle_a; // right
 assign neighbour[2]=upper_b;  // up
 assign neighbour[3]=bottom_b; // down
 wire selected=center[35:33]==0 || (center[35:33]==1 && center[32:31]==0);
 wire [9:0] luma_sum={2'd0,center[23:16]}+{1'b0,center[15:8],1'b0}+{2'd0,center[7:0]};
 wire [7:0] luma=luma_sum[9:2];
 wire [7:0] drop=luma<=64?0:(luma-64)>>3;
 wire [7:0] threshold=drop>=TH_DARK-TH_BRIGHT?TH_BRIGHT:TH_DARK-drop;
 wire [3:0] valid_neighbour,accepted;
 wire complete_window=center[26] && !center[27] && selected && (&valid_neighbour);
 function [7:0] rgb_distance;
  input [23:0] a,b;
  reg [7:0] dr,dg,db,m;
  begin
   dr=a[23:16]>b[23:16]?a[23:16]-b[23:16]:b[23:16]-a[23:16];
   dg=a[15:8]>b[15:8]?a[15:8]-b[15:8]:b[15:8]-a[15:8];
   db=a[7:0]>b[7:0]?a[7:0]-b[7:0]:b[7:0]-a[7:0];
   m=dr>dg?dr:dg;rgb_distance=m>db?m:db;
  end
 endfunction
 genvar g;
 generate for(g=0;g<4;g=g+1)begin:gate_neighbour
  assign valid_neighbour[g]=neighbour[g][26] && !neighbour[g][27] && neighbour[g][35:31]==center[35:31];
  assign accepted[g]=complete_window && rgb_distance(center[23:0],neighbour[g][23:0])<=threshold;
 end endgenerate
 reg [23:0] center1,center2,chosen1[0:3],rgb3;
 reg [10:0] sum2_r,sum2_g,sum2_b;
 reg [11:0] meta[0:3];
 integer k;
 function [10:0] channel_sum;
  input [7:0] c,a,b,d,e;
  reg [8:0] ab,de_sum;
  reg [9:0] neighbours_sum;
  begin
   ab={1'b0,a}+{1'b0,b};de_sum={1'b0,d}+{1'b0,e};
   neighbours_sum={1'b0,ab}+{1'b0,de_sum};
   channel_sum={1'b0,c,2'b00}+11'd4+{1'b0,neighbours_sum};
  end
 endfunction
 function [7:0] limited;
  input [7:0] original,filtered;
  reg [8:0] low,high;
  begin
   low=original>MAX_CORRECTION?{1'b0,original}-MAX_CORRECTION:0;
   high=original<255-MAX_CORRECTION?{1'b0,original}+MAX_CORRECTION:255;
   limited=filtered<low?low[7:0]:filtered>high?high[7:0]:filtered;
  end
 endfunction
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   center1<=0;center2<=0;sum2_r<=0;sum2_g<=0;sum2_b<=0;rgb3<=0;O_rgb<=0;
   for(k=0;k<4;k=k+1)begin chosen1[k]<=0;meta[k]<=0;end
  end else begin
   center1<=center[23:0];
   for(k=0;k<4;k=k+1)begin
    chosen1[k]<=accepted[k]?neighbour[k][23:0]:center[23:0];
   end
   meta[0]<=center[35:24];meta[1]<=meta[0];meta[2]<=meta[1];meta[3]<=meta[2];
   center2<=center1;
   sum2_r<=channel_sum(center1[23:16],chosen1[0][23:16],chosen1[1][23:16],chosen1[2][23:16],chosen1[3][23:16]);
   sum2_g<=channel_sum(center1[15:8],chosen1[0][15:8],chosen1[1][15:8],chosen1[2][15:8],chosen1[3][15:8]);
   sum2_b<=channel_sum(center1[7:0],chosen1[0][7:0],chosen1[1][7:0],chosen1[2][7:0],chosen1[3][7:0]);
   rgb3<={limited(center2[23:16],sum2_r[10:3]),limited(center2[15:8],sum2_g[10:3]),limited(center2[7:0],sum2_b[10:3])};
   O_rgb<=rgb3;
  end
 end
 assign O_control=meta[3][11:4];assign O_overlay=meta[3][3];
 assign O_de=meta[3][2];assign O_hs=meta[3][1];assign O_vs=meta[3][0];
endmodule

(* keep_hierarchy="true" *)
module display_denoise_line_v9 #(parameter ADDR_BITS=11,MEM_DEPTH=2048)(
 input clk,input [ADDR_BITS-1:0] write_address,read_address,
 input [35:0] data_in,output [35:0] data_out
);
`ifdef __ICARUS__
 reg [35:0] memory[0:MEM_DEPTH-1];reg [35:0] q;
 always @(posedge clk)begin memory[write_address]<=data_in;q<=memory[read_address];end
 assign data_out=q;
`else
 PH1P_LOGIC_ERAM #(.DATA_WIDTH_A(36),.DATA_WIDTH_B(36),.ADDR_WIDTH_A(ADDR_BITS),.ADDR_WIDTH_B(ADDR_BITS),
  .DATA_DEPTH_A(MEM_DEPTH),.DATA_DEPTH_B(MEM_DEPTH),.MODE("DP"),.REGMODE_A("NOREG"),.REGMODE_B("NOREG"),
  .WRITEMODE_A("NORMAL"),.WRITEMODE_B("NORMAL"),.CLKMODE("SYNC"),.FORCE_KEEP("ON")) u_ram(
  .clka(clk),.clkb(clk),.addra(write_address),.addrb(read_address),.dia(data_in),.dib(36'd0),.doa(),.dob(data_out),
  .wea(1'b1),.web(1'b0),.cea(1'b1),.ceb(1'b1),.ocea(1'b1),.oceb(1'b1),.bea(1'b0),.beb(1'b0),.rsta(1'b0),.rstb(1'b0),
  .ecc_sbiterr(),.ecc_dbiterr(),.ecc_sbiterrinj(1'b0),.ecc_dbiterrinj(1'b0));
`endif
endmodule
