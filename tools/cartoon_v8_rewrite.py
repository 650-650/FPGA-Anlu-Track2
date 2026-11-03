"""Build the V8 style source from unchanged V7 transport/convolutions and new fill.
This script writes only this V8 project's owned stylize_v5_96.v.
"""
from pathlib import Path
import re
R=Path(__file__).resolve().parents[1]
old=(R.parent/'07_stylize_flame_fusion_v7_shadow_clean/user_source/hdl_source/isp/stylize_v5_96.v').read_text(encoding='utf-8')
head=old[old.index('module stylize_v5_96 #('):old.index('// 自适应统计常数')]
head=head.replace('parameter MEDIAN_ERAM = 1','parameter MEDIAN_ERAM = 1, // compatibility only; no V8 quantisation median\n    parameter [7:0] SKETCH_FLOOR = 8\'d12,\n    parameter [7:0] SKETCH_GAIN = 8\'d49')
head=head.replace('localparam MODE_SKETCH  = 2\'d2;','localparam MODE_SKETCH  = 2\'d2;\nlocalparam MODE_EDGE = 2\'d3;')
control=old[old.index('reg  [9:0]  x_cnt;'):old.index('// 公共函数')]
functions=[]
for block in re.findall(r'(?ms)^function\b.*?^endfunction',old):
 if any(re.search(r'\b'+n+r'\b',block.splitlines()[0]) for n in ['gray','vsum','hblur','sobel8']):functions.append(block)
