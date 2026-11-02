// Cartoon-only finishing filter; original V8 integer algorithm, lower cap.
// Clear/sketch/edge/recognition/status are exact four-clock RGB bypasses.
// The current pixel stays at its original coordinate; no frame/line shift or
// cropped borders. All UI groups share exactly four output pixel clocks.
module display_cartoon_finish_v9 #(
 parameter H_TOTAL=1650,STRIDE=4,
 parameter TH_DARK=32,TH_BRIGHT=16,MAX_CORRECTION=6
)(
 input clk,rst_n,vs,hs,de,input [23:0] rgb,input overlay,input [7:0] control,
 output O_vs,O_hs,O_de,output reg [23:0] O_rgb,
 output O_overlay,output [7:0] O_control
);
 localparam DEPTH=H_TOTAL*STRIDE;
 localparam AB=$clog2(DEPTH),MEM_DEPTH=1<<AB;
 localparam FB=$clog2(DEPTH+STRIDE+1);
 reg [AB-1:0] pointer;
 wire [AB-1:0] ahead=pointer>=DEPTH-STRIDE?pointer-(DEPTH-STRIDE):pointer+STRIDE;
 wire [25:0] row_q;
 display_cartoon_line_v9 #(.ADDR_BITS(AB),.MEM_DEPTH(MEM_DEPTH)) u_line(
  .clk(clk),.write_address(pointer),.read_address(ahead),.data_in({de,overlay,rgb}),.data_out(row_q));
 reg [25:0] row_history[0:2*STRIDE-1];
 reg [25:0] pixel_history[0:STRIDE-1];
 reg [FB-1:0] filled;
 reg [4:0] previous_mode;
 wire same_mode=previous_mode==control[7:3];
 reg [23:0] center1,center2,center3;
 reg [25:0] left1;
 reg upper_valid1,left_valid1,active1;
 reg [7:0] threshold1;
 reg [3:0] vpipe,hpipe,dpipe,opipe;
 reg [7:0] ctlpipe[0:3];
 integer k;
 wire [9:0] luma_sum={2'd0,rgb[23:16]}+{1'b0,rgb[15:8],1'b0}+{2'd0,rgb[7:0]};
 wire [7:0] luma=luma_sum[9:2];
 wire [7:0] threshold_drop=luma<=64?0:(luma-64)>>3;
 wire [7:0] smooth_threshold=threshold_drop>=TH_DARK-TH_BRIGHT?TH_BRIGHT:TH_DARK-threshold_drop;
 wire selected=control[7:5]==1 && control[4:3]==1;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   pointer<=0;filled<=0;previous_mode<=0;center1<=0;left1<=0;
   upper_valid1<=0;left_valid1<=0;active1<=0;threshold1<=TH_DARK;
   vpipe<=0;hpipe<=0;dpipe<=0;opipe<=0;
   for(k=0;k<4;k=k+1)ctlpipe[k]<=0;
   for(k=0;k<STRIDE;k=k+1)pixel_history[k]<=0;
   for(k=0;k<2*STRIDE;k=k+1)row_history[k]<=0;
  end else begin
   pointer<=pointer==DEPTH-1?0:pointer+1'b1;
   previous_mode<=control[7:3];
   if(!same_mode)filled<=0;
   else if(filled<DEPTH+STRIDE)filled<=filled+1'b1;
   pixel_history[0]<={de,overlay,rgb};
   for(k=1;k<STRIDE;k=k+1)pixel_history[k]<=pixel_history[k-1];
   row_history[0]<=row_q;
   for(k=1;k<2*STRIDE;k=k+1)row_history[k]<=row_history[k-1];
   center1<=rgb;left1<=pixel_history[STRIDE-1];
   upper_valid1<=same_mode && filled>=DEPTH+STRIDE;
   left_valid1<=same_mode && filled>=STRIDE-1;
   active1<=selected && de && !overlay;
   threshold1<=smooth_threshold;
   vpipe<={vpipe[2:0],vs};hpipe<={hpipe[2:0],hs};dpipe<={dpipe[2:0],de};opipe<={opipe[2:0],overlay};
   ctlpipe[0]<=control;ctlpipe[1]<=ctlpipe[0];ctlpipe[2]<=ctlpipe[1];ctlpipe[3]<=ctlpipe[2];
  end
 end
 function [7:0] rgb_distance;
  input [23:0] a,b;
  reg [7:0] dr,dg,db,maximum;
  begin
   dr=a[23:16]>b[23:16]?a[23:16]-b[23:16]:b[23:16]-a[23:16];
   dg=a[15:8]>b[15:8]?a[15:8]-b[15:8]:b[15:8]-a[15:8];
   db=a[7:0]>b[7:0]?a[7:0]-b[7:0]:b[7:0]-a[7:0];
   maximum=dr>dg?dr:dg;rgb_distance=maximum>db?maximum:db;
  end
 endfunction
 wire [25:0] neighbour[0:3];
 assign neighbour[0]=left1;
 assign neighbour[1]=row_history[2*STRIDE-1];
 assign neighbour[2]=row_history[STRIDE-1];
 assign neighbour[3]=row_q;
 reg [3:0] valid_neighbour,accepted,exact_center;
 reg [7:0] distance[0:3];
 reg background_consistent,strong_difference;
 reg preserve_thin;
 integer n,p;
 always @*begin
  for(n=0;n<4;n=n+1)begin
   valid_neighbour[n]=(n==0?left_valid1:upper_valid1) && neighbour[n][25] && !neighbour[n][24];
   distance[n]=rgb_distance(center1,neighbour[n][23:0]);
   accepted[n]=valid_neighbour[n] && distance[n]<=threshold1;
   exact_center[n]=valid_neighbour[n] && distance[n]==0;
  end
  // Retain uniform thin lines and two-colour boundaries even below the range
  // threshold. A one-off impulse has no current-colour continuation.
  // Pairwise equality is the same two-colour test without a priority RGB
  // selector followed by a second distance calculation on the critical path.
  background_consistent=1;strong_difference=0;
  for(n=0;n<4;n=n+1)begin
   if(valid_neighbour[n] && distance[n]>=8)strong_difference=1;
   for(p=n+1;p<4;p=p+1)
    if(!exact_center[n] && !exact_center[p] && neighbour[n][23:0]!=neighbour[p][23:0])background_consistent=0;
  end
  preserve_thin=(&valid_neighbour) &&
   (|exact_center) && background_consistent && strong_difference;
 end
 reg [23:0] selected2[0:3];
 integer s;
 // Register range/line decisions before the RGB addition tree. Pixel values
 // are unchanged from the three-clock prototype; only uniform latency grows.
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin center2<=0;for(s=0;s<4;s=s+1)selected2[s]<=0;end
  else begin
   center2<=center1;
   for(s=0;s<4;s=s+1)selected2[s]<=active1 && accepted[s] && !preserve_thin?neighbour[s][23:0]:center1;
  end
 end
 function [10:0] channel_sum;
  input [7:0] center,a,b,c,d;
  reg [8:0] ab,cd;
  reg [9:0] neighbours_sum;
  reg [10:0] center_round;
  begin
   ab={1'b0,a}+{1'b0,b};cd={1'b0,c}+{1'b0,d};
   neighbours_sum={1'b0,ab}+{1'b0,cd};
   center_round={1'b0,center,2'b00}+11'd4;
   channel_sum=center_round+{1'b0,neighbours_sum};
  end
 endfunction
 reg [10:0] sum2_r,sum2_g,sum2_b;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin sum2_r<=0;sum2_g<=0;sum2_b<=0;center3<=0;end
  else begin
   sum2_r<=channel_sum(center2[23:16],selected2[0][23:16],selected2[1][23:16],selected2[2][23:16],selected2[3][23:16]);
   sum2_g<=channel_sum(center2[15:8],selected2[0][15:8],selected2[1][15:8],selected2[2][15:8],selected2[3][15:8]);
   sum2_b<=channel_sum(center2[7:0],selected2[0][7:0],selected2[1][7:0],selected2[2][7:0],selected2[3][7:0]);
   center3<=center2;
  end
 end
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
  if(!rst_n)O_rgb<=0;
  else O_rgb<={limited(center3[23:16],sum2_r[10:3]),limited(center3[15:8],sum2_g[10:3]),limited(center3[7:0],sum2_b[10:3])};
 end
 assign O_vs=vpipe[3];assign O_hs=hpipe[3];assign O_de=dpipe[3];assign O_overlay=opipe[3];assign O_control=ctlpipe[3];
endmodule

// Explicit native synchronous RAM; only RGB, DE and overlay validity are kept.
// At the read position the previous write is STRIDE lines minus STRIDE clocks
// old, giving upper-right. Write/read addresses never collide for H_TOTAL>2.
(* keep_hierarchy="true" *)
module display_cartoon_line_v9 #(parameter ADDR_BITS=12,MEM_DEPTH=4096)(
 input clk,input [ADDR_BITS-1:0] write_address,read_address,
 input [25:0] data_in,output [25:0] data_out
);
`ifdef __ICARUS__
 reg [25:0] memory[0:MEM_DEPTH-1];reg [25:0] q;
 always @(posedge clk)begin memory[write_address]<=data_in;q<=memory[read_address];end
 assign data_out=q;
`else
 PH1P_LOGIC_ERAM #(.DATA_WIDTH_A(26),.DATA_WIDTH_B(26),.ADDR_WIDTH_A(ADDR_BITS),.ADDR_WIDTH_B(ADDR_BITS),
  .DATA_DEPTH_A(MEM_DEPTH),.DATA_DEPTH_B(MEM_DEPTH),.MODE("DP"),.REGMODE_A("NOREG"),.REGMODE_B("NOREG"),
  .WRITEMODE_A("NORMAL"),.WRITEMODE_B("NORMAL"),.CLKMODE("SYNC"),.FORCE_KEEP("ON")) u_ram(
  .clka(clk),.clkb(clk),.addra(write_address),.addrb(read_address),.dia(data_in),.dib(26'd0),.doa(),.dob(data_out),
  .wea(1'b1),.web(1'b0),.cea(1'b1),.ceb(1'b1),.ocea(1'b1),.oceb(1'b1),.bea(1'b0),.beb(1'b0),.rsta(1'b0),.rstb(1'b0),
  .ecc_sbiterr(),.ecc_dbiterr(),.ecc_sbiterrinj(1'b0),.ecc_dbiterrinj(1'b0));
`endif
endmodule
