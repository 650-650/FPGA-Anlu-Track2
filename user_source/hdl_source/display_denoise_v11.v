// Combined display-only stage: accepted V9 clear cross plus a narrow, guarded
// radius-two impulse repair. Cartoon otherwise passes exactly (no RGB blur).
// Input sampled at edge j is emitted at edge j+2*H_TOTAL+6 on every page.
module display_denoise_v11 #(
 parameter H_TOTAL=1650,WIDTH=1280,HEIGHT=720,
 parameter TH_DARK=32,TH_BRIGHT=16,MAX_CORRECTION=6,CARTOON_DESPECKLE=1,
 parameter ROI_X0=672,ROI_X1=720,ROI_Y0=144,ROI_Y1=176
)(
 input clk,rst_n,vs,hs,de,input [23:0] rgb,input overlay,input [7:0] control,
 output O_vs,O_hs,O_de,output reg [23:0] O_rgb,
 output O_overlay,output [7:0] O_control
);
 localparam AB=$clog2(H_TOTAL),MD=1<<AB,WB=$clog2(4*H_TOTAL+7);
 wire [35:0] packet={control,overlay,de,hs,vs,rgb};
 reg [AB-1:0] pointer;reg [WB-1:0] warm;
 wire [AB-1:0] ahead=pointer==H_TOTAL-1?0:pointer+1'b1;
 wire [35:0] q1,q2,q3,q4;
 display_line_v11 #(.ADDR_BITS(AB),.MEM_DEPTH(MD)) line1(.clk(clk),.wa(pointer),.ra(ahead),.din(packet),.dout(q1));
 display_line_v11 #(.ADDR_BITS(AB),.MEM_DEPTH(MD)) line2(.clk(clk),.wa(pointer),.ra(ahead),.din(warm>=H_TOTAL?q1:36'd0),.dout(q2));
 display_line_v11 #(.ADDR_BITS(AB),.MEM_DEPTH(MD)) line3(.clk(clk),.wa(pointer),.ra(ahead),.din(warm>=2*H_TOTAL?q2:36'd0),.dout(q3));
 display_line_v11 #(.ADDR_BITS(AB),.MEM_DEPTH(MD)) line4(.clk(clk),.wa(pointer),.ra(ahead),.din(warm>=3*H_TOTAL?q3:36'd0),.dout(q4));
 reg [35:0] r0[0:4],r1[0:4],r2[0:4],r3[0:4],r4[0:4];
 integer k;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   pointer<=0;warm<=0;
   for(k=0;k<5;k=k+1)begin r0[k]<=0;r1[k]<=0;r2[k]<=0;r3[k]<=0;r4[k]<=0;end
  end else begin
   pointer<=pointer==H_TOTAL-1?0:pointer+1'b1;
   if(warm<4*H_TOTAL+6)warm<=warm+1'b1;
   r0[0]<=packet;r1[0]<=warm>=H_TOTAL?q1:36'd0;
   r2[0]<=warm>=2*H_TOTAL?q2:36'd0;r3[0]<=warm>=3*H_TOTAL?q3:36'd0;r4[0]<=warm>=4*H_TOTAL?q4:36'd0;
   for(k=1;k<5;k=k+1)begin r0[k]<=r0[k-1];r1[k]<=r1[k-1];r2[k]<=r2[k-1];r3[k]<=r3[k-1];r4[k]<=r4[k-1];end
  end
 end
 wire [35:0] center=r2[2];
 wire [35:0] cross_pkt[0:3],grid[0:8];
 assign cross_pkt[0]=r2[3];assign cross_pkt[1]=r2[1];assign cross_pkt[2]=r3[2];assign cross_pkt[3]=r1[2];
 assign grid[0]=r4[4];assign grid[1]=r4[2];assign grid[2]=r4[0];
 assign grid[3]=r2[4];assign grid[4]=r2[2];assign grid[5]=r2[0];
 assign grid[6]=r0[4];assign grid[7]=r0[2];assign grid[8]=r0[0];
 function [7:0] gray;
  input [23:0] p;reg [9:0] s;
  begin s={2'd0,p[23:16]}+{1'b0,p[15:8],1'b0}+{2'd0,p[7:0]};gray=s[9:2];end
 endfunction
 // Constant signed range checks avoid absolute-value/max trees in DPC gates.
 function near_rgb;
  input [23:0] a,b;input [8:0] tolerance;
  reg signed [8:0] dr,dg,db,t;
  begin
   dr=$signed({1'b0,a[23:16]})-$signed({1'b0,b[23:16]});
   dg=$signed({1'b0,a[15:8]})-$signed({1'b0,b[15:8]});
   db=$signed({1'b0,a[7:0]})-$signed({1'b0,b[7:0]});t=$signed(tolerance);
   near_rgb=dr>=-t && dr<=t && dg>=-t && dg<=t && db>=-t && db<=t;
  end
 endfunction
 function [7:0] distance;
  input [23:0] a,b;reg [7:0] dr,dg,db,m;
  begin
   dr=a[23:16]>b[23:16]?a[23:16]-b[23:16]:b[23:16]-a[23:16];
   dg=a[15:8]>b[15:8]?a[15:8]-b[15:8]:b[15:8]-a[15:8];
   db=a[7:0]>b[7:0]?a[7:0]-b[7:0]:b[7:0]-a[7:0];
   m=dr>dg?dr:dg;distance=m>db?m:db;
  end
 endfunction
 // One vector order: luminance is the primary key, RGB breaks equal-Y ties.
 // No channel is independently selected or averaged by the median network.
 function [95:0] sort3;
  input [31:0] p,q,r;reg [31:0] a,b,c,t;
  begin
   a=p;b=q;c=r;
   if(a>b)begin t=a;a=b;b=t;end
   if(b>c)begin t=b;b=c;c=t;end
   if(a>b)begin t=a;a=b;b=t;end
   sort3={a,b,c};
  end
 endfunction
 function [31:0] median3;
  input [31:0] a,b,c;reg [95:0] s;
  begin s=sort3(a,b,c);median3=s[63:32];end
 endfunction
 function [31:0] min3;
  input [31:0] a,b,c;reg [31:0] v;
  begin v=a<b?a:b;min3=v<c?v:c;end
 endfunction
 function [31:0] max3;
  input [31:0] a,b,c;reg [31:0] v;
  begin v=a>b?a:b;max3=v>c?v:c;end
 endfunction
 reg [11:0] px,py;reg cvs_d;
 wire new_frame=center[24] && !cvs_d;
 wire [11:0] cx=new_frame?12'd0:px,cy=new_frame?12'd0:py;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin px<=0;py<=0;cvs_d<=0;end
  else begin
   cvs_d<=center[24];
   if(new_frame)begin px<=0;py<=0;end
   else if(center[26])begin
    if(px==WIDTH-1)begin px<=0;py<=py==HEIGHT-1?0:py+1'b1;end else px<=px+1'b1;
   end
  end
 end
 wire [3:0] cross_valid,accepted;
 wire [8:0] grid_valid;
 wire clear_selected=center[35:33]==0 || (center[35:33]==1 && center[32:31]==0);
 wire clear_valid=center[26] && !center[27] && clear_selected && (&cross_valid);
 wire colour_page=!(center[35:33]==1 && center[32]);
 wire in_roi=cx>=ROI_X0 && cx<ROI_X1 && cy>=ROI_Y0 && cy<ROI_Y1;
 wire window_valid=center[26] && !center[27] && (&grid_valid);
 wire dpc_valid=window_valid && colour_page && in_roi;
 wire cleanup_valid=(CARTOON_DESPECKLE!=0) && window_valid && center[35:33]==1 && center[32:31]==1;
 wire [7:0] luma=gray(center[23:0]);
 wire [7:0] drop=luma<=64?0:(luma-64)>>3;
 wire [7:0] threshold=drop>=TH_DARK-TH_BRIGHT?TH_BRIGHT:TH_DARK-drop;
 wire [31:0] value[0:8];wire [215:0] packed_grid;
 genvar g;
 generate for(g=0;g<9;g=g+1)begin:gv
  assign grid_valid[g]=grid[g][26] && !grid[g][27] && grid[g][35:31]==center[35:31];
  assign value[g]={gray(grid[g][23:0]),grid[g][23:0]};
  assign packed_grid[215-24*g-:24]=grid[g][23:0];
 end
 for(g=0;g<4;g=g+1)begin:cv
  assign cross_valid[g]=cross_pkt[g][26] && !cross_pkt[g][27] && cross_pkt[g][35:31]==center[35:31];
  assign accepted[g]=clear_valid && distance(center[23:0],cross_pkt[g][23:0])<=threshold;
 end endgenerate
 reg [95:0] sorted1[0:2];
 reg [31:0] lower2,middle2,upper2,median3_d;
 reg [215:0] grid1,grid2,grid3;
 reg dv1,dv2,dv3,cl1,cl2,cl3;
 reg [23:0] center1,center2,chosen1[0:3],clear3;
 reg [10:0] sum2_r,sum2_g,sum2_b;
 reg [11:0] meta[0:3];
 function [10:0] channel_sum;
  input [7:0] c,a,b,d,e;reg [8:0] ab,dd;reg [9:0] s;
  begin ab={1'b0,a}+{1'b0,b};dd={1'b0,d}+{1'b0,e};s={1'b0,ab}+{1'b0,dd};channel_sum={1'b0,c,2'b00}+11'd4+{1'b0,s};end
 endfunction
 function [7:0] limited;
  input [7:0] c,f;reg [8:0] lo,hi;
  begin lo=c>MAX_CORRECTION?{1'b0,c}-MAX_CORRECTION:0;hi=c<255-MAX_CORRECTION?{1'b0,c}+MAX_CORRECTION:255;limited=f<lo?lo[7:0]:f>hi?hi[7:0]:f;end
 endfunction
 function chroma_jump;
  input [23:0] a,b;
  reg signed [10:0] coa,cob,cga,cgb,dco,dcg;
  begin
   coa=$signed({3'd0,a[23:16]})-$signed({3'd0,a[7:0]});
   cob=$signed({3'd0,b[23:16]})-$signed({3'd0,b[7:0]});
   cga=$signed({3'd0,a[15:8]})-(($signed({3'd0,a[23:16]})+$signed({3'd0,a[7:0]}))>>>1);
   cgb=$signed({3'd0,b[15:8]})-(($signed({3'd0,b[23:16]})+$signed({3'd0,b[7:0]}))>>>1);
   dco=coa-cob;dcg=cga-cgb;
   chroma_jump=dco>=11'sd48 || dco<=-11'sd48 || dcg>=11'sd48 || dcg<=-11'sd48;
  end
 endfunction
 wire [23:0] original3=grid3[119:96],replacement3=median3_d[23:0];
 wire [7:0] original_y3=gray(original3),replacement_y3=median3_d[31:24];
 wire bright_peak3=original3[23:16]>=160 || original3[15:8]>=160 || original3[7:0]>=160;
 wire bright3=original_y3>=160 && {1'b0,original_y3}>={1'b0,replacement_y3}+9'd48;
 wire coloured3=bright_peak3 && chroma_jump(original3,replacement3);
 wire [8:0] coherent3;
 wire [8:0] coherent24_3;
 wire [8:0] continuation3;
 generate for(g=0;g<9;g=g+1)begin:coherent_sample
  assign coherent3[g]=(g==4)?1'b0:near_rgb(grid3[215-24*g-:24],replacement3,9'd32);
  assign coherent24_3[g]=(g==4)?1'b0:near_rgb(grid3[215-24*g-:24],replacement3,9'd24);
  assign continuation3[g]=(g==4)?1'b0:near_rgb(grid3[215-24*g-:24],original3,9'd16);
 end endgenerate
 wire [1:0] c01={1'b0,coherent3[0]}+{1'b0,coherent3[1]},c23={1'b0,coherent3[2]}+{1'b0,coherent3[3]};
 wire [1:0] c56={1'b0,coherent3[5]}+{1'b0,coherent3[6]},c78={1'b0,coherent3[7]}+{1'b0,coherent3[8]};
 wire [2:0] count_a={1'b0,c01}+{1'b0,c23},count_b={1'b0,c56}+{1'b0,c78};
 wire [3:0] coherent_count={1'b0,count_a}+{1'b0,count_b};
 wire [1:0] d01={1'b0,coherent24_3[0]}+{1'b0,coherent24_3[1]},d23={1'b0,coherent24_3[2]}+{1'b0,coherent24_3[3]};
 wire [1:0] d56={1'b0,coherent24_3[5]}+{1'b0,coherent24_3[6]},d78={1'b0,coherent24_3[7]}+{1'b0,coherent24_3[8]};
 wire [2:0] clean_a={1'b0,d01}+{1'b0,d23},clean_b={1'b0,d56}+{1'b0,d78};
 wire [3:0] clean_count={1'b0,clean_a}+{1'b0,clean_b};
 // A genuine line continuing through any pair of opposite radius-two taps
 // survives. A <=4x4 rectangle cannot span both ends of a five-pixel pair.
 wire line_continues3=(continuation3[0]&&continuation3[8]) || (continuation3[1]&&continuation3[7]) ||
                      (continuation3[2]&&continuation3[6]) || (continuation3[3]&&continuation3[5]);
 wire repair3=dv3 && !line_continues3 && coherent_count>=5 && !near_rgb(original3,replacement3,9'd63) && (bright3||coloured3);
 wire y_jump32=({1'b0,original_y3}>={1'b0,replacement_y3}+9'd32) || ({1'b0,replacement_y3}>={1'b0,original_y3}+9'd32);
 wire cleanup3=cl3 && clean_count>=7 && y_jump32;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   for(k=0;k<3;k=k+1)sorted1[k]<=0;
   for(k=0;k<4;k=k+1)begin chosen1[k]<=0;meta[k]<=0;end
   lower2<=0;middle2<=0;upper2<=0;median3_d<=0;grid1<=0;grid2<=0;grid3<=0;
   dv1<=0;dv2<=0;dv3<=0;cl1<=0;cl2<=0;cl3<=0;center1<=0;center2<=0;sum2_r<=0;sum2_g<=0;sum2_b<=0;clear3<=0;O_rgb<=0;
  end else begin
   // 1: row sorts (9 compare-exchanges), unchanged clear neighbour selection.
   sorted1[0]<=sort3(value[0],value[1],value[2]);
   sorted1[1]<=sort3(value[3],value[4],value[5]);
   sorted1[2]<=sort3(value[6],value[7],value[8]);
   grid1<=packed_grid;dv1<=dpc_valid;cl1<=cleanup_valid;center1<=center[23:0];
   for(k=0;k<4;k=k+1)chosen1[k]<=accepted[k]?cross_pkt[k][23:0]:center[23:0];
   // 2: the three median candidates (7 comparisons), clear balanced RGB sum.
   lower2<=max3(sorted1[0][95:64],sorted1[1][95:64],sorted1[2][95:64]);
   middle2<=median3(sorted1[0][63:32],sorted1[1][63:32],sorted1[2][63:32]);
   upper2<=min3(sorted1[0][31:0],sorted1[1][31:0],sorted1[2][31:0]);
   grid2<=grid1;dv2<=dv1;cl2<=cl1;center2<=center1;
   sum2_r<=channel_sum(center1[23:16],chosen1[0][23:16],chosen1[1][23:16],chosen1[2][23:16],chosen1[3][23:16]);
   sum2_g<=channel_sum(center1[15:8],chosen1[0][15:8],chosen1[1][15:8],chosen1[2][15:8],chosen1[3][15:8]);
   sum2_b<=channel_sum(center1[7:0],chosen1[0][7:0],chosen1[1][7:0],chosen1[2][7:0],chosen1[3][7:0]);
   // 3: exact ninth-sample median (3 comparisons), unchanged clear correction.
   median3_d<=median3(lower2,middle2,upper2);grid3<=grid2;dv3<=dv2;cl3<=cl2;
   clear3<={limited(center2[23:16],sum2_r[10:3]),limited(center2[15:8],sum2_g[10:3]),limited(center2[7:0],sum2_b[10:3])};
   // 4: a guarded vector replacement, never a coordinate fill or RGB mean.
   O_rgb<=(repair3||cleanup3)?replacement3:clear3;
   meta[0]<=center[35:24];meta[1]<=meta[0];meta[2]<=meta[1];meta[3]<=meta[2];
  end
 end
 assign O_control=meta[3][11:4];assign O_overlay=meta[3][3];
 assign O_de=meta[3][2];assign O_hs=meta[3][1];assign O_vs=meta[3][0];
endmodule

(* keep_hierarchy="true" *)
module display_line_v11 #(parameter ADDR_BITS=11,MEM_DEPTH=2048)(
 input clk,input [ADDR_BITS-1:0] wa,ra,input [35:0] din,output [35:0] dout
);
`ifdef __ICARUS__
 reg [35:0] memory[0:MEM_DEPTH-1];reg [35:0] q;
 always @(posedge clk)begin memory[wa]<=din;q<=memory[ra];end
 assign dout=q;
`else
 PH1P_LOGIC_ERAM #(.DATA_WIDTH_A(36),.DATA_WIDTH_B(36),.ADDR_WIDTH_A(ADDR_BITS),.ADDR_WIDTH_B(ADDR_BITS),
  .DATA_DEPTH_A(MEM_DEPTH),.DATA_DEPTH_B(MEM_DEPTH),.MODE("DP"),.REGMODE_A("NOREG"),.REGMODE_B("NOREG"),
  .WRITEMODE_A("NORMAL"),.WRITEMODE_B("NORMAL"),.CLKMODE("SYNC"),.FORCE_KEEP("ON")) u_ram(
  .clka(clk),.clkb(clk),.addra(wa),.addrb(ra),.dia(din),.dib(36'd0),.doa(),.dob(dout),
  .wea(1'b1),.web(1'b0),.cea(1'b1),.ceb(1'b1),.ocea(1'b1),.oceb(1'b1),.bea(1'b0),.beb(1'b0),.rsta(1'b0),.rstb(1'b0),
  .ecc_sbiterr(),.ecc_dbiterr(),.ecc_sbiterrinj(1'b0),.ecc_dbiterrinj(1'b0));
`endif
endmodule
