// V11 categorical six-band cartoon, four pixels/clock, fixed 16 clocks.
// Modes 0/2/3 use the exact V10 bypass/guide/render path. Cartoon no longer
// uses a third Gaussian or continuous full-scene shelves: ordered Y2 labels
// are median-voted spatially, then mapped to six fixed cel-fill luminances.
// Original RGB colour differences are retained by one common gamut guard.
module stylize_v5_96 #(
    parameter IMG_WIDTH  = 1280,
    parameter IMG_HEIGHT = 720,
    parameter EXTERNAL_EDGE = 0,
    parameter MEDIAN_ERAM = 1, // compatibility only; no V8 quantisation median
    parameter [7:0] SKETCH_FLOOR = 8'd12,
    parameter [7:0] SKETCH_GAIN = 8'd49
)(
    input               I_clk,
    input               I_rst_n,

    input       [1:0]   I_mode,       // 0 原图 / 1 卡通 / 2 素描
    input       [2:0]   I_level,

    input               I_tlast,
    input               I_tuser,
    input      [95:0]   I_tdata,
    input      [95:0]   I_edge_data,
    input               I_tvalid,
    input               I_tready,
    output reg          O_tlast,
    output reg          O_tuser,
    output reg [95:0]   O_tdata,
    output reg          O_tvalid,
    output              O_tready
);

assign O_tready = I_tready;

localparam W_GRP   = IMG_WIDTH / 4;
localparam LAT     = 16;

localparam MODE_CARTOON = 2'd1;
localparam MODE_SKETCH  = 2'd2;
localparam MODE_EDGE = 2'd3;

reg  [9:0]  x_cnt;
reg  [10:0] y_cnt;
reg  [1:0]  ctrl_f;             // 本帧模式
reg  [2:0]  level_f;

reg  sof_pend;                  // I_tuser 提前到达时，记住它，等第一个有效拍
wire sof_beat = I_tvalid && (I_tuser || sof_pend);

always @(posedge I_clk or negedge I_rst_n) begin
    if(!I_rst_n)        sof_pend <= 1'b0;
    else if(I_tvalid)   sof_pend <= 1'b0;
    else if(I_tuser)    sof_pend <= 1'b1;
end

