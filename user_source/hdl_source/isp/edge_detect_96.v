// Full-resolution robust directional edges, four pixels per clock. Three
// spatially separate signed gradients must agree: a single noisy sample cannot
// become a white halo. The sparse 5x5 support also retains one-pixel diagonals.
// Two additional gray line buffers replace extra arithmetic/whole-frame storage.
// Noise adaptation uses a central Laplacian residual, not the accepted line
// density, so an image containing real contours need not suppress its fine lines.
module edge_detect_96 #(parameter IMG_WIDTH=1280,IMG_HEIGHT=720,parameter EDGE_TH=40)(
 input I_clk,I_rst_n,I_tlast,I_tuser,input [95:0] I_tdata,input I_tvalid,I_tready,
 output reg O_tlast,O_tuser,output reg [95:0] O_tdata,output reg O_tvalid,output O_tready
);
 assign O_tready=I_tready;
 localparam GROUPS=IMG_WIDTH/4;
 function [7:0] grey;
  input [23:0] p;reg [9:0] sum;
  begin sum={2'd0,p[23:16]}+{1'b0,p[15:8],1'b0}+{2'd0,p[7:0]};grey=sum[9:2];end
 endfunction
 wire [31:0] word={grey(I_tdata[95:72]),grey(I_tdata[71:48]),grey(I_tdata[47:24]),grey(I_tdata[23:0])};
 (* ram_style="bram" *) reg [31:0] line1[0:GROUPS-1];
 (* ram_style="bram" *) reg [31:0] line2[0:GROUPS-1];
 (* ram_style="bram" *) reg [31:0] line3[0:GROUPS-1];
 (* ram_style="bram" *) reg [31:0] line4[0:GROUPS-1];
 reg [10:0] x,y,rd_addr,sx,sy;
 wire [10:0] cx=I_tuser?11'd0:x,cy=I_tuser?11'd0:y;
 reg [31:0] bottom;reg sv,su,sl;
 wire [31:0] row3=line1[rd_addr],middle=line2[rd_addr],row1=line3[rd_addr],top=line4[rd_addr];
 always @(posedge I_clk)if(I_tvalid)rd_addr<=cx;
 always @(posedge I_clk)if(sv)line1[sx]<=bottom;
 always @(posedge I_clk)if(sv)begin line2[sx]<=row3;line3[sx]<=middle;line4[sx]<=row1;end
 always @(posedge I_clk)begin
  if(!I_rst_n)begin x<=0;y<=0;sx<=0;sy<=0;bottom<=0;sv<=0;su<=0;sl<=0;end
  else begin
   sv<=I_tvalid;su<=I_tuser;sl<=I_tlast;
   if(I_tuser && !I_tvalid)begin x<=0;y<=0;end
   if(I_tvalid)begin
    sx<=cx;sy<=cy;bottom<=word;
    if(cx==GROUPS-1)begin x<=0;y<=cy==IMG_HEIGHT-1?0:cy+1'b1;end
    else begin x<=cx+1'b1;y<=cy;end
   end
  end
 end
 reg [31:0] previous_top,previous_row1,previous_mid,previous_row3,previous_bot;
 wire [63:0] wt={previous_top,top},w1={previous_row1,row1},wm={previous_mid,middle},w3={previous_row3,row3},wb={previous_bot,bottom};
 reg [6:0] threshold;
 reg [17:0] samples,noise_count;
 wire [4:0] scaled_floor=({1'b0,threshold}+8'd4)>>3;
 wire [4:0] gradient_floor=scaled_floor<=5?5'd4:scaled_floor-1'b1;
 function agree;
  input signed [8:0] a,b,c;input [4:0] floor;
  reg signed [8:0] positive,negative;
  begin
   positive=$signed({4'd0,floor});negative=-positive;
   agree=(a>=positive && b>=positive && c>=positive)||
         (a<=negative && b<=negative && c<=negative);
  end
 endfunction
 function edge_pixel;
  input [39:0] a,b,c,d,e;input [4:0] floor;
  reg signed [8:0] r0,r1,r2,c0,c1,c2,d0,d1,d2,e0,e1,e2;
  begin
   r0=$signed({1'b0,b[15:8]})-$signed({1'b0,b[31:24]});
   r1=$signed({1'b0,c[15:8]})-$signed({1'b0,c[31:24]});
   r2=$signed({1'b0,d[15:8]})-$signed({1'b0,d[31:24]});
   c0=$signed({1'b0,d[31:24]})-$signed({1'b0,b[31:24]});
   c1=$signed({1'b0,d[23:16]})-$signed({1'b0,b[23:16]});
   c2=$signed({1'b0,d[15:8]})-$signed({1'b0,b[15:8]});
   d0=$signed({1'b0,a[23:16]})-$signed({1'b0,c[39:32]});
   d1=$signed({1'b0,b[15:8]})-$signed({1'b0,d[31:24]});
   d2=$signed({1'b0,c[7:0]})-$signed({1'b0,e[23:16]});
   e0=$signed({1'b0,a[23:16]})-$signed({1'b0,c[7:0]});
   e1=$signed({1'b0,b[31:24]})-$signed({1'b0,d[15:8]});
   e2=$signed({1'b0,c[39:32]})-$signed({1'b0,e[23:16]});
   edge_pixel=agree(r0,r1,r2,floor)||agree(c0,c1,c2,floor)||
              agree(d0,d1,d2,floor)||agree(e0,e1,e2,floor);
  end
 endfunction
 wire window_valid=sy>=4 && sx!=0 && !su;
 wire signed [10:0] laplacian=$signed({1'b0,wm[47:40],2'b00})-
     $signed({3'd0,w1[47:40]})-$signed({3'd0,wm[55:48]})-
     $signed({3'd0,wm[39:32]})-$signed({3'd0,w3[47:40]});
 wire [10:0] residual=laplacian<0?-laplacian:laplacian;
 wire [3:0] detected;
 genvar k;
 generate for(k=0;k<4;k=k+1)begin: pixels
  assign detected[3-k]=window_valid && edge_pixel(wt[63-8*k-:40],w1[63-8*k-:40],
    wm[63-8*k-:40],w3[63-8*k-:40],wb[63-8*k-:40],gradient_floor);
 end endgenerate
 always @(posedge I_clk or negedge I_rst_n)begin
  if(!I_rst_n)begin
   previous_top<=0;previous_row1<=0;previous_mid<=0;previous_row3<=0;previous_bot<=0;O_tlast<=0;O_tuser<=0;O_tdata<=0;O_tvalid<=0;
   threshold<=EDGE_TH<28?28:EDGE_TH>112?112:EDGE_TH;samples<=0;noise_count<=0;
  end else begin
   O_tlast<=sl;O_tuser<=su;O_tvalid<=sv;
   O_tdata<=sv?{{24{detected[3]}},{24{detected[2]}},{24{detected[1]}},{24{detected[0]}}}:96'd0;
   if(su)begin
    if(samples>=128)begin
     if(noise_count>(samples>>2) && threshold<108)threshold<=threshold+4;
     else if(noise_count>(samples>>3) && threshold<112)threshold<=threshold+2;
     else if(noise_count<(samples>>5) && threshold>28)threshold<=threshold-2;
    end
    samples<=0;noise_count<=0;
   end else if(sv&&window_valid)begin samples<=samples+1'b1;if(residual>(threshold>>1))noise_count<=noise_count+1'b1;end
   if(sv)begin
    previous_top<=sx==GROUPS-1?32'd0:top;
    previous_row1<=sx==GROUPS-1?32'd0:row1;
    previous_mid<=sx==GROUPS-1?32'd0:middle;
    previous_row3<=sx==GROUPS-1?32'd0:row3;
    previous_bot<=sx==GROUPS-1?32'd0:bottom;
   end else if(su)begin previous_top<=0;previous_row1<=0;previous_mid<=0;previous_row3<=0;previous_bot<=0;end
  end
 end
endmodule