assert len(functions)==4
start=old.index('// 第一级窗口：');end=old.index('// 自适应参数')
convolution=old[start:end]
convolution=re.sub(r'wire \[95:0\] bypass_in=.*?;','wire [95:0] bypass_in=bypass_d2;',convolution)
st=convolution.index('reg  signed [8:0] b4_ofr');en=convolution.index('always @(posedge I_clk)',st)
convolution=convolution[:st]+convolution[en:]
convolution=re.sub(r'^\s*b4_of[rb]\s*<=.*?;\n','',convolution,flags=re.M)
tail=r'''
// B5/B5b/B6 keep the original three clocks. True B2 RGB is carried intact;
// no local colour learning, saturation multiplier or histogram posterisation.
reg [95:0] b5_rgb,bq_rgb;
reg [31:0] b5_y2,b5_mag,bq_y2,bq_mag;
reg b5_v,bq_v,b6_v;
reg [9:0] b5_x,bq_x,b6_x;
reg [TW-1:0] b5_tag,bq_tag,b6_tag;
reg [159:0] b6_pay;
always @(posedge I_clk)begin
 if(b4_v)begin
  b5_rgb<=b4_b2;b5_mag<=b4_mag;b5_x<=b4_x;b5_tag<=b4_tag;
  for(k=0;k<4;k=k+1)b5_y2[31-8*k-:8]<=gray(b4_b2[95-24*k-:24]);
 end
 if(b5_v)begin bq_rgb<=b5_rgb;bq_y2<=b5_y2;bq_mag<=b5_mag;bq_x<=b5_x;bq_tag<=b5_tag;end
 if(bq_v)begin
  for(k=0;k<4;k=k+1)b6_pay[159-40*k-:40]<={bq_y2[31-8*k-:8],bq_mag[31-8*k-:8],bq_rgb[95-24*k-:24]};
  b6_x<=bq_x;b6_tag<=bq_tag;
 end
end
always @(posedge I_clk or negedge I_rst_n)begin
 if(!I_rst_n)begin b3_v<=0;b4_v<=0;b5_v<=0;bq_v<=0;b6_v<=0;end
 else begin b3_v<=b2_v;b4_v<=b3_v;b5_v<=b4_v;bq_v<=b5_v;b6_v<=bq_v;end
end

// Third window reuses the existing two 40-bit lines for all three styles.
wire w3_v;wire [9:0]w3_x;wire[TW-1:0]w3_tag;
wire[239:0]w3_top,w3_mid,w3_bot;
sty_win3_96 #(.W_GRP(W_GRP),.LEFT_X(3),.TW(TW),.PW(40)) u_win_c(
 .clk(I_clk),.rst_n(I_rst_n),.i_v(b6_v),.i_x(b6_x),.i_pix(b6_pay),.i_tag(b6_tag),
 .o_v(w3_v),.o_x(w3_x),.o_tag(w3_tag),.o_top(w3_top),.o_mid(w3_mid),.o_bot(w3_bot));
wire[31:0]guide_mag;wire[3:0]guide_edge,guide_support;
genvar gp;
generate for(gp=0;gp<4;gp=gp+1)begin: guides
 style_guide_v8 u_guide(
  .I_y2({w3_top[239-40*gp-:8],w3_top[199-40*gp-:8],w3_top[159-40*gp-:8],
         w3_mid[239-40*gp-:8],w3_mid[199-40*gp-:8],w3_mid[159-40*gp-:8],
         w3_bot[239-40*gp-:8],w3_bot[199-40*gp-:8],w3_bot[159-40*gp-:8]}),
  .I_fine({w3_top[231-40*gp-:8],w3_top[191-40*gp-:8],w3_top[151-40*gp-:8],
           w3_mid[231-40*gp-:8],w3_mid[191-40*gp-:8],w3_mid[151-40*gp-:8],
           w3_bot[231-40*gp-:8],w3_bot[191-40*gp-:8],w3_bot[151-40*gp-:8]}),
  .O_mag(guide_mag[31-8*gp-:8]),.O_edge(guide_edge[3-gp]),.O_support(guide_support[3-gp]));
end endgenerate

reg[95:0]c1_rgb;reg[31:0]c1_y2,c1_mag;reg[3:0]c1_edge;
reg c1_v,c1_mask;reg[TW-1:0]c1_tag;
always @(posedge I_clk)if(w3_v)begin
 for(k=0;k<4;k=k+1)begin
  c1_rgb[95-24*k-:24]<=w3_mid[183-40*k-:24];
  c1_y2[31-8*k-:8]<=w3_mid[199-40*k-:8];
 end
 c1_mag<=guide_mag;c1_edge<=guide_edge;c1_tag<=w3_tag;
 c1_mask<=(w3_x<3)||(w3_tag[TW-1-:11]<6);
end

// Local trusted magnitude uses a fixed ink calibration. A distant bright
// texture/noise patch cannot change the gain or erase this pixel's weak line.
// Original paper response and subtractive ink rendering are retained.
reg[95:0]c2_px;reg c2_v,c2_mask;reg[TW-1:0]c2_tag;
reg[23:0]pp;reg[7:0]sketch_dm,sketch_ink,sketch_paper;
reg[15:0]sketch_prod;
always @(posedge I_clk)if(c1_v)begin
 for(k=0;k<4;k=k+1)begin
  pp=c1_rgb[95-24*k-:24];
  case(c1_tag[1:0])
   MODE_SKETCH:begin
    sketch_dm=c1_mag[31-8*k-:8]>SKETCH_FLOOR?c1_mag[31-8*k-:8]-SKETCH_FLOOR:0;
    sketch_prod=sketch_dm*SKETCH_GAIN;
    sketch_ink=sketch_prod[15:12]!=0?8'd255:sketch_prod[11:4];
    sketch_paper=8'd255-{3'd0,~c1_y2[31-8*k-:5]};
    c2_px[95-24*k-:24]<={3{sketch_paper>sketch_ink?sketch_paper-sketch_ink:8'd0}};
   end
   MODE_EDGE:c2_px[95-24*k-:24]<={24{c1_edge[3-k]}};
   default:begin
    if(c1_edge[3-k])begin
     if(c1_y2[31-8*k-:8]<96)c2_px[95-24*k-:24]<={1'b0,pp[23:17],1'b0,pp[15:9],1'b0,pp[7:1]};
     else c2_px[95-24*k-:24]<=0;
    end else c2_px[95-24*k-:24]<=pp;
   end
  endcase
 end
 c2_tag<=c1_tag;c2_mask<=c1_mask;
end
always @(posedge I_clk or negedge I_rst_n)begin
 if(!I_rst_n)begin c1_v<=0;c2_v<=0;end
 else begin c1_v<=w3_v;c2_v<=c1_v;end
end
wire[1:0]mode_o=c2_tag[1:0];
always @(posedge I_clk or negedge I_rst_n)begin
 if(!I_rst_n)begin O_tvalid<=0;O_tuser<=0;O_tlast<=0;O_tdata<=0;end
 else begin
  O_tvalid<=c2_v;O_tuser<=u_dly[LAT-2];O_tlast<=l_dly[LAT-2];
  if(!c2_v)O_tdata<=0;
  else if(mode_o==0)O_tdata<=bypass_delayed;
  else if(c2_mask)O_tdata<=0;
  else O_tdata<=c2_px;
 end
end
endmodule
'''
helpers=old[old.index('module sty_win3_96 #('):]
header='''// V8 colour-preserving style pipeline, four pixels/clock, fixed 16 clocks.
// Mode0 is the exact original RGB bypass. Mode1 uses existing B2 smoothed RGB
// with connected outlines; it never learns colours, quantises them into gray,
// or raises saturation noise. Modes2/3 share one local trusted gradient guide.
// No global image-content statistic controls another location's ink strength.
// EXTERNAL_EDGE/MEDIAN_ERAM ports/parameters remain for project compatibility;
// V8 mode3 uses the shared guide, and V8 cartoon has no quantisation median.
// The unused generic median helpers below are retained for old unit benches.
'''
target=R/'user_source/hdl_source/isp/stylize_v5_96.v'
target.write_text(header+head+control+'\n'.join(functions)+'\n'+convolution+tail+helpers,encoding='utf-8',newline='\n')
print('V8_STYLE_REWRITTEN',target)