wire [9:0]  x_cur    = sof_beat ? 10'd0 : x_cnt;
wire [10:0] y_cur    = sof_beat ? 11'd0 : y_cnt;
wire [1:0]  ctrl_cur = sof_beat ? I_mode : ctrl_f;
wire [2:0]  level_cur = sof_beat ? (I_level<=4?I_level:3'd2) : level_f;

// 同步复位：x_cur 进入行缓存读地址，带异步复位会让 TD 不能映射到 ERAM
always @(posedge I_clk) begin
    if(!I_rst_n) begin
        x_cnt  <= 10'd0;
        y_cnt  <= 11'd0;
        ctrl_f <= 2'd0;
        level_f <= 3'd2;
    end else if(I_tvalid) begin
        ctrl_f <= ctrl_cur;
        level_f <= level_cur;
        if(x_cur == W_GRP - 1) begin
            x_cnt <= 10'd0;
            y_cnt <= (y_cur == IMG_HEIGHT - 1) ? 11'd0 : y_cur + 1'b1;
        end else begin
            x_cnt <= x_cur + 1'b1;
            y_cnt <= y_cur;
        end
    end
end

// tuser / tlast 每拍移位，固定延迟 LAT
reg [LAT-1:0] u_dly, l_dly;
always @(posedge I_clk or negedge I_rst_n) begin
    if(!I_rst_n) begin
        u_dly <= {LAT{1'b0}};
        l_dly <= {LAT{1'b0}};
    end else begin
        u_dly <= {u_dly[LAT-2:0], I_tuser};
        l_dly <= {l_dly[LAT-2:0], I_tlast};
    end
end


// 随数据一起走的标签：{y, mode, 原图像素}
localparam TW = 11 + 3 + 2;
// Carry the frame's parameter with its pixels, including the pipeline tail.
wire [TW-1:0] tag_in = {y_cur, level_cur, ctrl_cur};

// =============================================================================
function [7:0] gray;                 // (R + 2G + B) / 4
    input [23:0] p;
    reg   [9:0]  s;
    begin
        s    = {2'b0, p[23:16]} + {1'b0, p[15:8], 1'b0} + {2'b0, p[7:0]};
        gray = s[9:2];
    end
endfunction
function [9:0] vsum;                 // a + 2b + c
    input [7:0] a, b, c;
    begin
        vsum = {2'b0, a} + {1'b0, b, 1'b0} + {2'b0, c};
    end
endfunction
function [7:0] hblur;                // (l + 2c + r) / 16
    input [9:0] l, c, r;
    reg   [11:0] s;
    begin
        s     = {2'b0, l} + {1'b0, c, 1'b0} + {2'b0, r};
        hblur = s[11:4];
    end
endfunction
function [7:0] sobel8;
    input [9:0]        l, r;
    input signed [8:0] dl, dc, dr;
    reg signed [11:0] gx, gy;
    reg        [11:0] ax, ay, m;
    begin
        gx = $signed({2'b0, r}) - $signed({2'b0, l});
        gy = dl + (dc <<< 1) + dr;
        ax = gx[11] ? -gx : gx;
        ay = gy[11] ? -gy : gy;
        m  = ax + ay;
        sobel8 = (m > 12'd255) ? 8'd255 : m[7:0];
    end
endfunction
// 第一级窗口：原图 -> 3x3 高斯平滑
// =============================================================================
wire          a2_v;
wire [9:0]    a2_x;
wire [TW-1:0] a2_tag;

// RGB bypass is independent of the arithmetic/tag pipeline. Replacing
// 96 payload bits in every tag stage with a tiny ERAM FIFO saves slices.
// Two input delay clocks + fourteen FIFO/output clocks = original 16.
reg [95:0] bypass_d1,bypass_d2;
always @(posedge I_clk)begin bypass_d1<=I_tdata;bypass_d2<=bypass_d1;end
wire [95:0] bypass_in=bypass_d2;
wire [95:0] bypass_delayed;
sty_bypass_memory u_bypass_memory(.clk(I_clk),.rst_n(I_rst_n),.din(bypass_in),.dout(bypass_delayed));


wire [143:0]  a2_top, a2_mid, a2_bot;

sty_win3_96 #(.W_GRP(W_GRP), .LEFT_X(1), .TW(TW)) u_win_a (
    .clk(I_clk), .rst_n(I_rst_n), .i_v(I_tvalid), .i_x(x_cur), .i_pix(I_tdata), .i_tag(tag_in),
    .o_v(a2_v), .o_x(a2_x), .o_tag(a2_tag),
    .o_top(a2_top), .o_mid(a2_mid), .o_bot(a2_bot)
);

// A3：每列 R/G/B 纵向 [1 2 1]
reg  [59:0]   a3_vr, a3_vg, a3_vb;     // 6 列 x 10bit，第0列在最高位
reg           a3_v;
reg  [9:0]    a3_x;
reg  [TW-1:0] a3_tag;

integer i;
always @(posedge I_clk) begin
    if(a2_v) begin
        for(i = 0; i < 6; i = i + 1) begin
            a3_vr[59-10*i -: 10] <= vsum(a2_top[143-24*i -: 8], a2_mid[143-24*i -: 8], a2_bot[143-24*i -: 8]);
            a3_vg[59-10*i -: 10] <= vsum(a2_top[135-24*i -: 8], a2_mid[135-24*i -: 8], a2_bot[135-24*i -: 8]);
            a3_vb[59-10*i -: 10] <= vsum(a2_top[127-24*i -: 8], a2_mid[127-24*i -: 8], a2_bot[127-24*i -: 8]);
        end
        a3_x   <= a2_x;
        a3_tag <= a2_tag;
    end
end

// A4：横向 [1 2 1] / 16，得到 4 个平滑像素
reg  [95:0]   a4_blur;
reg           a4_v;
reg  [9:0]    a4_x;
reg  [TW-1:0] a4_tag;

integer k;
always @(posedge I_clk) begin
    if(a3_v) begin
        for(k = 0; k < 4; k = k + 1) begin
            a4_blur[95-24*k -: 8] <= hblur(a3_vr[59-10*k -: 10], a3_vr[49-10*k -: 10], a3_vr[39-10*k -: 10]);
            a4_blur[87-24*k -: 8] <= hblur(a3_vg[59-10*k -: 10], a3_vg[49-10*k -: 10], a3_vg[39-10*k -: 10]);
            a4_blur[79-24*k -: 8] <= hblur(a3_vb[59-10*k -: 10], a3_vb[49-10*k -: 10], a3_vb[39-10*k -: 10]);
        end
        a4_x   <= a3_x;
        a4_tag <= a3_tag;
    end
end

always @(posedge I_clk or negedge I_rst_n) begin
    if(!I_rst_n) begin
        a3_v <= 1'b0;
        a4_v <= 1'b0;
    end else begin
        a3_v <= a2_v;
        a4_v <= a3_v;
    end
end


// =============================================================================
// 第二级窗口：平滑图 B -> Sobel + 再平滑 B2
//   第一级输出的第 x 拍是原图第 x-1 拍；它的第 0 拍无效，所以左边界在 x==2 处复制。
// =============================================================================
wire          b2_v;
wire [9:0]    b2_x;
wire [TW-1:0] b2_tag;
wire [143:0]  b2_top, b2_mid, b2_bot;

sty_win3_96 #(.W_GRP(W_GRP), .LEFT_X(2), .TW(TW)) u_win_b (
    .clk(I_clk), .rst_n(I_rst_n), .i_v(a4_v), .i_x(a4_x), .i_pix(a4_blur), .i_tag(a4_tag),
    .o_v(b2_v), .o_x(b2_x), .o_tag(b2_tag),
    .o_top(b2_top), .o_mid(b2_mid), .o_bot(b2_bot)
);

// B3：灰度纵向和/差（Sobel），RGB 纵向和（再平滑）
reg  [59:0]   b3_vs, b3_vr, b3_vg, b3_vb;
reg  [53:0]   b3_vd;
reg           b3_v, b3_mask, b3_first;
reg  [9:0]    b3_x;
reg  [TW-1:0] b3_tag;

always @(posedge I_clk) begin
    if(b2_v) begin
        for(i = 0; i < 6; i = i + 1) begin
            b3_vs[59-10*i -: 10] <= vsum(gray(b2_top[143-24*i -: 24]),
                                         gray(b2_mid[143-24*i -: 24]),
                                         gray(b2_bot[143-24*i -: 24]));
            b3_vd[53-9*i -: 9]   <= {1'b0, gray(b2_top[143-24*i -: 24])}
                                  - {1'b0, gray(b2_bot[143-24*i -: 24])};
            b3_vr[59-10*i -: 10] <= vsum(b2_top[143-24*i -: 8], b2_mid[143-24*i -: 8], b2_bot[143-24*i -: 8]);
            b3_vg[59-10*i -: 10] <= vsum(b2_top[135-24*i -: 8], b2_mid[135-24*i -: 8], b2_bot[135-24*i -: 8]);
            b3_vb[59-10*i -: 10] <= vsum(b2_top[127-24*i -: 8], b2_mid[127-24*i -: 8], b2_bot[127-24*i -: 8]);
        end
        b3_tag   <= b2_tag;
        b3_x     <= b2_x;
        // 第二级窗口完整的区域：x >= 2，y >= 4（统计只取这里）
        b3_mask  <= (b2_x < 10'd2) || (b2_tag[TW-1 -: 11] < 11'd4);
        b3_first <= (b2_x == 10'd0) && (b2_tag[TW-1 -: 11] == 11'd0);
    end
end

// B4：Sobel 幅值、再平滑颜色 B2
reg  [31:0]   b4_mag;
reg  [95:0]   b4_b2;
reg           b4_v, b4_mask, b4_first;
reg  [9:0]    b4_x;
reg  [TW-1:0] b4_tag;
always @(posedge I_clk) begin
    if(b3_v) begin
        for(k = 0; k < 4; k = k + 1) begin
            b4_mag[31-8*k -: 8]  <= sobel8(b3_vs[59-10*k -: 10], b3_vs[39-10*k -: 10],
                                           b3_vd[53-9*k -: 9], b3_vd[44-9*k -: 9], b3_vd[35-9*k -: 9]);
            b4_b2[95-24*k -: 8]  <= hblur(b3_vr[59-10*k -: 10], b3_vr[49-10*k -: 10], b3_vr[39-10*k -: 10]);
            b4_b2[87-24*k -: 8]  <= hblur(b3_vg[59-10*k -: 10], b3_vg[49-10*k -: 10], b3_vg[39-10*k -: 10]);
            b4_b2[79-24*k -: 8]  <= hblur(b3_vb[59-10*k -: 10], b3_vb[49-10*k -: 10], b3_vb[39-10*k -: 10]);
        end
        b4_tag   <= b3_tag;
        b4_x     <= b3_x;
        b4_mask  <= b3_mask;
        b4_first <= b3_first;
    end
end

// =============================================================================

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
wire w3_pre_v;wire[239:0]w3_pre_top,w3_pre_mid,w3_pre_bot;
sty_win3_96 #(.W_GRP(W_GRP),.LEFT_X(3),.TW(TW),.PW(40)) u_win_c(
 .clk(I_clk),.rst_n(I_rst_n),.i_v(b6_v),.i_x(b6_x),.i_pix(b6_pay),.i_tag(b6_tag),
 .o_v(w3_v),.o_x(w3_x),.o_tag(w3_tag),.o_top(w3_top),.o_mid(w3_mid),.o_bot(w3_bot),
 .pre_v(w3_pre_v),.pre_top(w3_pre_top),.pre_mid(w3_pre_mid),.pre_bot(w3_pre_bot));
// Compute the exact Sobel pair on the original window-register RHS. The
// gradients are registered on the SAME edge as o_top/mid/bot, so the existing
// C1 stage still consumes corresponding fine samples without any extra clock.
// Each difference is [-255,255] (signed9), a+/-b is [-510,510] (signed10),
// and the final gradients are [-1020,1020], exactly representable in signed11.
function [21:0] balanced_gradient;
 input [71:0] win;
 reg signed [8:0] a,b,d,e;
 reg signed [9:0] ab,amb;
 reg signed [10:0] gx,gy;
 begin
  a=$signed({1'b0,win[7:0]})-$signed({1'b0,win[71:64]});
  b=$signed({1'b0,win[55:48]})-$signed({1'b0,win[23:16]});
  d=$signed({1'b0,win[31:24]})-$signed({1'b0,win[47:40]});
  e=$signed({1'b0,win[15:8]})-$signed({1'b0,win[63:56]});
  ab=$signed({a[8],a})+$signed({b[8],b});
  amb=$signed({a[8],a})-$signed({b[8],b});
  gx=$signed({ab[9],ab})+$signed({d[8],d,1'b0});
  gy=$signed({amb[9],amb})+$signed({e[8],e,1'b0});
  balanced_gradient={gx,gy};
 end
endfunction
wire[31:0]guide_mag;wire[3:0]guide_edge,guide_support;
wire[287:0] cartoon_y_neighbours;
genvar gp;
generate for(gp=0;gp<4;gp=gp+1)begin: guides
 wire [71:0] pre_coarse_y={
  w3_pre_top[239-40*gp-:8],w3_pre_top[199-40*gp-:8],w3_pre_top[159-40*gp-:8],
  w3_pre_mid[239-40*gp-:8],w3_pre_mid[199-40*gp-:8],w3_pre_mid[159-40*gp-:8],
  w3_pre_bot[239-40*gp-:8],w3_pre_bot[199-40*gp-:8],w3_pre_bot[159-40*gp-:8]};
 reg [21:0] coarse_gradient_r;
 always @(posedge I_clk)if(w3_pre_v)coarse_gradient_r<=balanced_gradient(pre_coarse_y);
 style_guide_v8 #(.EXTERNAL_GRADIENT(1)) u_guide(
  .I_gx(coarse_gradient_r[21:11]),.I_gy(coarse_gradient_r[10:0]),
  .I_edge_detail(w3_tag[1:0]==MODE_EDGE && w3_tag[4:2]==4),
  .I_edge_threshold(w3_tag[1:0]!=MODE_EDGE?8'd32:
      w3_tag[4:2]==0?8'd96:w3_tag[4:2]==1?8'd64:
      w3_tag[4:2]==3?8'd16:w3_tag[4:2]==4?8'd8:8'd32),
  .I_y2({w3_top[239-40*gp-:8],w3_top[199-40*gp-:8],w3_top[159-40*gp-:8],
         w3_mid[239-40*gp-:8],w3_mid[199-40*gp-:8],w3_mid[159-40*gp-:8],
         w3_bot[239-40*gp-:8],w3_bot[199-40*gp-:8],w3_bot[159-40*gp-:8]}),
  .I_fine({w3_top[231-40*gp-:8],w3_top[191-40*gp-:8],w3_top[151-40*gp-:8],
           w3_mid[231-40*gp-:8],w3_mid[191-40*gp-:8],w3_mid[151-40*gp-:8],
           w3_bot[231-40*gp-:8],w3_bot[191-40*gp-:8],w3_bot[151-40*gp-:8]}),
  .O_mag(guide_mag[31-8*gp-:8]),.O_edge(guide_edge[3-gp]),.O_support(guide_support[3-gp]));
 assign cartoon_y_neighbours[287-72*gp-:72]={
  w3_top[239-40*gp-:8],w3_top[199-40*gp-:8],w3_top[159-40*gp-:8],
  w3_mid[239-40*gp-:8],w3_mid[199-40*gp-:8],w3_mid[159-40*gp-:8],
  w3_bot[239-40*gp-:8],w3_bot[199-40*gp-:8],w3_bot[159-40*gp-:8]};
end endgenerate

localparam GUARD_DISABLED=1;
// Pure logic majority counts: no 512-entry lookup ROM or new line storage.
function [3:0] pop9;
 input [8:0] v;reg [1:0] a,b,c;reg [2:0] ab;
 begin
  a={1'b0,v[0]}+{1'b0,v[1]}+{1'b0,v[2]};
  b={1'b0,v[3]}+{1'b0,v[4]}+{1'b0,v[5]};
  c={1'b0,v[6]}+{1'b0,v[7]}+{1'b0,v[8]};
  ab={1'b0,a}+{1'b0,b};pop9={1'b0,ab}+{2'd0,c};
 end
endfunction
function [7:0] cartoon_palette;
 input [71:0] ys;
 reg [8:0] above;reg [4:0] majority;reg [2:0] label;
 reg [7:0] threshold;integer t,n;
 begin
  for(t=0;t<5;t=t+1)begin
   case(t)0:threshold=25;1:threshold=76;2:threshold=127;3:threshold=178;default:threshold=229;endcase
   for(n=0;n<9;n=n+1)above[n]=ys[71-8*n-:8]>threshold;
   majority[t]=pop9(above)>=5;
  end
  label={2'd0,majority[0]}+{2'd0,majority[1]}+{2'd0,majority[2]}+{2'd0,majority[3]}+{2'd0,majority[4]};
  case(label)0:cartoon_palette=0;1:cartoon_palette=51;2:cartoon_palette=102;3:cartoon_palette=153;4:cartoon_palette=204;default:cartoon_palette=255;endcase
 end
endfunction
function [5:0] cut_distance2;
 input [7:0] y;reg [8:0] cut,twice_y;
 begin
  if(y<51)cut=51;else if(y<102)cut=153;else if(y<153)cut=255;else if(y<204)cut=357;else cut=459;
  twice_y={y,1'b0};cut_distance2=twice_y>=cut?twice_y-cut:cut-twice_y;
 end
endfunction
function flat_window;
 input [71:0] ys;
 reg [7:0] y0,y1,y2,y3,y4,y5,y6,y7,y8;
 reg [7:0] lo0,lo1,lo2,hi0,hi1,hi2,lo,hi;
 begin
  {y0,y1,y2,y3,y4,y5,y6,y7,y8}=ys;
  lo0=(y0<y1?y0:y1);lo0=lo0<y2?lo0:y2;
  lo1=(y3<y4?y3:y4);lo1=lo1<y5?lo1:y5;
  lo2=(y6<y7?y6:y7);lo2=lo2<y8?lo2:y8;
  hi0=(y0>y1?y0:y1);hi0=hi0>y2?hi0:y2;
  hi1=(y3>y4?y3:y4);hi1=hi1>y5?hi1:y5;
  hi2=(y6>y7?y6:y7);hi2=hi2>y8?hi2:y8;
  lo=lo0<lo1?lo0:lo1;lo=lo<lo2?lo:lo2;
  hi=hi0>hi1?hi0:hi1;hi=hi>hi2?hi:hi2;
  flat_window=({1'b0,hi}-{1'b0,lo})<=9'd12;
 end
endfunction
function [2:0] rough_weight;
 input [71:0] ys;
 reg signed [9:0] dx,dy;reg [9:0] ax,ay;reg [10:0] sum;
 begin
  dx=$signed({2'd0,ys[47:40]})+$signed({2'd0,ys[31:24]})-$signed({1'b0,ys[39:32],1'b0});
  dy=$signed({2'd0,ys[63:56]})+$signed({2'd0,ys[15:8]})-$signed({1'b0,ys[39:32],1'b0});
  ax=dx[9]?-dx:dx;ay=dy[9]?-dy:dy;sum={1'b0,ax}+{1'b0,ay};rough_weight=sum>=4?3'd4:sum[2:0];
 end
endfunction
function signed [14:0] multiply_weight;
 input signed [8:0] value;input [5:0] weight;
 reg signed [14:0] x,a,b,c,d,e,ab,cd;
 begin
  x={{6{value[8]}},value};
  a=weight[0]?x:15'sd0;b=weight[1]?(x<<<1):15'sd0;
  c=weight[2]?(x<<<2):15'sd0;d=weight[3]?(x<<<3):15'sd0;e=weight[4]?(x<<<4):15'sd0;
  ab=a+b;cd=c+d;multiply_weight=ab+cd+e;
 end
endfunction
function [7:0] guarded_tone;
 input [7:0] palette,y;input [5:0] distance2;input flat,support;input [2:0] noise;
 reg [3:0] margin,missing;reg [5:0] attenuation,weight;
 reg signed [8:0] delta;reg signed [14:0] product;reg signed [15:0] value;
 begin
  margin=distance2<=16?4'd0:distance2>=24?4'd8:distance2-6'd16;
  missing=4'd8-margin;
  // Small 3x4 multiply is explicit shift/add to avoid consuming DSPs.
  attenuation=(missing[0]?{3'd0,noise}:6'd0)+(missing[1]?{2'd0,noise,1'b0}:6'd0)+
              (missing[2]?{1'd0,noise,2'b00}:6'd0)+(missing[3]?{noise,3'b000}:6'd0);
  weight=6'd32-attenuation;
  if(!flat||support||GUARD_DISABLED)guarded_tone=palette;
  else if(weight==32)guarded_tone=palette;
  else begin
   delta=$signed({1'b0,palette})-$signed({1'b0,y});product=multiply_weight(delta,weight);
   value=$signed({8'd0,y})+(product>>>5);guarded_tone=value[7:0];
  end
 end
endfunction
// Reuse the voted six-band palette; higher presets merge its labels rather
// than adding another window, memory, or set of neighbourhood comparators.
function [7:0] cartoon_target;
 input [7:0] palette,y;input [2:0] level;
 reg [8:0] blend;
 begin
  blend={1'b0,palette}+{1'b0,y};
  case(level)
   0:cartoon_target=y;
   1:cartoon_target=blend[8:1];
   3:cartoon_target=palette<=51?8'd0:palette<=153?8'd128:8'd255;
   4:cartoon_target=palette<=102?8'd16:8'd240;
   default:cartoon_target=palette;
  endcase
 end
endfunction
function [23:0] cartoon_colour;
 input [23:0] pixel;input [7:0] target,mag;input is_edge;input [2:0] level;
 reg [7:0] y,lo,hi,c,drop;reg signed [8:0] delta,lower,upper,value;integer ch;
 begin
  y=gray(pixel);lo=pixel[23:16]<pixel[15:8]?pixel[23:16]:pixel[15:8];lo=lo<pixel[7:0]?lo:pixel[7:0];
  hi=pixel[23:16]>pixel[15:8]?pixel[23:16]:pixel[15:8];hi=hi>pixel[7:0]?hi:pixel[7:0];
  lower=-$signed({1'b0,lo});upper=9'sd255-$signed({1'b0,hi});
  delta=$signed({1'b0,target})-$signed({1'b0,y});if(delta<lower)delta=lower;else if(delta>upper)delta=upper;
  for(ch=0;ch<3;ch=ch+1)begin
   value=$signed({1'b0,pixel[23-8*ch-:8]})+delta;c=value[7:0];
   drop=0;
   if(!is_edge || level==0)cartoon_colour[23-8*ch-:8]=c;
   else if(level==4)cartoon_colour[23-8*ch-:8]=8'd0;
   else if(level==3 && mag>=64)cartoon_colour[23-8*ch-:8]=c>>2;
   else begin
    if(level==1)drop=mag<64?(c>>3):(c>>2);
    else if(level==3)drop=c>>1;
    else drop=mag<64?(c>>2):(c>>1);
    cartoon_colour[23-8*ch-:8]=c-drop;
   end
  end
 end
endfunction
reg[95:0]c1_rgb;reg[31:0]c1_y2,c1_mag;reg[3:0]c1_edge;
reg[31:0] c1_palette;reg[23:0] c1_distance;reg[3:0] c1_flat,c1_support;reg[11:0] c1_noise;
reg c1_v,c1_mask;reg[TW-1:0]c1_tag;
// Read the final sketch ink at the SAME edge as C1 magnitude/tag capture.
// Default parameters use two dual-read ERAMs, four pixels per clock. Other
// parameter values retain the original arithmetic implementation in C2.
localparam USE_SKETCH_INK_ROM=(SKETCH_GAIN==8'd49 && SKETCH_FLOOR==8'd12);
wire [31:0] c1_sketch_ink_rom;
generate if(USE_SKETCH_INK_ROM)begin: sketch_ink_rom_path
 sketch_ink_pair_rom_v16 u_ink_01(.clk(I_clk),.enable(w3_v),
  .a({w3_tag[4:2],guide_mag[31:24]}),.b({w3_tag[4:2],guide_mag[23:16]}),
  .qa(c1_sketch_ink_rom[31:24]),.qb(c1_sketch_ink_rom[23:16]));
 sketch_ink_pair_rom_v16 u_ink_23(.clk(I_clk),.enable(w3_v),
  .a({w3_tag[4:2],guide_mag[15:8]}),.b({w3_tag[4:2],guide_mag[7:0]}),
  .qa(c1_sketch_ink_rom[15:8]),.qb(c1_sketch_ink_rom[7:0]));
end else begin: sketch_original_parameter_path
 assign c1_sketch_ink_rom=32'd0;
end endgenerate
always @(posedge I_clk)if(w3_v)begin
 for(k=0;k<4;k=k+1)begin
  c1_rgb[95-24*k-:24]<=w3_mid[183-40*k-:24];
  c1_y2[31-8*k-:8]<=w3_mid[199-40*k-:8];
  c1_palette[31-8*k-:8]<=cartoon_palette(cartoon_y_neighbours[287-72*k-:72]);
  c1_distance[23-6*k-:6]<=cut_distance2(w3_mid[199-40*k-:8]);
  c1_flat[3-k]<=flat_window(cartoon_y_neighbours[287-72*k-:72]);
  c1_noise[11-3*k-:3]<=rough_weight(cartoon_y_neighbours[287-72*k-:72]);
 end
 c1_mag<=guide_mag;c1_edge<=guide_edge;c1_support<=guide_support;c1_tag<=w3_tag;
 c1_mask<=(w3_x<3)||(w3_tag[TW-1-:11]<6);
end

// Local trusted magnitude uses a fixed ink calibration. A distant bright
// texture/noise patch cannot change the gain or erase this pixel's weak line.
// Original paper response and subtractive ink rendering are retained.
reg[95:0]c2_px;reg c2_v,c2_mask;reg[TW-1:0]c2_tag;
reg[31:0]c2_mag;reg[3:0]c2_edge;
reg[31:0]c2_target;
reg[23:0]pp;reg[7:0]sketch_dm,sketch_ink,sketch_paper;
reg[15:0]sketch_prod;
wire [7:0] sketch_floor_now=c1_tag[4:2]==0?8'd64:c1_tag[4:2]==1?8'd32:
    c1_tag[4:2]==3?8'd6:c1_tag[4:2]==4?8'd2:SKETCH_FLOOR;
// Equivalent shared five-level gain select. Default-parameter 8x8 products
// remain in the existing C2 clocked stage; no extra video pipeline register.
reg [15:0] sketch_gain_now;
always @* begin
 case(c1_tag[4:2])
  0:sketch_gain_now=8'd8;
  1:sketch_gain_now=8'd20;
  3:sketch_gain_now=8'd80;
  4:sketch_gain_now=8'd128;
  default:sketch_gain_now=SKETCH_GAIN;
 endcase
end
always @(posedge I_clk)if(c1_v)begin
 for(k=0;k<4;k=k+1)begin
  pp=c1_rgb[95-24*k-:24];
  case(c1_tag[1:0])
   MODE_SKETCH:begin
    if(USE_SKETCH_INK_ROM)sketch_ink=c1_sketch_ink_rom[31-8*k-:8];
    else begin
     sketch_dm=c1_mag[31-8*k-:8]>sketch_floor_now?c1_mag[31-8*k-:8]-sketch_floor_now:0;
     sketch_prod=sketch_dm*sketch_gain_now;
     sketch_ink=sketch_prod[15:12]!=0?8'd255:sketch_prod[11:4];
    end
    sketch_paper=8'd255-{3'd0,~c1_y2[31-8*k-:5]};
    c2_px[95-24*k-:24]<={3{sketch_paper>sketch_ink?sketch_paper-sketch_ink:8'd0}};
   end
   MODE_EDGE:c2_px[95-24*k-:24]<={24{c1_edge[3-k]}};
   default:begin
    c2_target[31-8*k-:8]<=cartoon_target(
       guarded_tone(c1_palette[31-8*k-:8],c1_y2[31-8*k-:8],c1_distance[23-6*k-:6],c1_flat[3-k],c1_support[3-k],c1_noise[11-3*k-:3]),
       c1_y2[31-8*k-:8],c1_tag[4:2]);
    c2_px[95-24*k-:24]<=c1_rgb[95-24*k-:24];
   end
  endcase
 end
 c2_tag<=c1_tag;c2_mask<=c1_mask;
 c2_mag<=c1_mag;c2_edge<=c1_edge;
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
  else if(mode_o==MODE_CARTOON)begin
   for(k=0;k<4;k=k+1)O_tdata[95-24*k-:24]<=cartoon_colour(c2_px[95-24*k-:24],c2_target[31-8*k-:8],c2_mag[31-8*k-:8],c2_edge[3-k],c2_tag[4:2]);
  end
  else O_tdata<=c2_px;
 end
end
endmodule
module sty_win3_96 #(
    parameter W_GRP  = 320,
    parameter LEFT_X = 1,
    parameter TW     = 8,
    parameter PW     = 24
)(
    input               clk,
    input               rst_n,
    input               i_v,
    input      [9:0]    i_x,
    input      [4*PW-1:0]   i_pix,
    input      [TW-1:0] i_tag,
    output reg          o_v,
    output reg [9:0]    o_x,
    output reg [TW-1:0] o_tag,
    output reg [6*PW-1:0]  o_top,
    output reg [6*PW-1:0]  o_mid,
    output reg [6*PW-1:0]  o_bot,
    output wire pre_v,
    output wire [6*PW-1:0] pre_top,pre_mid,pre_bot
);

// 行缓存：line1 = 上一行，line2 = 上上行。同步地址读，不复位（才能映射 ERAM）
reg [4*PW-1:0] line1_mem [0:W_GRP-1]; // synthesis ram_style = bram
reg [4*PW-1:0] line2_mem [0:W_GRP-1]; // synthesis ram_style = bram
reg [9:0]  rd_addr;
wire [4*PW-1:0] rd1 = line1_mem[rd_addr];
wire [4*PW-1:0] rd2 = line2_mem[rd_addr];

reg          s1_v;
reg [9:0]    s1_x;
reg [4*PW-1:0]   s1_pix;
reg [TW-1:0] s1_tag;

always @(posedge clk) begin
    if(i_v) rd_addr <= i_x;
end

always @(posedge clk) begin
    if(s1_v) line1_mem[s1_x] <= s1_pix;
end

always @(posedge clk) begin
    if(s1_v) line2_mem[s1_x] <= rd1;
end

always @(posedge clk or negedge rst_n) begin
    if(!rst_n) begin
        s1_v <= 1'b0;
        o_v  <= 1'b0;
    end else begin
        s1_v <= i_v;
        o_v  <= s1_v;
    end
end

always @(posedge clk) begin
    if(i_v) begin
        s1_x   <= i_x;
        s1_pix <= i_pix;
        s1_tag <= i_tag;
    end
end

reg [4*PW-1:0] a_top, a_mid, a_bot;
reg [PW-1:0] b_top, b_mid, b_bot;
wire left_edge = (s1_x == LEFT_X);
// Passive combinational taps of the original output-register RHS. All old
// register assignments, valid pulses, tags and line-memory accesses stay as-is.
assign pre_v=s1_v;
assign pre_top={(left_edge ? a_top[4*PW-1 -: PW] : b_top), a_top, rd2[4*PW-1 -: PW]};
assign pre_mid={(left_edge ? a_mid[4*PW-1 -: PW] : b_mid), a_mid, rd1[4*PW-1 -: PW]};
assign pre_bot={(left_edge ? a_bot[4*PW-1 -: PW] : b_bot), a_bot, s1_pix[4*PW-1 -: PW]};

always @(posedge clk) begin
    if(s1_v) begin
        o_top <= {(left_edge ? a_top[4*PW-1 -: PW] : b_top), a_top, rd2[4*PW-1 -: PW]};
        o_mid <= {(left_edge ? a_mid[4*PW-1 -: PW] : b_mid), a_mid, rd1[4*PW-1 -: PW]};
        o_bot <= {(left_edge ? a_bot[4*PW-1 -: PW] : b_bot), a_bot, s1_pix[4*PW-1 -: PW]};
        b_top <= a_top[PW-1:0];  b_mid <= a_mid[PW-1:0];  b_bot <= a_bot[PW-1:0];
        a_top <= rd2;          a_mid <= rd1;          a_bot <= s1_pix;
        o_x   <= s1_x;
        o_tag <= s1_tag;
    end
end

endmodule

(* keep_hierarchy="true" *)
module sty_bypass_memory(input wire clk,rst_n,input wire [95:0] din,output wire [95:0] dout);
reg [95:0] shift[0:12];
integer n;
always @(posedge clk)begin
    shift[0]<=din;for(n=1;n<13;n=n+1)shift[n]<=shift[n-1];
end
assign dout=shift[12];
endmodule

module median4_eram(input wire clk,input wire [107:0] bands,output wire [11:0] median);
wire [8:0] address[0:3][0:4];
wire [4:0] ge5[0:3];
genvar p,t,n,g;
generate
for(p=0;p<4;p=p+1)begin: pixels
    for(t=0;t<5;t=t+1)begin: thresholds
        for(n=0;n<9;n=n+1)begin: samples
            assign address[p][t][n]=bands[107-27*p-3*n-:3]<=t;
        end
    end
    assign median[11-3*p-:3]=!ge5[p][4]?3'd5:!ge5[p][3]?3'd4:
        !ge5[p][2]?3'd3:!ge5[p][1]?3'd2:!ge5[p][0]?3'd1:3'd0;
end
for(t=0;t<5;t=t+1)begin: threshold_roms
    for(g=0;g<2;g=g+1)begin: pairs
        median_majority_pair_rom u_rom(.clk(clk),.a(address[2*g][t]),.b(address[2*g+1][t]),
            .qa(ge5[2*g][t]),.qb(ge5[2*g+1][t]));
    end
end
endgenerate
endmodule
(* keep_hierarchy="true" *)
module median_majority_pair_rom(input wire clk,input wire [8:0] a,b,output reg qa,qb);
function majority9;
    input [8:0] v;
    reg [1:0] a3,b3,c3;reg [3:0] count;
    begin
        a3={1'b0,v[0]}+{1'b0,v[1]}+{1'b0,v[2]};
        b3={1'b0,v[3]}+{1'b0,v[4]}+{1'b0,v[5]};
        c3={1'b0,v[6]}+{1'b0,v[7]}+{1'b0,v[8]};
        count={2'd0,a3}+{2'd0,b3}+{2'd0,c3};majority9=count>=5;
    end
endfunction
always @(posedge clk)begin qa<=majority9(a);qb<=majority9(b);end
endmodule

// Embedded two-read, one-clock ROM. The official TD rom_style=bram
// inference directive selects ERAM; simulation uses the identical read logic.
(* keep_hierarchy="true" *) module sketch_ink_pair_rom_v16(
 input wire clk,enable,input wire[10:0]a,b,output wire[7:0]qa,qb
);
 (* rom_style="bram" *) reg[7:0]memory[0:2047];
 reg[7:0]ra,rb;
 initial begin
  memory[0]=8'h00;
  memory[1]=8'h00;
  memory[2]=8'h00;
  memory[3]=8'h00;
  memory[4]=8'h00;
  memory[5]=8'h00;
  memory[6]=8'h00;
  memory[7]=8'h00;
  memory[8]=8'h00;
  memory[9]=8'h00;
  memory[10]=8'h00;
  memory[11]=8'h00;
  memory[12]=8'h00;
  memory[13]=8'h00;
  memory[14]=8'h00;
  memory[15]=8'h00;
  memory[16]=8'h00;
  memory[17]=8'h00;
  memory[18]=8'h00;
  memory[19]=8'h00;
  memory[20]=8'h00;
  memory[21]=8'h00;
  memory[22]=8'h00;
  memory[23]=8'h00;
  memory[24]=8'h00;
  memory[25]=8'h00;
  memory[26]=8'h00;
  memory[27]=8'h00;
  memory[28]=8'h00;
  memory[29]=8'h00;
  memory[30]=8'h00;
  memory[31]=8'h00;
  memory[32]=8'h00;
  memory[33]=8'h00;
  memory[34]=8'h00;
  memory[35]=8'h00;
  memory[36]=8'h00;
  memory[37]=8'h00;
  memory[38]=8'h00;
  memory[39]=8'h00;
  memory[40]=8'h00;
  memory[41]=8'h00;
  memory[42]=8'h00;
  memory[43]=8'h00;
  memory[44]=8'h00;
  memory[45]=8'h00;
  memory[46]=8'h00;
  memory[47]=8'h00;
  memory[48]=8'h00;
  memory[49]=8'h00;
  memory[50]=8'h00;
  memory[51]=8'h00;
  memory[52]=8'h00;
  memory[53]=8'h00;
  memory[54]=8'h00;
  memory[55]=8'h00;
  memory[56]=8'h00;
  memory[57]=8'h00;
  memory[58]=8'h00;
  memory[59]=8'h00;
  memory[60]=8'h00;
  memory[61]=8'h00;
  memory[62]=8'h00;
  memory[63]=8'h00;
  memory[64]=8'h00;
  memory[65]=8'h00;
  memory[66]=8'h01;
  memory[67]=8'h01;
  memory[68]=8'h02;
  memory[69]=8'h02;
  memory[70]=8'h03;
  memory[71]=8'h03;
  memory[72]=8'h04;
  memory[73]=8'h04;
  memory[74]=8'h05;
  memory[75]=8'h05;
  memory[76]=8'h06;
  memory[77]=8'h06;
  memory[78]=8'h07;
  memory[79]=8'h07;
  memory[80]=8'h08;
  memory[81]=8'h08;
  memory[82]=8'h09;
  memory[83]=8'h09;
  memory[84]=8'h0a;
  memory[85]=8'h0a;
  memory[86]=8'h0b;
  memory[87]=8'h0b;
  memory[88]=8'h0c;
  memory[89]=8'h0c;
  memory[90]=8'h0d;
  memory[91]=8'h0d;
  memory[92]=8'h0e;
  memory[93]=8'h0e;
  memory[94]=8'h0f;
  memory[95]=8'h0f;
  memory[96]=8'h10;
  memory[97]=8'h10;
  memory[98]=8'h11;
  memory[99]=8'h11;
  memory[100]=8'h12;
  memory[101]=8'h12;
  memory[102]=8'h13;
  memory[103]=8'h13;
  memory[104]=8'h14;
  memory[105]=8'h14;
  memory[106]=8'h15;
  memory[107]=8'h15;
  memory[108]=8'h16;
  memory[109]=8'h16;
  memory[110]=8'h17;
  memory[111]=8'h17;
  memory[112]=8'h18;
  memory[113]=8'h18;
  memory[114]=8'h19;
  memory[115]=8'h19;
  memory[116]=8'h1a;
  memory[117]=8'h1a;
  memory[118]=8'h1b;
  memory[119]=8'h1b;
  memory[120]=8'h1c;
  memory[121]=8'h1c;
  memory[122]=8'h1d;
  memory[123]=8'h1d;
  memory[124]=8'h1e;
  memory[125]=8'h1e;
  memory[126]=8'h1f;
  memory[127]=8'h1f;
  memory[128]=8'h20;
  memory[129]=8'h20;
  memory[130]=8'h21;
  memory[131]=8'h21;
  memory[132]=8'h22;
  memory[133]=8'h22;
  memory[134]=8'h23;
  memory[135]=8'h23;
  memory[136]=8'h24;
  memory[137]=8'h24;
  memory[138]=8'h25;
  memory[139]=8'h25;
  memory[140]=8'h26;
  memory[141]=8'h26;
  memory[142]=8'h27;
  memory[143]=8'h27;
  memory[144]=8'h28;
  memory[145]=8'h28;
  memory[146]=8'h29;
  memory[147]=8'h29;
  memory[148]=8'h2a;
  memory[149]=8'h2a;
  memory[150]=8'h2b;
  memory[151]=8'h2b;
  memory[152]=8'h2c;
  memory[153]=8'h2c;
  memory[154]=8'h2d;
  memory[155]=8'h2d;
  memory[156]=8'h2e;
  memory[157]=8'h2e;
  memory[158]=8'h2f;
  memory[159]=8'h2f;
  memory[160]=8'h30;
  memory[161]=8'h30;
  memory[162]=8'h31;
  memory[163]=8'h31;
  memory[164]=8'h32;
  memory[165]=8'h32;
  memory[166]=8'h33;
  memory[167]=8'h33;
  memory[168]=8'h34;
  memory[169]=8'h34;
  memory[170]=8'h35;
  memory[171]=8'h35;
  memory[172]=8'h36;
  memory[173]=8'h36;
  memory[174]=8'h37;
  memory[175]=8'h37;
  memory[176]=8'h38;
  memory[177]=8'h38;
  memory[178]=8'h39;
  memory[179]=8'h39;
  memory[180]=8'h3a;
  memory[181]=8'h3a;
  memory[182]=8'h3b;
  memory[183]=8'h3b;
  memory[184]=8'h3c;
  memory[185]=8'h3c;
  memory[186]=8'h3d;
  memory[187]=8'h3d;
  memory[188]=8'h3e;
  memory[189]=8'h3e;
  memory[190]=8'h3f;
  memory[191]=8'h3f;
  memory[192]=8'h40;
  memory[193]=8'h40;
  memory[194]=8'h41;
  memory[195]=8'h41;
  memory[196]=8'h42;
  memory[197]=8'h42;
  memory[198]=8'h43;
  memory[199]=8'h43;
  memory[200]=8'h44;
  memory[201]=8'h44;
  memory[202]=8'h45;
  memory[203]=8'h45;
  memory[204]=8'h46;
  memory[205]=8'h46;
  memory[206]=8'h47;
  memory[207]=8'h47;
  memory[208]=8'h48;
  memory[209]=8'h48;
  memory[210]=8'h49;
  memory[211]=8'h49;
  memory[212]=8'h4a;
  memory[213]=8'h4a;
  memory[214]=8'h4b;
  memory[215]=8'h4b;
  memory[216]=8'h4c;
  memory[217]=8'h4c;
  memory[218]=8'h4d;
  memory[219]=8'h4d;
  memory[220]=8'h4e;
  memory[221]=8'h4e;
  memory[222]=8'h4f;
  memory[223]=8'h4f;
  memory[224]=8'h50;
  memory[225]=8'h50;
  memory[226]=8'h51;
  memory[227]=8'h51;
  memory[228]=8'h52;
  memory[229]=8'h52;
  memory[230]=8'h53;
  memory[231]=8'h53;
  memory[232]=8'h54;
  memory[233]=8'h54;
  memory[234]=8'h55;
  memory[235]=8'h55;
  memory[236]=8'h56;
  memory[237]=8'h56;
  memory[238]=8'h57;
  memory[239]=8'h57;
  memory[240]=8'h58;
  memory[241]=8'h58;
  memory[242]=8'h59;
  memory[243]=8'h59;
  memory[244]=8'h5a;
  memory[245]=8'h5a;
  memory[246]=8'h5b;
  memory[247]=8'h5b;
  memory[248]=8'h5c;
  memory[249]=8'h5c;
  memory[250]=8'h5d;
  memory[251]=8'h5d;
  memory[252]=8'h5e;
  memory[253]=8'h5e;
  memory[254]=8'h5f;
  memory[255]=8'h5f;
  memory[256]=8'h00;
  memory[257]=8'h00;
  memory[258]=8'h00;
  memory[259]=8'h00;
  memory[260]=8'h00;
  memory[261]=8'h00;
  memory[262]=8'h00;
  memory[263]=8'h00;
  memory[264]=8'h00;
  memory[265]=8'h00;
  memory[266]=8'h00;
  memory[267]=8'h00;
  memory[268]=8'h00;
  memory[269]=8'h00;
  memory[270]=8'h00;
  memory[271]=8'h00;
  memory[272]=8'h00;
  memory[273]=8'h00;
  memory[274]=8'h00;
  memory[275]=8'h00;
  memory[276]=8'h00;
  memory[277]=8'h00;
  memory[278]=8'h00;
  memory[279]=8'h00;
  memory[280]=8'h00;
  memory[281]=8'h00;
  memory[282]=8'h00;
  memory[283]=8'h00;
  memory[284]=8'h00;
  memory[285]=8'h00;
  memory[286]=8'h00;
  memory[287]=8'h00;
  memory[288]=8'h00;
  memory[289]=8'h01;
  memory[290]=8'h02;
  memory[291]=8'h03;
  memory[292]=8'h05;
  memory[293]=8'h06;
  memory[294]=8'h07;
  memory[295]=8'h08;
  memory[296]=8'h0a;
  memory[297]=8'h0b;
  memory[298]=8'h0c;
  memory[299]=8'h0d;
  memory[300]=8'h0f;
  memory[301]=8'h10;
  memory[302]=8'h11;
  memory[303]=8'h12;
  memory[304]=8'h14;
  memory[305]=8'h15;
  memory[306]=8'h16;
  memory[307]=8'h17;
  memory[308]=8'h19;
  memory[309]=8'h1a;
  memory[310]=8'h1b;
  memory[311]=8'h1c;
  memory[312]=8'h1e;
  memory[313]=8'h1f;
  memory[314]=8'h20;
  memory[315]=8'h21;
  memory[316]=8'h23;
  memory[317]=8'h24;
  memory[318]=8'h25;
  memory[319]=8'h26;
  memory[320]=8'h28;
  memory[321]=8'h29;
  memory[322]=8'h2a;
  memory[323]=8'h2b;
  memory[324]=8'h2d;
  memory[325]=8'h2e;
  memory[326]=8'h2f;
  memory[327]=8'h30;
  memory[328]=8'h32;
  memory[329]=8'h33;
  memory[330]=8'h34;
  memory[331]=8'h35;
  memory[332]=8'h37;
  memory[333]=8'h38;
  memory[334]=8'h39;
  memory[335]=8'h3a;
  memory[336]=8'h3c;
  memory[337]=8'h3d;
  memory[338]=8'h3e;
  memory[339]=8'h3f;
  memory[340]=8'h41;
  memory[341]=8'h42;
  memory[342]=8'h43;
  memory[343]=8'h44;
  memory[344]=8'h46;
  memory[345]=8'h47;
  memory[346]=8'h48;
  memory[347]=8'h49;
  memory[348]=8'h4b;
  memory[349]=8'h4c;
  memory[350]=8'h4d;
  memory[351]=8'h4e;
  memory[352]=8'h50;
  memory[353]=8'h51;
  memory[354]=8'h52;
  memory[355]=8'h53;
  memory[356]=8'h55;
  memory[357]=8'h56;
  memory[358]=8'h57;
  memory[359]=8'h58;
  memory[360]=8'h5a;
  memory[361]=8'h5b;
  memory[362]=8'h5c;
  memory[363]=8'h5d;
  memory[364]=8'h5f;
  memory[365]=8'h60;
  memory[366]=8'h61;
  memory[367]=8'h62;
  memory[368]=8'h64;
  memory[369]=8'h65;
  memory[370]=8'h66;
  memory[371]=8'h67;
  memory[372]=8'h69;
  memory[373]=8'h6a;
  memory[374]=8'h6b;
  memory[375]=8'h6c;
  memory[376]=8'h6e;
  memory[377]=8'h6f;
  memory[378]=8'h70;
  memory[379]=8'h71;
  memory[380]=8'h73;
  memory[381]=8'h74;
  memory[382]=8'h75;
  memory[383]=8'h76;
  memory[384]=8'h78;
  memory[385]=8'h79;
  memory[386]=8'h7a;
  memory[387]=8'h7b;
  memory[388]=8'h7d;
  memory[389]=8'h7e;
  memory[390]=8'h7f;
  memory[391]=8'h80;
  memory[392]=8'h82;
  memory[393]=8'h83;
  memory[394]=8'h84;
  memory[395]=8'h85;
  memory[396]=8'h87;
  memory[397]=8'h88;
  memory[398]=8'h89;
  memory[399]=8'h8a;
  memory[400]=8'h8c;
  memory[401]=8'h8d;
  memory[402]=8'h8e;
  memory[403]=8'h8f;
  memory[404]=8'h91;
  memory[405]=8'h92;
  memory[406]=8'h93;
  memory[407]=8'h94;
  memory[408]=8'h96;
  memory[409]=8'h97;
  memory[410]=8'h98;
  memory[411]=8'h99;
  memory[412]=8'h9b;
  memory[413]=8'h9c;
  memory[414]=8'h9d;
  memory[415]=8'h9e;
  memory[416]=8'ha0;
  memory[417]=8'ha1;
  memory[418]=8'ha2;
  memory[419]=8'ha3;
  memory[420]=8'ha5;
  memory[421]=8'ha6;
  memory[422]=8'ha7;
  memory[423]=8'ha8;
  memory[424]=8'haa;
  memory[425]=8'hab;
  memory[426]=8'hac;
  memory[427]=8'had;
  memory[428]=8'haf;
  memory[429]=8'hb0;
  memory[430]=8'hb1;
  memory[431]=8'hb2;
  memory[432]=8'hb4;
  memory[433]=8'hb5;
  memory[434]=8'hb6;
  memory[435]=8'hb7;
  memory[436]=8'hb9;
  memory[437]=8'hba;
  memory[438]=8'hbb;
  memory[439]=8'hbc;
  memory[440]=8'hbe;
  memory[441]=8'hbf;
  memory[442]=8'hc0;
  memory[443]=8'hc1;
  memory[444]=8'hc3;
  memory[445]=8'hc4;
  memory[446]=8'hc5;
  memory[447]=8'hc6;
  memory[448]=8'hc8;
  memory[449]=8'hc9;
  memory[450]=8'hca;
  memory[451]=8'hcb;
  memory[452]=8'hcd;
  memory[453]=8'hce;
  memory[454]=8'hcf;
  memory[455]=8'hd0;
  memory[456]=8'hd2;
  memory[457]=8'hd3;
  memory[458]=8'hd4;
  memory[459]=8'hd5;
  memory[460]=8'hd7;
  memory[461]=8'hd8;
  memory[462]=8'hd9;
  memory[463]=8'hda;
  memory[464]=8'hdc;
  memory[465]=8'hdd;
  memory[466]=8'hde;
  memory[467]=8'hdf;
  memory[468]=8'he1;
  memory[469]=8'he2;
  memory[470]=8'he3;
  memory[471]=8'he4;
  memory[472]=8'he6;
  memory[473]=8'he7;
  memory[474]=8'he8;
  memory[475]=8'he9;
  memory[476]=8'heb;
  memory[477]=8'hec;
  memory[478]=8'hed;
  memory[479]=8'hee;
  memory[480]=8'hf0;
  memory[481]=8'hf1;
  memory[482]=8'hf2;
  memory[483]=8'hf3;
  memory[484]=8'hf5;
  memory[485]=8'hf6;
  memory[486]=8'hf7;
  memory[487]=8'hf8;
  memory[488]=8'hfa;
  memory[489]=8'hfb;
  memory[490]=8'hfc;
  memory[491]=8'hfd;
  memory[492]=8'hff;
  memory[493]=8'hff;
  memory[494]=8'hff;
  memory[495]=8'hff;
  memory[496]=8'hff;
  memory[497]=8'hff;
  memory[498]=8'hff;
  memory[499]=8'hff;
  memory[500]=8'hff;
  memory[501]=8'hff;
  memory[502]=8'hff;
  memory[503]=8'hff;
  memory[504]=8'hff;
  memory[505]=8'hff;
  memory[506]=8'hff;
  memory[507]=8'hff;
  memory[508]=8'hff;
  memory[509]=8'hff;
  memory[510]=8'hff;
  memory[511]=8'hff;
  memory[512]=8'h00;
  memory[513]=8'h00;
  memory[514]=8'h00;
  memory[515]=8'h00;
  memory[516]=8'h00;
  memory[517]=8'h00;
  memory[518]=8'h00;
  memory[519]=8'h00;
  memory[520]=8'h00;
  memory[521]=8'h00;
  memory[522]=8'h00;
  memory[523]=8'h00;
  memory[524]=8'h00;
  memory[525]=8'h03;
  memory[526]=8'h06;
  memory[527]=8'h09;
  memory[528]=8'h0c;
  memory[529]=8'h0f;
  memory[530]=8'h12;
  memory[531]=8'h15;
  memory[532]=8'h18;
  memory[533]=8'h1b;
  memory[534]=8'h1e;
  memory[535]=8'h21;
  memory[536]=8'h24;
  memory[537]=8'h27;
  memory[538]=8'h2a;
  memory[539]=8'h2d;
  memory[540]=8'h31;
  memory[541]=8'h34;
  memory[542]=8'h37;
  memory[543]=8'h3a;
  memory[544]=8'h3d;
  memory[545]=8'h40;
  memory[546]=8'h43;
  memory[547]=8'h46;
  memory[548]=8'h49;
  memory[549]=8'h4c;
  memory[550]=8'h4f;
  memory[551]=8'h52;
  memory[552]=8'h55;
  memory[553]=8'h58;
  memory[554]=8'h5b;
  memory[555]=8'h5e;
  memory[556]=8'h62;
  memory[557]=8'h65;
  memory[558]=8'h68;
  memory[559]=8'h6b;
  memory[560]=8'h6e;
  memory[561]=8'h71;
  memory[562]=8'h74;
  memory[563]=8'h77;
  memory[564]=8'h7a;
  memory[565]=8'h7d;
  memory[566]=8'h80;
  memory[567]=8'h83;
  memory[568]=8'h86;
  memory[569]=8'h89;
  memory[570]=8'h8c;
  memory[571]=8'h8f;
  memory[572]=8'h93;
  memory[573]=8'h96;
  memory[574]=8'h99;
  memory[575]=8'h9c;
  memory[576]=8'h9f;
  memory[577]=8'ha2;
  memory[578]=8'ha5;
  memory[579]=8'ha8;
  memory[580]=8'hab;
  memory[581]=8'hae;
  memory[582]=8'hb1;
  memory[583]=8'hb4;
  memory[584]=8'hb7;
  memory[585]=8'hba;
  memory[586]=8'hbd;
  memory[587]=8'hc0;
  memory[588]=8'hc4;
  memory[589]=8'hc7;
  memory[590]=8'hca;
  memory[591]=8'hcd;
  memory[592]=8'hd0;
  memory[593]=8'hd3;
  memory[594]=8'hd6;
  memory[595]=8'hd9;
  memory[596]=8'hdc;
  memory[597]=8'hdf;
  memory[598]=8'he2;
  memory[599]=8'he5;
  memory[600]=8'he8;
  memory[601]=8'heb;
  memory[602]=8'hee;
  memory[603]=8'hf1;
  memory[604]=8'hf5;
  memory[605]=8'hf8;
  memory[606]=8'hfb;
  memory[607]=8'hfe;
  memory[608]=8'hff;
  memory[609]=8'hff;
  memory[610]=8'hff;
  memory[611]=8'hff;
  memory[612]=8'hff;
  memory[613]=8'hff;
  memory[614]=8'hff;
  memory[615]=8'hff;
  memory[616]=8'hff;
  memory[617]=8'hff;
  memory[618]=8'hff;
  memory[619]=8'hff;
  memory[620]=8'hff;
  memory[621]=8'hff;
  memory[622]=8'hff;
  memory[623]=8'hff;
  memory[624]=8'hff;
  memory[625]=8'hff;
  memory[626]=8'hff;
  memory[627]=8'hff;
  memory[628]=8'hff;
  memory[629]=8'hff;
  memory[630]=8'hff;
  memory[631]=8'hff;
  memory[632]=8'hff;
  memory[633]=8'hff;
  memory[634]=8'hff;
  memory[635]=8'hff;
  memory[636]=8'hff;
  memory[637]=8'hff;
  memory[638]=8'hff;
  memory[639]=8'hff;
  memory[640]=8'hff;
  memory[641]=8'hff;
  memory[642]=8'hff;
  memory[643]=8'hff;
  memory[644]=8'hff;
  memory[645]=8'hff;
  memory[646]=8'hff;
  memory[647]=8'hff;
  memory[648]=8'hff;
  memory[649]=8'hff;
  memory[650]=8'hff;
  memory[651]=8'hff;
  memory[652]=8'hff;
  memory[653]=8'hff;
  memory[654]=8'hff;
  memory[655]=8'hff;
  memory[656]=8'hff;
  memory[657]=8'hff;
  memory[658]=8'hff;
  memory[659]=8'hff;
  memory[660]=8'hff;
  memory[661]=8'hff;
  memory[662]=8'hff;
  memory[663]=8'hff;
  memory[664]=8'hff;
  memory[665]=8'hff;
  memory[666]=8'hff;
  memory[667]=8'hff;
  memory[668]=8'hff;
  memory[669]=8'hff;
  memory[670]=8'hff;
  memory[671]=8'hff;
  memory[672]=8'hff;
  memory[673]=8'hff;
  memory[674]=8'hff;
  memory[675]=8'hff;
  memory[676]=8'hff;
  memory[677]=8'hff;
  memory[678]=8'hff;
  memory[679]=8'hff;
  memory[680]=8'hff;
  memory[681]=8'hff;
  memory[682]=8'hff;
  memory[683]=8'hff;
  memory[684]=8'hff;
  memory[685]=8'hff;
  memory[686]=8'hff;
  memory[687]=8'hff;
  memory[688]=8'hff;
  memory[689]=8'hff;
  memory[690]=8'hff;
  memory[691]=8'hff;
  memory[692]=8'hff;
  memory[693]=8'hff;
  memory[694]=8'hff;
  memory[695]=8'hff;
  memory[696]=8'hff;
  memory[697]=8'hff;
  memory[698]=8'hff;
  memory[699]=8'hff;
  memory[700]=8'hff;
  memory[701]=8'hff;
  memory[702]=8'hff;
  memory[703]=8'hff;
  memory[704]=8'hff;
  memory[705]=8'hff;
  memory[706]=8'hff;
  memory[707]=8'hff;
  memory[708]=8'hff;
  memory[709]=8'hff;
  memory[710]=8'hff;
  memory[711]=8'hff;
  memory[712]=8'hff;
  memory[713]=8'hff;
  memory[714]=8'hff;
  memory[715]=8'hff;
  memory[716]=8'hff;
  memory[717]=8'hff;
  memory[718]=8'hff;
  memory[719]=8'hff;
  memory[720]=8'hff;
  memory[721]=8'hff;
  memory[722]=8'hff;
  memory[723]=8'hff;
  memory[724]=8'hff;
  memory[725]=8'hff;
  memory[726]=8'hff;
  memory[727]=8'hff;
  memory[728]=8'hff;
  memory[729]=8'hff;
  memory[730]=8'hff;
  memory[731]=8'hff;
  memory[732]=8'hff;
  memory[733]=8'hff;
  memory[734]=8'hff;
  memory[735]=8'hff;
  memory[736]=8'hff;
  memory[737]=8'hff;
  memory[738]=8'hff;
  memory[739]=8'hff;
  memory[740]=8'hff;
  memory[741]=8'hff;
  memory[742]=8'hff;
  memory[743]=8'hff;
  memory[744]=8'hff;
  memory[745]=8'hff;
  memory[746]=8'hff;
  memory[747]=8'hff;
  memory[748]=8'hff;
  memory[749]=8'hff;
  memory[750]=8'hff;
  memory[751]=8'hff;
  memory[752]=8'hff;
  memory[753]=8'hff;
  memory[754]=8'hff;
  memory[755]=8'hff;
  memory[756]=8'hff;
  memory[757]=8'hff;
  memory[758]=8'hff;
  memory[759]=8'hff;
  memory[760]=8'hff;
  memory[761]=8'hff;
  memory[762]=8'hff;
  memory[763]=8'hff;
  memory[764]=8'hff;
  memory[765]=8'hff;
  memory[766]=8'hff;
  memory[767]=8'hff;
  memory[768]=8'h00;
  memory[769]=8'h00;
  memory[770]=8'h00;
  memory[771]=8'h00;
  memory[772]=8'h00;
  memory[773]=8'h00;
  memory[774]=8'h00;
  memory[775]=8'h05;
  memory[776]=8'h0a;
  memory[777]=8'h0f;
  memory[778]=8'h14;
  memory[779]=8'h19;
  memory[780]=8'h1e;
  memory[781]=8'h23;
  memory[782]=8'h28;
  memory[783]=8'h2d;
  memory[784]=8'h32;
  memory[785]=8'h37;
  memory[786]=8'h3c;
  memory[787]=8'h41;
  memory[788]=8'h46;
  memory[789]=8'h4b;
  memory[790]=8'h50;
  memory[791]=8'h55;
  memory[792]=8'h5a;
  memory[793]=8'h5f;
  memory[794]=8'h64;
  memory[795]=8'h69;
  memory[796]=8'h6e;
  memory[797]=8'h73;
  memory[798]=8'h78;
  memory[799]=8'h7d;
  memory[800]=8'h82;
  memory[801]=8'h87;
  memory[802]=8'h8c;
  memory[803]=8'h91;
  memory[804]=8'h96;
  memory[805]=8'h9b;
  memory[806]=8'ha0;
  memory[807]=8'ha5;
  memory[808]=8'haa;
  memory[809]=8'haf;
  memory[810]=8'hb4;
  memory[811]=8'hb9;
  memory[812]=8'hbe;
  memory[813]=8'hc3;
  memory[814]=8'hc8;
  memory[815]=8'hcd;
  memory[816]=8'hd2;
  memory[817]=8'hd7;
  memory[818]=8'hdc;
  memory[819]=8'he1;
  memory[820]=8'he6;
  memory[821]=8'heb;
  memory[822]=8'hf0;
  memory[823]=8'hf5;
  memory[824]=8'hfa;
  memory[825]=8'hff;
  memory[826]=8'hff;
  memory[827]=8'hff;
  memory[828]=8'hff;
  memory[829]=8'hff;
  memory[830]=8'hff;
  memory[831]=8'hff;
  memory[832]=8'hff;
  memory[833]=8'hff;
  memory[834]=8'hff;
  memory[835]=8'hff;
  memory[836]=8'hff;
  memory[837]=8'hff;
  memory[838]=8'hff;
  memory[839]=8'hff;
  memory[840]=8'hff;
  memory[841]=8'hff;
  memory[842]=8'hff;
  memory[843]=8'hff;
  memory[844]=8'hff;
  memory[845]=8'hff;
  memory[846]=8'hff;
  memory[847]=8'hff;
  memory[848]=8'hff;
  memory[849]=8'hff;
  memory[850]=8'hff;
  memory[851]=8'hff;
  memory[852]=8'hff;
  memory[853]=8'hff;
  memory[854]=8'hff;
  memory[855]=8'hff;
  memory[856]=8'hff;
  memory[857]=8'hff;
  memory[858]=8'hff;
  memory[859]=8'hff;
  memory[860]=8'hff;
  memory[861]=8'hff;
  memory[862]=8'hff;
  memory[863]=8'hff;
  memory[864]=8'hff;
  memory[865]=8'hff;
  memory[866]=8'hff;
  memory[867]=8'hff;
  memory[868]=8'hff;
  memory[869]=8'hff;
  memory[870]=8'hff;
  memory[871]=8'hff;
  memory[872]=8'hff;
  memory[873]=8'hff;
  memory[874]=8'hff;
  memory[875]=8'hff;
  memory[876]=8'hff;
  memory[877]=8'hff;
  memory[878]=8'hff;
  memory[879]=8'hff;
  memory[880]=8'hff;
  memory[881]=8'hff;
  memory[882]=8'hff;
  memory[883]=8'hff;
  memory[884]=8'hff;
  memory[885]=8'hff;
  memory[886]=8'hff;
  memory[887]=8'hff;
  memory[888]=8'hff;
  memory[889]=8'hff;
  memory[890]=8'hff;
  memory[891]=8'hff;
  memory[892]=8'hff;
  memory[893]=8'hff;
  memory[894]=8'hff;
  memory[895]=8'hff;
  memory[896]=8'hff;
  memory[897]=8'hff;
  memory[898]=8'hff;
  memory[899]=8'hff;
  memory[900]=8'hff;
  memory[901]=8'hff;
  memory[902]=8'hff;
  memory[903]=8'hff;
  memory[904]=8'hff;
  memory[905]=8'hff;
  memory[906]=8'hff;
  memory[907]=8'hff;
  memory[908]=8'hff;
  memory[909]=8'hff;
  memory[910]=8'hff;
  memory[911]=8'hff;
  memory[912]=8'hff;
  memory[913]=8'hff;
  memory[914]=8'hff;
  memory[915]=8'hff;
  memory[916]=8'hff;
  memory[917]=8'hff;
  memory[918]=8'hff;
  memory[919]=8'hff;
  memory[920]=8'hff;
  memory[921]=8'hff;
  memory[922]=8'hff;
  memory[923]=8'hff;
  memory[924]=8'hff;
  memory[925]=8'hff;
  memory[926]=8'hff;
  memory[927]=8'hff;
  memory[928]=8'hff;
  memory[929]=8'hff;
  memory[930]=8'hff;
  memory[931]=8'hff;
  memory[932]=8'hff;
  memory[933]=8'hff;
  memory[934]=8'hff;
  memory[935]=8'hff;
  memory[936]=8'hff;
  memory[937]=8'hff;
  memory[938]=8'hff;
  memory[939]=8'hff;
  memory[940]=8'hff;
  memory[941]=8'hff;
  memory[942]=8'hff;
  memory[943]=8'hff;
  memory[944]=8'hff;
  memory[945]=8'hff;
  memory[946]=8'hff;
  memory[947]=8'hff;
  memory[948]=8'hff;
  memory[949]=8'hff;
  memory[950]=8'hff;
  memory[951]=8'hff;
  memory[952]=8'hff;
  memory[953]=8'hff;
  memory[954]=8'hff;
  memory[955]=8'hff;
  memory[956]=8'hff;
  memory[957]=8'hff;
  memory[958]=8'hff;
  memory[959]=8'hff;
  memory[960]=8'hff;
  memory[961]=8'hff;
  memory[962]=8'hff;
  memory[963]=8'hff;
  memory[964]=8'hff;
  memory[965]=8'hff;
  memory[966]=8'hff;
  memory[967]=8'hff;
  memory[968]=8'hff;
  memory[969]=8'hff;
  memory[970]=8'hff;
  memory[971]=8'hff;
  memory[972]=8'hff;
  memory[973]=8'hff;
  memory[974]=8'hff;
  memory[975]=8'hff;
  memory[976]=8'hff;
  memory[977]=8'hff;
  memory[978]=8'hff;
  memory[979]=8'hff;
  memory[980]=8'hff;
  memory[981]=8'hff;
  memory[982]=8'hff;
  memory[983]=8'hff;
  memory[984]=8'hff;
  memory[985]=8'hff;
  memory[986]=8'hff;
  memory[987]=8'hff;
  memory[988]=8'hff;
  memory[989]=8'hff;
  memory[990]=8'hff;
  memory[991]=8'hff;
  memory[992]=8'hff;
  memory[993]=8'hff;
  memory[994]=8'hff;
  memory[995]=8'hff;
  memory[996]=8'hff;
  memory[997]=8'hff;
  memory[998]=8'hff;
  memory[999]=8'hff;
  memory[1000]=8'hff;
  memory[1001]=8'hff;
  memory[1002]=8'hff;
  memory[1003]=8'hff;
  memory[1004]=8'hff;
  memory[1005]=8'hff;
  memory[1006]=8'hff;
  memory[1007]=8'hff;
  memory[1008]=8'hff;
  memory[1009]=8'hff;
  memory[1010]=8'hff;
  memory[1011]=8'hff;
  memory[1012]=8'hff;
  memory[1013]=8'hff;
  memory[1014]=8'hff;
  memory[1015]=8'hff;
  memory[1016]=8'hff;
  memory[1017]=8'hff;
  memory[1018]=8'hff;
  memory[1019]=8'hff;
  memory[1020]=8'hff;
  memory[1021]=8'hff;
  memory[1022]=8'hff;
  memory[1023]=8'hff;
  memory[1024]=8'h00;
  memory[1025]=8'h00;
  memory[1026]=8'h00;
  memory[1027]=8'h08;
  memory[1028]=8'h10;
  memory[1029]=8'h18;
  memory[1030]=8'h20;
  memory[1031]=8'h28;
  memory[1032]=8'h30;
  memory[1033]=8'h38;
  memory[1034]=8'h40;
  memory[1035]=8'h48;
  memory[1036]=8'h50;
  memory[1037]=8'h58;
  memory[1038]=8'h60;
  memory[1039]=8'h68;
  memory[1040]=8'h70;
  memory[1041]=8'h78;
  memory[1042]=8'h80;
  memory[1043]=8'h88;
  memory[1044]=8'h90;
  memory[1045]=8'h98;
  memory[1046]=8'ha0;
  memory[1047]=8'ha8;
  memory[1048]=8'hb0;
  memory[1049]=8'hb8;
  memory[1050]=8'hc0;
  memory[1051]=8'hc8;
  memory[1052]=8'hd0;
  memory[1053]=8'hd8;
  memory[1054]=8'he0;
  memory[1055]=8'he8;
  memory[1056]=8'hf0;
  memory[1057]=8'hf8;
  memory[1058]=8'hff;
  memory[1059]=8'hff;
  memory[1060]=8'hff;
  memory[1061]=8'hff;
  memory[1062]=8'hff;
  memory[1063]=8'hff;
  memory[1064]=8'hff;
  memory[1065]=8'hff;
  memory[1066]=8'hff;
  memory[1067]=8'hff;
  memory[1068]=8'hff;
  memory[1069]=8'hff;
  memory[1070]=8'hff;
  memory[1071]=8'hff;
  memory[1072]=8'hff;
  memory[1073]=8'hff;
  memory[1074]=8'hff;
  memory[1075]=8'hff;
  memory[1076]=8'hff;
  memory[1077]=8'hff;
  memory[1078]=8'hff;
  memory[1079]=8'hff;
  memory[1080]=8'hff;
  memory[1081]=8'hff;
  memory[1082]=8'hff;
  memory[1083]=8'hff;
  memory[1084]=8'hff;
  memory[1085]=8'hff;
  memory[1086]=8'hff;
  memory[1087]=8'hff;
  memory[1088]=8'hff;
  memory[1089]=8'hff;
  memory[1090]=8'hff;
  memory[1091]=8'hff;
  memory[1092]=8'hff;
  memory[1093]=8'hff;
  memory[1094]=8'hff;
  memory[1095]=8'hff;
  memory[1096]=8'hff;
  memory[1097]=8'hff;
  memory[1098]=8'hff;
  memory[1099]=8'hff;
  memory[1100]=8'hff;
  memory[1101]=8'hff;
  memory[1102]=8'hff;
  memory[1103]=8'hff;
  memory[1104]=8'hff;
  memory[1105]=8'hff;
  memory[1106]=8'hff;
  memory[1107]=8'hff;
  memory[1108]=8'hff;
  memory[1109]=8'hff;
  memory[1110]=8'hff;
  memory[1111]=8'hff;
  memory[1112]=8'hff;
  memory[1113]=8'hff;
  memory[1114]=8'hff;
  memory[1115]=8'hff;
  memory[1116]=8'hff;
  memory[1117]=8'hff;
  memory[1118]=8'hff;
  memory[1119]=8'hff;
  memory[1120]=8'hff;
  memory[1121]=8'hff;
  memory[1122]=8'hff;
  memory[1123]=8'hff;
  memory[1124]=8'hff;
  memory[1125]=8'hff;
  memory[1126]=8'hff;
  memory[1127]=8'hff;
  memory[1128]=8'hff;
  memory[1129]=8'hff;
  memory[1130]=8'hff;
  memory[1131]=8'hff;
  memory[1132]=8'hff;
  memory[1133]=8'hff;
  memory[1134]=8'hff;
  memory[1135]=8'hff;
  memory[1136]=8'hff;
  memory[1137]=8'hff;
  memory[1138]=8'hff;
  memory[1139]=8'hff;
  memory[1140]=8'hff;
  memory[1141]=8'hff;
  memory[1142]=8'hff;
  memory[1143]=8'hff;
  memory[1144]=8'hff;
  memory[1145]=8'hff;
  memory[1146]=8'hff;
  memory[1147]=8'hff;
  memory[1148]=8'hff;
  memory[1149]=8'hff;
  memory[1150]=8'hff;
  memory[1151]=8'hff;
  memory[1152]=8'hff;
  memory[1153]=8'hff;
  memory[1154]=8'hff;
  memory[1155]=8'hff;
  memory[1156]=8'hff;
  memory[1157]=8'hff;
  memory[1158]=8'hff;
  memory[1159]=8'hff;
  memory[1160]=8'hff;
  memory[1161]=8'hff;
  memory[1162]=8'hff;
  memory[1163]=8'hff;
  memory[1164]=8'hff;
  memory[1165]=8'hff;
  memory[1166]=8'hff;
  memory[1167]=8'hff;
  memory[1168]=8'hff;
  memory[1169]=8'hff;
  memory[1170]=8'hff;
  memory[1171]=8'hff;
  memory[1172]=8'hff;
  memory[1173]=8'hff;
  memory[1174]=8'hff;
  memory[1175]=8'hff;
  memory[1176]=8'hff;
  memory[1177]=8'hff;
  memory[1178]=8'hff;
  memory[1179]=8'hff;
  memory[1180]=8'hff;
  memory[1181]=8'hff;
  memory[1182]=8'hff;
  memory[1183]=8'hff;
  memory[1184]=8'hff;
  memory[1185]=8'hff;
  memory[1186]=8'hff;
  memory[1187]=8'hff;
  memory[1188]=8'hff;
  memory[1189]=8'hff;
  memory[1190]=8'hff;
  memory[1191]=8'hff;
  memory[1192]=8'hff;
  memory[1193]=8'hff;
  memory[1194]=8'hff;
  memory[1195]=8'hff;
  memory[1196]=8'hff;
  memory[1197]=8'hff;
  memory[1198]=8'hff;
  memory[1199]=8'hff;
  memory[1200]=8'hff;
  memory[1201]=8'hff;
  memory[1202]=8'hff;
  memory[1203]=8'hff;
  memory[1204]=8'hff;
  memory[1205]=8'hff;
  memory[1206]=8'hff;
  memory[1207]=8'hff;
  memory[1208]=8'hff;
  memory[1209]=8'hff;
  memory[1210]=8'hff;
  memory[1211]=8'hff;
  memory[1212]=8'hff;
  memory[1213]=8'hff;
  memory[1214]=8'hff;
  memory[1215]=8'hff;
  memory[1216]=8'hff;
  memory[1217]=8'hff;
  memory[1218]=8'hff;
  memory[1219]=8'hff;
  memory[1220]=8'hff;
  memory[1221]=8'hff;
  memory[1222]=8'hff;
  memory[1223]=8'hff;
  memory[1224]=8'hff;
  memory[1225]=8'hff;
  memory[1226]=8'hff;
  memory[1227]=8'hff;
  memory[1228]=8'hff;
  memory[1229]=8'hff;
  memory[1230]=8'hff;
  memory[1231]=8'hff;
  memory[1232]=8'hff;
  memory[1233]=8'hff;
  memory[1234]=8'hff;
  memory[1235]=8'hff;
  memory[1236]=8'hff;
  memory[1237]=8'hff;
  memory[1238]=8'hff;
  memory[1239]=8'hff;
  memory[1240]=8'hff;
  memory[1241]=8'hff;
  memory[1242]=8'hff;
  memory[1243]=8'hff;
  memory[1244]=8'hff;
  memory[1245]=8'hff;
  memory[1246]=8'hff;
  memory[1247]=8'hff;
  memory[1248]=8'hff;
  memory[1249]=8'hff;
  memory[1250]=8'hff;
  memory[1251]=8'hff;
  memory[1252]=8'hff;
  memory[1253]=8'hff;
  memory[1254]=8'hff;
  memory[1255]=8'hff;
  memory[1256]=8'hff;
  memory[1257]=8'hff;
  memory[1258]=8'hff;
  memory[1259]=8'hff;
  memory[1260]=8'hff;
  memory[1261]=8'hff;
  memory[1262]=8'hff;
  memory[1263]=8'hff;
  memory[1264]=8'hff;
  memory[1265]=8'hff;
  memory[1266]=8'hff;
  memory[1267]=8'hff;
  memory[1268]=8'hff;
  memory[1269]=8'hff;
  memory[1270]=8'hff;
  memory[1271]=8'hff;
  memory[1272]=8'hff;
  memory[1273]=8'hff;
  memory[1274]=8'hff;
  memory[1275]=8'hff;
  memory[1276]=8'hff;
  memory[1277]=8'hff;
  memory[1278]=8'hff;
  memory[1279]=8'hff;
  memory[1280]=8'h00;
  memory[1281]=8'h00;
  memory[1282]=8'h00;
  memory[1283]=8'h00;
  memory[1284]=8'h00;
  memory[1285]=8'h00;
  memory[1286]=8'h00;
  memory[1287]=8'h00;
  memory[1288]=8'h00;
  memory[1289]=8'h00;
  memory[1290]=8'h00;
  memory[1291]=8'h00;
  memory[1292]=8'h00;
  memory[1293]=8'h03;
  memory[1294]=8'h06;
  memory[1295]=8'h09;
  memory[1296]=8'h0c;
  memory[1297]=8'h0f;
  memory[1298]=8'h12;
  memory[1299]=8'h15;
  memory[1300]=8'h18;
  memory[1301]=8'h1b;
  memory[1302]=8'h1e;
  memory[1303]=8'h21;
  memory[1304]=8'h24;
  memory[1305]=8'h27;
  memory[1306]=8'h2a;
  memory[1307]=8'h2d;
  memory[1308]=8'h31;
  memory[1309]=8'h34;
  memory[1310]=8'h37;
  memory[1311]=8'h3a;
  memory[1312]=8'h3d;
  memory[1313]=8'h40;
  memory[1314]=8'h43;
  memory[1315]=8'h46;
  memory[1316]=8'h49;
  memory[1317]=8'h4c;
  memory[1318]=8'h4f;
  memory[1319]=8'h52;
  memory[1320]=8'h55;
  memory[1321]=8'h58;
  memory[1322]=8'h5b;
  memory[1323]=8'h5e;
  memory[1324]=8'h62;
  memory[1325]=8'h65;
  memory[1326]=8'h68;
  memory[1327]=8'h6b;
  memory[1328]=8'h6e;
  memory[1329]=8'h71;
  memory[1330]=8'h74;
  memory[1331]=8'h77;
  memory[1332]=8'h7a;
  memory[1333]=8'h7d;
  memory[1334]=8'h80;
  memory[1335]=8'h83;
  memory[1336]=8'h86;
  memory[1337]=8'h89;
  memory[1338]=8'h8c;
  memory[1339]=8'h8f;
  memory[1340]=8'h93;
  memory[1341]=8'h96;
  memory[1342]=8'h99;
  memory[1343]=8'h9c;
  memory[1344]=8'h9f;
  memory[1345]=8'ha2;
  memory[1346]=8'ha5;
  memory[1347]=8'ha8;
  memory[1348]=8'hab;
  memory[1349]=8'hae;
  memory[1350]=8'hb1;
  memory[1351]=8'hb4;
  memory[1352]=8'hb7;
  memory[1353]=8'hba;
  memory[1354]=8'hbd;
  memory[1355]=8'hc0;
  memory[1356]=8'hc4;
  memory[1357]=8'hc7;
  memory[1358]=8'hca;
  memory[1359]=8'hcd;
  memory[1360]=8'hd0;
  memory[1361]=8'hd3;
  memory[1362]=8'hd6;
  memory[1363]=8'hd9;
  memory[1364]=8'hdc;
  memory[1365]=8'hdf;
  memory[1366]=8'he2;
  memory[1367]=8'he5;
  memory[1368]=8'he8;
  memory[1369]=8'heb;
  memory[1370]=8'hee;
  memory[1371]=8'hf1;
  memory[1372]=8'hf5;
  memory[1373]=8'hf8;
  memory[1374]=8'hfb;
  memory[1375]=8'hfe;
  memory[1376]=8'hff;
  memory[1377]=8'hff;
  memory[1378]=8'hff;
  memory[1379]=8'hff;
  memory[1380]=8'hff;
  memory[1381]=8'hff;
  memory[1382]=8'hff;
  memory[1383]=8'hff;
  memory[1384]=8'hff;
  memory[1385]=8'hff;
  memory[1386]=8'hff;
  memory[1387]=8'hff;
  memory[1388]=8'hff;
  memory[1389]=8'hff;
  memory[1390]=8'hff;
  memory[1391]=8'hff;
  memory[1392]=8'hff;
  memory[1393]=8'hff;
  memory[1394]=8'hff;
  memory[1395]=8'hff;
  memory[1396]=8'hff;
  memory[1397]=8'hff;
  memory[1398]=8'hff;
  memory[1399]=8'hff;
  memory[1400]=8'hff;
  memory[1401]=8'hff;
  memory[1402]=8'hff;
  memory[1403]=8'hff;
  memory[1404]=8'hff;
  memory[1405]=8'hff;
  memory[1406]=8'hff;
  memory[1407]=8'hff;
  memory[1408]=8'hff;
  memory[1409]=8'hff;
  memory[1410]=8'hff;
  memory[1411]=8'hff;
  memory[1412]=8'hff;
  memory[1413]=8'hff;
  memory[1414]=8'hff;
  memory[1415]=8'hff;
  memory[1416]=8'hff;
  memory[1417]=8'hff;
  memory[1418]=8'hff;
  memory[1419]=8'hff;
  memory[1420]=8'hff;
  memory[1421]=8'hff;
  memory[1422]=8'hff;
  memory[1423]=8'hff;
  memory[1424]=8'hff;
  memory[1425]=8'hff;
  memory[1426]=8'hff;
  memory[1427]=8'hff;
  memory[1428]=8'hff;
  memory[1429]=8'hff;
  memory[1430]=8'hff;
  memory[1431]=8'hff;
  memory[1432]=8'hff;
  memory[1433]=8'hff;
  memory[1434]=8'hff;
  memory[1435]=8'hff;
  memory[1436]=8'hff;
  memory[1437]=8'hff;
  memory[1438]=8'hff;
  memory[1439]=8'hff;
  memory[1440]=8'hff;
  memory[1441]=8'hff;
  memory[1442]=8'hff;
  memory[1443]=8'hff;
  memory[1444]=8'hff;
  memory[1445]=8'hff;
  memory[1446]=8'hff;
  memory[1447]=8'hff;
  memory[1448]=8'hff;
  memory[1449]=8'hff;
  memory[1450]=8'hff;
  memory[1451]=8'hff;
  memory[1452]=8'hff;
  memory[1453]=8'hff;
  memory[1454]=8'hff;
  memory[1455]=8'hff;
  memory[1456]=8'hff;
  memory[1457]=8'hff;
  memory[1458]=8'hff;
  memory[1459]=8'hff;
  memory[1460]=8'hff;
  memory[1461]=8'hff;
  memory[1462]=8'hff;
  memory[1463]=8'hff;
  memory[1464]=8'hff;
  memory[1465]=8'hff;
  memory[1466]=8'hff;
  memory[1467]=8'hff;
  memory[1468]=8'hff;
  memory[1469]=8'hff;
  memory[1470]=8'hff;
  memory[1471]=8'hff;
  memory[1472]=8'hff;
  memory[1473]=8'hff;
  memory[1474]=8'hff;
  memory[1475]=8'hff;
  memory[1476]=8'hff;
  memory[1477]=8'hff;
  memory[1478]=8'hff;
  memory[1479]=8'hff;
  memory[1480]=8'hff;
  memory[1481]=8'hff;
  memory[1482]=8'hff;
  memory[1483]=8'hff;
  memory[1484]=8'hff;
  memory[1485]=8'hff;
  memory[1486]=8'hff;
  memory[1487]=8'hff;
  memory[1488]=8'hff;
  memory[1489]=8'hff;
  memory[1490]=8'hff;
  memory[1491]=8'hff;
  memory[1492]=8'hff;
  memory[1493]=8'hff;
  memory[1494]=8'hff;
  memory[1495]=8'hff;
  memory[1496]=8'hff;
  memory[1497]=8'hff;
  memory[1498]=8'hff;
  memory[1499]=8'hff;
  memory[1500]=8'hff;
  memory[1501]=8'hff;
  memory[1502]=8'hff;
  memory[1503]=8'hff;
  memory[1504]=8'hff;
  memory[1505]=8'hff;
  memory[1506]=8'hff;
  memory[1507]=8'hff;
  memory[1508]=8'hff;
  memory[1509]=8'hff;
  memory[1510]=8'hff;
  memory[1511]=8'hff;
  memory[1512]=8'hff;
  memory[1513]=8'hff;
  memory[1514]=8'hff;
  memory[1515]=8'hff;
  memory[1516]=8'hff;
  memory[1517]=8'hff;
  memory[1518]=8'hff;
  memory[1519]=8'hff;
  memory[1520]=8'hff;
  memory[1521]=8'hff;
  memory[1522]=8'hff;
  memory[1523]=8'hff;
  memory[1524]=8'hff;
  memory[1525]=8'hff;
  memory[1526]=8'hff;
  memory[1527]=8'hff;
  memory[1528]=8'hff;
  memory[1529]=8'hff;
  memory[1530]=8'hff;
  memory[1531]=8'hff;
  memory[1532]=8'hff;
  memory[1533]=8'hff;
  memory[1534]=8'hff;
  memory[1535]=8'hff;
  memory[1536]=8'h00;
  memory[1537]=8'h00;
  memory[1538]=8'h00;
  memory[1539]=8'h00;
  memory[1540]=8'h00;
  memory[1541]=8'h00;
  memory[1542]=8'h00;
  memory[1543]=8'h00;
  memory[1544]=8'h00;
  memory[1545]=8'h00;
  memory[1546]=8'h00;
  memory[1547]=8'h00;
  memory[1548]=8'h00;
  memory[1549]=8'h03;
  memory[1550]=8'h06;
  memory[1551]=8'h09;
  memory[1552]=8'h0c;
  memory[1553]=8'h0f;
  memory[1554]=8'h12;
  memory[1555]=8'h15;
  memory[1556]=8'h18;
  memory[1557]=8'h1b;
  memory[1558]=8'h1e;
  memory[1559]=8'h21;
  memory[1560]=8'h24;
  memory[1561]=8'h27;
  memory[1562]=8'h2a;
  memory[1563]=8'h2d;
  memory[1564]=8'h31;
  memory[1565]=8'h34;
  memory[1566]=8'h37;
  memory[1567]=8'h3a;
  memory[1568]=8'h3d;
  memory[1569]=8'h40;
  memory[1570]=8'h43;
  memory[1571]=8'h46;
  memory[1572]=8'h49;
  memory[1573]=8'h4c;
  memory[1574]=8'h4f;
  memory[1575]=8'h52;
  memory[1576]=8'h55;
  memory[1577]=8'h58;
  memory[1578]=8'h5b;
  memory[1579]=8'h5e;
  memory[1580]=8'h62;
  memory[1581]=8'h65;
  memory[1582]=8'h68;
  memory[1583]=8'h6b;
  memory[1584]=8'h6e;
  memory[1585]=8'h71;
  memory[1586]=8'h74;
  memory[1587]=8'h77;
  memory[1588]=8'h7a;
  memory[1589]=8'h7d;
  memory[1590]=8'h80;
  memory[1591]=8'h83;
  memory[1592]=8'h86;
  memory[1593]=8'h89;
  memory[1594]=8'h8c;
  memory[1595]=8'h8f;
  memory[1596]=8'h93;
  memory[1597]=8'h96;
  memory[1598]=8'h99;
  memory[1599]=8'h9c;
  memory[1600]=8'h9f;
  memory[1601]=8'ha2;
  memory[1602]=8'ha5;
  memory[1603]=8'ha8;
  memory[1604]=8'hab;
  memory[1605]=8'hae;
  memory[1606]=8'hb1;
  memory[1607]=8'hb4;
  memory[1608]=8'hb7;
  memory[1609]=8'hba;
  memory[1610]=8'hbd;
  memory[1611]=8'hc0;
  memory[1612]=8'hc4;
  memory[1613]=8'hc7;
  memory[1614]=8'hca;
  memory[1615]=8'hcd;
  memory[1616]=8'hd0;
  memory[1617]=8'hd3;
  memory[1618]=8'hd6;
  memory[1619]=8'hd9;
  memory[1620]=8'hdc;
  memory[1621]=8'hdf;
  memory[1622]=8'he2;
  memory[1623]=8'he5;
  memory[1624]=8'he8;
  memory[1625]=8'heb;
  memory[1626]=8'hee;
  memory[1627]=8'hf1;
  memory[1628]=8'hf5;
  memory[1629]=8'hf8;
  memory[1630]=8'hfb;
  memory[1631]=8'hfe;
  memory[1632]=8'hff;
  memory[1633]=8'hff;
  memory[1634]=8'hff;
  memory[1635]=8'hff;
  memory[1636]=8'hff;
  memory[1637]=8'hff;
  memory[1638]=8'hff;
  memory[1639]=8'hff;
  memory[1640]=8'hff;
  memory[1641]=8'hff;
  memory[1642]=8'hff;
  memory[1643]=8'hff;
  memory[1644]=8'hff;
  memory[1645]=8'hff;
  memory[1646]=8'hff;
  memory[1647]=8'hff;
  memory[1648]=8'hff;
  memory[1649]=8'hff;
  memory[1650]=8'hff;
  memory[1651]=8'hff;
  memory[1652]=8'hff;
  memory[1653]=8'hff;
  memory[1654]=8'hff;
  memory[1655]=8'hff;
  memory[1656]=8'hff;
  memory[1657]=8'hff;
  memory[1658]=8'hff;
  memory[1659]=8'hff;
  memory[1660]=8'hff;
  memory[1661]=8'hff;
  memory[1662]=8'hff;
  memory[1663]=8'hff;
  memory[1664]=8'hff;
  memory[1665]=8'hff;
  memory[1666]=8'hff;
  memory[1667]=8'hff;
  memory[1668]=8'hff;
  memory[1669]=8'hff;
  memory[1670]=8'hff;
  memory[1671]=8'hff;
  memory[1672]=8'hff;
  memory[1673]=8'hff;
  memory[1674]=8'hff;
  memory[1675]=8'hff;
  memory[1676]=8'hff;
  memory[1677]=8'hff;
  memory[1678]=8'hff;
  memory[1679]=8'hff;
  memory[1680]=8'hff;
  memory[1681]=8'hff;
  memory[1682]=8'hff;
  memory[1683]=8'hff;
  memory[1684]=8'hff;
  memory[1685]=8'hff;
  memory[1686]=8'hff;
  memory[1687]=8'hff;
  memory[1688]=8'hff;
  memory[1689]=8'hff;
  memory[1690]=8'hff;
  memory[1691]=8'hff;
  memory[1692]=8'hff;
  memory[1693]=8'hff;
  memory[1694]=8'hff;
  memory[1695]=8'hff;
  memory[1696]=8'hff;
  memory[1697]=8'hff;
  memory[1698]=8'hff;
  memory[1699]=8'hff;
  memory[1700]=8'hff;
  memory[1701]=8'hff;
  memory[1702]=8'hff;
  memory[1703]=8'hff;
  memory[1704]=8'hff;
  memory[1705]=8'hff;
  memory[1706]=8'hff;
  memory[1707]=8'hff;
  memory[1708]=8'hff;
  memory[1709]=8'hff;
  memory[1710]=8'hff;
  memory[1711]=8'hff;
  memory[1712]=8'hff;
  memory[1713]=8'hff;
  memory[1714]=8'hff;
  memory[1715]=8'hff;
  memory[1716]=8'hff;
  memory[1717]=8'hff;
  memory[1718]=8'hff;
  memory[1719]=8'hff;
  memory[1720]=8'hff;
  memory[1721]=8'hff;
  memory[1722]=8'hff;
  memory[1723]=8'hff;
  memory[1724]=8'hff;
  memory[1725]=8'hff;
  memory[1726]=8'hff;
  memory[1727]=8'hff;
  memory[1728]=8'hff;
  memory[1729]=8'hff;
  memory[1730]=8'hff;
  memory[1731]=8'hff;
  memory[1732]=8'hff;
  memory[1733]=8'hff;
  memory[1734]=8'hff;
  memory[1735]=8'hff;
  memory[1736]=8'hff;
  memory[1737]=8'hff;
  memory[1738]=8'hff;
  memory[1739]=8'hff;
  memory[1740]=8'hff;
  memory[1741]=8'hff;
  memory[1742]=8'hff;
  memory[1743]=8'hff;
  memory[1744]=8'hff;
  memory[1745]=8'hff;
  memory[1746]=8'hff;
  memory[1747]=8'hff;
  memory[1748]=8'hff;
  memory[1749]=8'hff;
  memory[1750]=8'hff;
  memory[1751]=8'hff;
  memory[1752]=8'hff;
  memory[1753]=8'hff;
  memory[1754]=8'hff;
  memory[1755]=8'hff;
  memory[1756]=8'hff;
  memory[1757]=8'hff;
  memory[1758]=8'hff;
  memory[1759]=8'hff;
  memory[1760]=8'hff;
  memory[1761]=8'hff;
  memory[1762]=8'hff;
  memory[1763]=8'hff;
  memory[1764]=8'hff;
  memory[1765]=8'hff;
  memory[1766]=8'hff;
  memory[1767]=8'hff;
  memory[1768]=8'hff;
  memory[1769]=8'hff;
  memory[1770]=8'hff;
  memory[1771]=8'hff;
  memory[1772]=8'hff;
  memory[1773]=8'hff;
  memory[1774]=8'hff;
  memory[1775]=8'hff;
  memory[1776]=8'hff;
  memory[1777]=8'hff;
  memory[1778]=8'hff;
  memory[1779]=8'hff;
  memory[1780]=8'hff;
  memory[1781]=8'hff;
  memory[1782]=8'hff;
  memory[1783]=8'hff;
  memory[1784]=8'hff;
  memory[1785]=8'hff;
  memory[1786]=8'hff;
  memory[1787]=8'hff;
  memory[1788]=8'hff;
  memory[1789]=8'hff;
  memory[1790]=8'hff;
  memory[1791]=8'hff;
  memory[1792]=8'h00;
  memory[1793]=8'h00;
  memory[1794]=8'h00;
  memory[1795]=8'h00;
  memory[1796]=8'h00;
  memory[1797]=8'h00;
  memory[1798]=8'h00;
  memory[1799]=8'h00;
  memory[1800]=8'h00;
  memory[1801]=8'h00;
  memory[1802]=8'h00;
  memory[1803]=8'h00;
  memory[1804]=8'h00;
  memory[1805]=8'h03;
  memory[1806]=8'h06;
  memory[1807]=8'h09;
  memory[1808]=8'h0c;
  memory[1809]=8'h0f;
  memory[1810]=8'h12;
  memory[1811]=8'h15;
  memory[1812]=8'h18;
  memory[1813]=8'h1b;
  memory[1814]=8'h1e;
  memory[1815]=8'h21;
  memory[1816]=8'h24;
  memory[1817]=8'h27;
  memory[1818]=8'h2a;
  memory[1819]=8'h2d;
  memory[1820]=8'h31;
  memory[1821]=8'h34;
  memory[1822]=8'h37;
  memory[1823]=8'h3a;
  memory[1824]=8'h3d;
  memory[1825]=8'h40;
  memory[1826]=8'h43;
  memory[1827]=8'h46;
  memory[1828]=8'h49;
  memory[1829]=8'h4c;
  memory[1830]=8'h4f;
  memory[1831]=8'h52;
  memory[1832]=8'h55;
  memory[1833]=8'h58;
  memory[1834]=8'h5b;
  memory[1835]=8'h5e;
  memory[1836]=8'h62;
  memory[1837]=8'h65;
  memory[1838]=8'h68;
  memory[1839]=8'h6b;
  memory[1840]=8'h6e;
  memory[1841]=8'h71;
  memory[1842]=8'h74;
  memory[1843]=8'h77;
  memory[1844]=8'h7a;
  memory[1845]=8'h7d;
  memory[1846]=8'h80;
  memory[1847]=8'h83;
  memory[1848]=8'h86;
  memory[1849]=8'h89;
  memory[1850]=8'h8c;
  memory[1851]=8'h8f;
  memory[1852]=8'h93;
  memory[1853]=8'h96;
  memory[1854]=8'h99;
  memory[1855]=8'h9c;
  memory[1856]=8'h9f;
  memory[1857]=8'ha2;
  memory[1858]=8'ha5;
  memory[1859]=8'ha8;
  memory[1860]=8'hab;
  memory[1861]=8'hae;
  memory[1862]=8'hb1;
  memory[1863]=8'hb4;
  memory[1864]=8'hb7;
  memory[1865]=8'hba;
  memory[1866]=8'hbd;
  memory[1867]=8'hc0;
  memory[1868]=8'hc4;
  memory[1869]=8'hc7;
  memory[1870]=8'hca;
  memory[1871]=8'hcd;
  memory[1872]=8'hd0;
  memory[1873]=8'hd3;
  memory[1874]=8'hd6;
  memory[1875]=8'hd9;
  memory[1876]=8'hdc;
  memory[1877]=8'hdf;
  memory[1878]=8'he2;
  memory[1879]=8'he5;
  memory[1880]=8'he8;
  memory[1881]=8'heb;
  memory[1882]=8'hee;
  memory[1883]=8'hf1;
  memory[1884]=8'hf5;
  memory[1885]=8'hf8;
  memory[1886]=8'hfb;
  memory[1887]=8'hfe;
  memory[1888]=8'hff;
  memory[1889]=8'hff;
  memory[1890]=8'hff;
  memory[1891]=8'hff;
  memory[1892]=8'hff;
  memory[1893]=8'hff;
  memory[1894]=8'hff;
  memory[1895]=8'hff;
  memory[1896]=8'hff;
  memory[1897]=8'hff;
  memory[1898]=8'hff;
  memory[1899]=8'hff;
  memory[1900]=8'hff;
  memory[1901]=8'hff;
  memory[1902]=8'hff;
  memory[1903]=8'hff;
  memory[1904]=8'hff;
  memory[1905]=8'hff;
  memory[1906]=8'hff;
  memory[1907]=8'hff;
  memory[1908]=8'hff;
  memory[1909]=8'hff;
  memory[1910]=8'hff;
  memory[1911]=8'hff;
  memory[1912]=8'hff;
  memory[1913]=8'hff;
  memory[1914]=8'hff;
  memory[1915]=8'hff;
  memory[1916]=8'hff;
  memory[1917]=8'hff;
  memory[1918]=8'hff;
  memory[1919]=8'hff;
  memory[1920]=8'hff;
  memory[1921]=8'hff;
  memory[1922]=8'hff;
  memory[1923]=8'hff;
  memory[1924]=8'hff;
  memory[1925]=8'hff;
  memory[1926]=8'hff;
  memory[1927]=8'hff;
  memory[1928]=8'hff;
  memory[1929]=8'hff;
  memory[1930]=8'hff;
  memory[1931]=8'hff;
  memory[1932]=8'hff;
  memory[1933]=8'hff;
  memory[1934]=8'hff;
  memory[1935]=8'hff;
  memory[1936]=8'hff;
  memory[1937]=8'hff;
  memory[1938]=8'hff;
  memory[1939]=8'hff;
  memory[1940]=8'hff;
  memory[1941]=8'hff;
  memory[1942]=8'hff;
  memory[1943]=8'hff;
  memory[1944]=8'hff;
  memory[1945]=8'hff;
  memory[1946]=8'hff;
  memory[1947]=8'hff;
  memory[1948]=8'hff;
  memory[1949]=8'hff;
  memory[1950]=8'hff;
  memory[1951]=8'hff;
  memory[1952]=8'hff;
  memory[1953]=8'hff;
  memory[1954]=8'hff;
  memory[1955]=8'hff;
  memory[1956]=8'hff;
  memory[1957]=8'hff;
  memory[1958]=8'hff;
  memory[1959]=8'hff;
  memory[1960]=8'hff;
  memory[1961]=8'hff;
  memory[1962]=8'hff;
  memory[1963]=8'hff;
  memory[1964]=8'hff;
  memory[1965]=8'hff;
  memory[1966]=8'hff;
  memory[1967]=8'hff;
  memory[1968]=8'hff;
  memory[1969]=8'hff;
  memory[1970]=8'hff;
  memory[1971]=8'hff;
  memory[1972]=8'hff;
  memory[1973]=8'hff;
  memory[1974]=8'hff;
  memory[1975]=8'hff;
  memory[1976]=8'hff;
  memory[1977]=8'hff;
  memory[1978]=8'hff;
  memory[1979]=8'hff;
  memory[1980]=8'hff;
  memory[1981]=8'hff;
  memory[1982]=8'hff;
  memory[1983]=8'hff;
  memory[1984]=8'hff;
  memory[1985]=8'hff;
  memory[1986]=8'hff;
  memory[1987]=8'hff;
  memory[1988]=8'hff;
  memory[1989]=8'hff;
  memory[1990]=8'hff;
  memory[1991]=8'hff;
  memory[1992]=8'hff;
  memory[1993]=8'hff;
  memory[1994]=8'hff;
  memory[1995]=8'hff;
  memory[1996]=8'hff;
  memory[1997]=8'hff;
  memory[1998]=8'hff;
  memory[1999]=8'hff;
  memory[2000]=8'hff;
  memory[2001]=8'hff;
  memory[2002]=8'hff;
  memory[2003]=8'hff;
  memory[2004]=8'hff;
  memory[2005]=8'hff;
  memory[2006]=8'hff;
  memory[2007]=8'hff;
  memory[2008]=8'hff;
  memory[2009]=8'hff;
  memory[2010]=8'hff;
  memory[2011]=8'hff;
  memory[2012]=8'hff;
  memory[2013]=8'hff;
  memory[2014]=8'hff;
  memory[2015]=8'hff;
  memory[2016]=8'hff;
  memory[2017]=8'hff;
  memory[2018]=8'hff;
  memory[2019]=8'hff;
  memory[2020]=8'hff;
  memory[2021]=8'hff;
  memory[2022]=8'hff;
  memory[2023]=8'hff;
  memory[2024]=8'hff;
  memory[2025]=8'hff;
  memory[2026]=8'hff;
  memory[2027]=8'hff;
  memory[2028]=8'hff;
  memory[2029]=8'hff;
  memory[2030]=8'hff;
  memory[2031]=8'hff;
  memory[2032]=8'hff;
  memory[2033]=8'hff;
  memory[2034]=8'hff;
  memory[2035]=8'hff;
  memory[2036]=8'hff;
  memory[2037]=8'hff;
  memory[2038]=8'hff;
  memory[2039]=8'hff;
  memory[2040]=8'hff;
  memory[2041]=8'hff;
  memory[2042]=8'hff;
  memory[2043]=8'hff;
  memory[2044]=8'hff;
  memory[2045]=8'hff;
  memory[2046]=8'hff;
  memory[2047]=8'hff;
 end
 always @(posedge clk)if(enable)begin ra<=memory[a];rb<=memory[b];end
 assign qa=ra;assign qb=rb;
endmodule
