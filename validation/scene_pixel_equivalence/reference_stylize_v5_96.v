// V11 categorical six-band cartoon, four pixels/clock, fixed 16 clocks.
// Modes 0/2/3 use the exact V10 bypass/guide/render path. Cartoon no longer
// uses a third Gaussian or continuous full-scene shelves: ordered Y2 labels
// are median-voted spatially, then mapped to six fixed cel-fill luminances.
// Original RGB colour differences are retained by one common gamut guard.
module reference_stylize_v5_96 #(
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

// 同步复位：x_cur 进入行缓存读地址，带异步复位会让 TD 不能映射到 ERAM
always @(posedge I_clk) begin
    if(!I_rst_n) begin
        x_cnt  <= 10'd0;
        y_cnt  <= 11'd0;
        ctrl_f <= 2'd0;
    end else if(I_tvalid) begin
        ctrl_f <= ctrl_cur;
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
localparam TW = 11 + 2;
wire [TW-1:0] tag_in = {y_cur, ctrl_cur};

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
reference_sty_bypass_memory u_bypass_memory(.clk(I_clk),.rst_n(I_rst_n),.din(bypass_in),.dout(bypass_delayed));


wire [143:0]  a2_top, a2_mid, a2_bot;

reference_sty_win3_96 #(.W_GRP(W_GRP), .LEFT_X(1), .TW(TW)) u_win_a (
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

reference_sty_win3_96 #(.W_GRP(W_GRP), .LEFT_X(2), .TW(TW)) u_win_b (
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
reference_sty_win3_96 #(.W_GRP(W_GRP),.LEFT_X(3),.TW(TW),.PW(40)) u_win_c(
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
 reference_style_guide_v8 #(.EXTERNAL_GRADIENT(1)) u_guide(
  .I_gx(coarse_gradient_r[21:11]),.I_gy(coarse_gradient_r[10:0]),
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
function [23:0] cartoon_colour;
 input [23:0] pixel;input [7:0] target,mag;input is_edge;
 reg [7:0] y,lo,hi,c,drop;reg signed [8:0] delta,lower,upper,value;integer ch;
 begin
  y=gray(pixel);lo=pixel[23:16]<pixel[15:8]?pixel[23:16]:pixel[15:8];lo=lo<pixel[7:0]?lo:pixel[7:0];
  hi=pixel[23:16]>pixel[15:8]?pixel[23:16]:pixel[15:8];hi=hi>pixel[7:0]?hi:pixel[7:0];
  lower=-$signed({1'b0,lo});upper=9'sd255-$signed({1'b0,hi});
  delta=$signed({1'b0,target})-$signed({1'b0,y});if(delta<lower)delta=lower;else if(delta>upper)delta=upper;
  for(ch=0;ch<3;ch=ch+1)begin
   value=$signed({1'b0,pixel[23-8*ch-:8]})+delta;c=value[7:0];
   drop=!is_edge?0:mag<64?(c>>2):(c>>1);cartoon_colour[23-8*ch-:8]=c-drop;
  end
 end
endfunction
reg[95:0]c1_rgb;reg[31:0]c1_y2,c1_mag;reg[3:0]c1_edge;
reg[31:0] c1_palette;reg[23:0] c1_distance;reg[3:0] c1_flat,c1_support;reg[11:0] c1_noise;
reg c1_v,c1_mask;reg[TW-1:0]c1_tag;
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
    c2_target[31-8*k-:8]<=guarded_tone(c1_palette[31-8*k-:8],c1_y2[31-8*k-:8],c1_distance[23-6*k-:6],c1_flat[3-k],c1_support[3-k],c1_noise[11-3*k-:3]);
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
   for(k=0;k<4;k=k+1)O_tdata[95-24*k-:24]<=cartoon_colour(c2_px[95-24*k-:24],c2_target[31-8*k-:8],c2_mag[31-8*k-:8],c2_edge[3-k]);
  end
  else O_tdata<=c2_px;
 end
end
endmodule
module reference_sty_win3_96 #(
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
module reference_sty_bypass_memory(input wire clk,rst_n,input wire [95:0] din,output wire [95:0] dout);
reg [95:0] shift[0:12];
integer n;
always @(posedge clk)begin
    shift[0]<=din;for(n=1;n<13;n=n+1)shift[n]<=shift[n-1];
end
assign dout=shift[12];
endmodule

module reference_median4_eram(input wire clk,input wire [107:0] bands,output wire [11:0] median);
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
        reference_median_majority_pair_rom u_rom(.clk(clk),.a(address[2*g][t]),.b(address[2*g+1][t]),
            .qa(ge5[2*g][t]),.qb(ge5[2*g+1][t]));
    end
end
endgenerate
endmodule
(* keep_hierarchy="true" *)
module reference_median_majority_pair_rom(input wire clk,input wire [8:0] a,b,output reg qa,qb);
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
