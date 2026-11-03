module isp_top (
    input I_wb_allow,I_wb_relearn,
    input [1:0] I_mode_req,
    input [11:0] I_style_levels,
    output wire O_wb_locked,
    output wire [12:0] O_color_gain_r,O_color_gain_b,
    output [95:0] O_meter_data,
    output O_meter_valid,O_meter_sof,
    input 			axi4s_video_aclk,
    input 			I_rst_n			,
    input 			I_tlast			,
    input 			I_tuser			,
    input [39:0] 	I_tdata			,
    input 			I_tvalid		,
    input [9:0] 	I_tdest			,
    input 			O_tready		,
    output [127:0] 	O_tdata			,
    output 			O_tlast			,
    output 			O_tuser			,
    output 			O_tvalid		,
    output 			I_tready
);
 
wire quality_valid, quality_user, quality_last;
wire sty_valid, sty_user, sty_last;   // 风格化模块输出（下面 assign 要用，先声明）
(* ASYNC_REG="TRUE" *) reg [1:0] wb_allow_sync,wb_relearn_sync;
always @(posedge axi4s_video_aclk or negedge I_rst_n) begin
 if(!I_rst_n)begin wb_allow_sync<=0;wb_relearn_sync<=0;end
 else begin wb_allow_sync<={wb_allow_sync[0],I_wb_allow};
 wb_relearn_sync<={wb_relearn_sync[0],I_wb_relearn};end
end
wire         m_aixs_tvalid;  //synthesis keep 
  wire [127:0] m_aixs_tdata;  //synthesis keep 
  wire         m_aixs_tuser;  //synthesis keep 
  wire         m_aixs_tlast;  //synthesis keep 
  wire         m_aixs_tready;  //synthesis keep 
  
  wire [ 95:0] m_aixs_tdata_96;  //synthesis keep 


  wire         awb_O_tlast;  //synthesis keep 
  wire         awb_O_tuser;  //synthesis keep 
  wire [ 95:0] awb_O_tdata;  //synthesis keep 
  wire         awb_O_tvalid;  //synthesis keep 
  wire         awb_O_tready;  //synthesis keep 

  wire         awb_O_tuser_128;  //synthesis keep 
  wire         awb_O_tvalid_128;  //synthesis keep 
  wire [127:0] awb_O_tdata_128;  //synthesis keep 

  assign O_meter_data=awb_O_tdata;
  assign O_meter_valid=awb_O_tvalid;
  assign O_meter_sof=awb_O_tuser;
  assign awb_O_tready = O_tready;
  assign O_tdata  = awb_O_tdata_128;
  assign O_tlast  = sty_last    ;
  assign O_tuser  = awb_O_tuser_128    ;
  assign O_tvalid = awb_O_tvalid_128   ;
  
  //assign m_aixs_tready = O_tready;
  //assign O_tdata  = m_aixs_tdata;
  //assign O_tlast  = m_aixs_tlast    ;
  //assign O_tuser  = m_aixs_tuser    ;
  //assign O_tvalid = m_aixs_tvalid   ;
 
 
demosaic #(
    .IMG_HEIGHT          (720 ), // 图像高度
    .IMG_WIDTH           (1280), // 图像宽度
    .data_complete_delay (50  ),
    .BAYER_MODE          ("BGGR")
)
u_demosaic
(
    .I_clk   			(axi4s_video_aclk)	,   // 时钟信号
    .I_rst_n 			(I_rst_n)	,   // 复位信号，低有效
    .axi4s_video_tdata 	(I_tdata)	,  // AXI4-Stream视频数据
    .axi4s_video_tdest 	(I_tdest)	,
    .axi4s_video_tlast 	(I_tlast)	,  // 行结束信号
    .axi4s_video_tvalid	(I_tvalid)	,  // 数据有效信号
    .axi4s_video_tuser 	(I_tuser)	,  // 帧开始信号
    .axi4s_video_tready	(I_tready)	,  // 从模块准备好接受数据
    .O_tlast  			(m_aixs_tlast)	,  // 输出行结束信号
    .O_tuser  			(m_aixs_tuser)	,  // 输出帧开始信号
    .O_tdata  			(m_aixs_tdata)	,  // 输出数据
    .O_tvalid 			(m_aixs_tvalid)	,  // 输出数据有效信号
    .O_tready   		(m_aixs_tready)	   // 输出数据准备好信号
);
 
data128_96 u_data128_96 (
    .I_tdata(m_aixs_tdata),
    .O_tdata(m_aixs_tdata_96)
);

// Trial black pedestal: 8/255. Not a measured sensor calibration.
wire [95:0] black_corrected_data;
black_level96 u_black (.din(m_aixs_tdata_96), .dout(black_corrected_data));

awb #(
    .IMG_HEIGHT(720 ),
    .IMG_WIDTH (1280)
) u_awb (
    .I_wb_allow(wb_allow_sync[1]),.I_wb_relearn(wb_relearn_sync[1]),.O_wb_locked(),
    .I_clk   (axi4s_video_aclk),
    .I_rst_n (I_rst_n),
    .I_tlast (m_aixs_tlast),
    .I_tuser (m_aixs_tuser),
    .I_tdata (black_corrected_data),
    .I_tvalid(m_aixs_tvalid),
    .I_tready(m_aixs_tready),
    .O_tlast (awb_O_tlast ),
    .O_tuser (awb_O_tuser ),
    .O_tdata (awb_O_tdata ),
    .O_tvalid(awb_O_tvalid),
    .O_tready(awb_O_tready)
);

    // ---------------------------------------------------------------------
    // 自适应黑电平 / 去灰（auto_black_96.v）：插在白平衡之后、1.5 的 sRGB 曲线之前。
    // 每帧按通道统计黑底，下一帧减掉并拉伸回满量程，解决画面发灰、暗部偏粉紫。
    // 自动曝光统计（O_meter_*）仍取自白平衡输出，不受影响。
    // The new control mapping keeps dehaze enabled; image arithmetic is unchanged.
    // ---------------------------------------------------------------------
    // Preserve the accepted V3 dehaze policy in every UI group.
    wire dehaze_en=1'b1;

    wire [95:0] ab_data;
    wire        ab_valid, ab_user, ab_last;
    auto_black_96 u_auto_black (
        .clk(axi4s_video_aclk), .rst_n(I_rst_n), .I_enable(dehaze_en),
        .din(awb_O_tdata), .valid_in(awb_O_tvalid), .user_in(awb_O_tuser), .last_in(awb_O_tlast),
        .dout(ab_data), .valid_out(ab_valid), .user_out(ab_user), .last_out(ab_last),
        .O_black());

    wire [95:0] quality_data;

    image_quality_v2 u_quality (
        .clk(axi4s_video_aclk), .rst_n(I_rst_n),
        .din(ab_data), .valid_in(ab_valid),
        .user_in(ab_user), .last_in(ab_last),
        .dout(quality_data), .valid_out(quality_valid),
        .user_out(quality_user), .last_out(quality_last));

    scene_color_control u_scene_color(.clk(axi4s_video_aclk),.rst_n(I_rst_n),
        .valid(quality_valid),.sof(quality_user),.allow(wb_allow_sync[1]),.relearn(wb_relearn_sync[1]),
        .rgb(quality_data),.gain_r(O_color_gain_r),.gain_b(O_color_gain_b),.ready(O_wb_locked));

    // ---------------------------------------------------------------------
    // 风格化 v5（stylize_v5_96.v）：插在 1.5 画质处理之后、96->128 打包之前。
    // 自动曝光统计（O_meter_*）仍取自 AWB 输出，不受风格化模式影响。
    //   模式 0 原图  1 卡通化  2 素描
    // Mode is delivered coherently at the earlier RAW frame boundary.
    wire [1:0] sty_mode=I_mode_req;

    wire [95:0] sty_data;
    // V8 edge rendering reuses the style fine/coarse windows. Mode zero
    // continues through the original raw bypass; metering taps are unchanged.

    stylize_v5_96 #(
        .IMG_WIDTH (1280),
        .IMG_HEIGHT(720 ),.EXTERNAL_EDGE(0)
    ) u_stylize (
        .I_clk    (axi4s_video_aclk),
        .I_rst_n  (I_rst_n),
        .I_mode   (sty_mode),
        .I_level  (sty_mode==1?I_style_levels[5:3]:sty_mode==2?I_style_levels[8:6]:sty_mode==3?I_style_levels[11:9]:I_style_levels[2:0]),
        .I_tlast  (quality_last),
        .I_tuser  (quality_user),
        .I_tdata  (quality_data),
        .I_edge_data(96'd0),
        .I_tvalid (quality_valid),
        .I_tready (1'b1),
        .O_tlast  (sty_last),
        .O_tuser  (sty_user),
        .O_tdata  (sty_data),
        .O_tvalid (sty_valid),
        .O_tready ()
    );

    data_96bit_to_128bit u_data_96bit_to_128bit(
        .I_clk              ( axi4s_video_aclk  ),
        .I_rst_n            ( I_rst_n           ),
	
        .I_96b_frame_start  ( sty_user	    ),
        .I_96b_valid        ( sty_valid 		),
        .I_96b_data         ( sty_data		),
	
        .O_128b_frame_start ( awb_O_tuser_128  	),
        .O_128b_valid       ( awb_O_tvalid_128 	),
        .O_128b_data        ( awb_O_tdata_128  	)
    );



//data96_128 u_data96_128 (
//    .I_tdata(awb_O_tdata),
//    .O_tdata(awb_O_tdata_128)
//);
	
endmodule

// Lab 1.2: black subtraction before white-balance statistics and gain.
module black_level96(input [95:0] din, output [95:0] dout);
genvar n;
generate for(n=0;n<12;n=n+1) begin: c
 assign dout[n*8 +: 8] = din[n*8 +: 8] > 8 ? din[n*8 +: 8] - 8'd8 : 8'd0;
end endgenerate
endmodule

// Lab 1.5: five stages with common-channel display contrast.
// valid/frame/line flags travel through exactly the same five stages.
module image_quality_v2 (
 input clk, rst_n, input [95:0] din, input valid_in,user_in,last_in,
 output reg [95:0] dout, output valid_out,user_out,last_out
);
function [7:0] srgb;
input [7:0] x;
begin case(x)
8'd0: srgb=8'd0;
8'd1: srgb=8'd13;
8'd2: srgb=8'd22;
8'd3: srgb=8'd29;
8'd4: srgb=8'd34;
8'd5: srgb=8'd39;
8'd6: srgb=8'd43;
8'd7: srgb=8'd47;
8'd8: srgb=8'd50;
8'd9: srgb=8'd54;
8'd10: srgb=8'd57;
8'd11: srgb=8'd60;
8'd12: srgb=8'd62;
8'd13: srgb=8'd65;
8'd14: srgb=8'd67;
8'd15: srgb=8'd70;
8'd16: srgb=8'd72;
8'd17: srgb=8'd74;
8'd18: srgb=8'd76;
8'd19: srgb=8'd78;
8'd20: srgb=8'd80;
8'd21: srgb=8'd82;
8'd22: srgb=8'd84;
8'd23: srgb=8'd86;
8'd24: srgb=8'd88;
8'd25: srgb=8'd90;
8'd26: srgb=8'd91;
8'd27: srgb=8'd93;
8'd28: srgb=8'd95;
8'd29: srgb=8'd96;
8'd30: srgb=8'd98;
8'd31: srgb=8'd99;
8'd32: srgb=8'd101;
8'd33: srgb=8'd102;
8'd34: srgb=8'd104;
8'd35: srgb=8'd105;
8'd36: srgb=8'd107;
8'd37: srgb=8'd108;
8'd38: srgb=8'd109;
8'd39: srgb=8'd111;
8'd40: srgb=8'd112;
8'd41: srgb=8'd113;
8'd42: srgb=8'd115;
8'd43: srgb=8'd116;
8'd44: srgb=8'd117;
8'd45: srgb=8'd118;
8'd46: srgb=8'd120;
8'd47: srgb=8'd121;
8'd48: srgb=8'd122;
8'd49: srgb=8'd123;
8'd50: srgb=8'd124;
8'd51: srgb=8'd125;
8'd52: srgb=8'd127;
8'd53: srgb=8'd128;
8'd54: srgb=8'd129;
8'd55: srgb=8'd130;
8'd56: srgb=8'd131;
8'd57: srgb=8'd132;
8'd58: srgb=8'd133;
8'd59: srgb=8'd134;
8'd60: srgb=8'd135;
8'd61: srgb=8'd136;
8'd62: srgb=8'd137;
8'd63: srgb=8'd138;
8'd64: srgb=8'd139;
8'd65: srgb=8'd140;
8'd66: srgb=8'd141;
8'd67: srgb=8'd142;
8'd68: srgb=8'd143;
8'd69: srgb=8'd144;
8'd70: srgb=8'd145;
8'd71: srgb=8'd146;
8'd72: srgb=8'd147;
8'd73: srgb=8'd148;
8'd74: srgb=8'd149;
8'd75: srgb=8'd150;
8'd76: srgb=8'd151;
8'd77: srgb=8'd152;
8'd78: srgb=8'd152;
8'd79: srgb=8'd153;
8'd80: srgb=8'd154;
8'd81: srgb=8'd155;
8'd82: srgb=8'd156;
8'd83: srgb=8'd157;
8'd84: srgb=8'd158;
8'd85: srgb=8'd158;
8'd86: srgb=8'd159;
8'd87: srgb=8'd160;
8'd88: srgb=8'd161;
8'd89: srgb=8'd162;
8'd90: srgb=8'd163;
8'd91: srgb=8'd163;
8'd92: srgb=8'd164;
8'd93: srgb=8'd165;
8'd94: srgb=8'd166;
8'd95: srgb=8'd167;
8'd96: srgb=8'd167;
8'd97: srgb=8'd168;
8'd98: srgb=8'd169;
8'd99: srgb=8'd170;
8'd100: srgb=8'd171;
8'd101: srgb=8'd171;
8'd102: srgb=8'd172;
8'd103: srgb=8'd173;
8'd104: srgb=8'd174;
8'd105: srgb=8'd174;
8'd106: srgb=8'd175;
8'd107: srgb=8'd176;
8'd108: srgb=8'd177;
8'd109: srgb=8'd177;
8'd110: srgb=8'd178;
8'd111: srgb=8'd179;
8'd112: srgb=8'd179;
8'd113: srgb=8'd180;
8'd114: srgb=8'd181;
8'd115: srgb=8'd182;
8'd116: srgb=8'd182;
8'd117: srgb=8'd183;
8'd118: srgb=8'd184;
8'd119: srgb=8'd184;
8'd120: srgb=8'd185;
8'd121: srgb=8'd186;
8'd122: srgb=8'd186;
8'd123: srgb=8'd187;
8'd124: srgb=8'd188;
8'd125: srgb=8'd189;
8'd126: srgb=8'd189;
8'd127: srgb=8'd190;
8'd128: srgb=8'd191;
8'd129: srgb=8'd191;
8'd130: srgb=8'd192;
8'd131: srgb=8'd193;
8'd132: srgb=8'd193;
8'd133: srgb=8'd194;
8'd134: srgb=8'd194;
8'd135: srgb=8'd195;
8'd136: srgb=8'd196;
8'd137: srgb=8'd196;
8'd138: srgb=8'd197;
8'd139: srgb=8'd198;
8'd140: srgb=8'd198;
8'd141: srgb=8'd199;
8'd142: srgb=8'd200;
8'd143: srgb=8'd200;
8'd144: srgb=8'd201;
8'd145: srgb=8'd201;
8'd146: srgb=8'd202;
8'd147: srgb=8'd203;
8'd148: srgb=8'd203;
8'd149: srgb=8'd204;
8'd150: srgb=8'd205;
8'd151: srgb=8'd205;
8'd152: srgb=8'd206;
8'd153: srgb=8'd206;
8'd154: srgb=8'd207;
8'd155: srgb=8'd208;
8'd156: srgb=8'd208;
8'd157: srgb=8'd209;
8'd158: srgb=8'd209;
8'd159: srgb=8'd210;
8'd160: srgb=8'd210;
8'd161: srgb=8'd211;
8'd162: srgb=8'd212;
8'd163: srgb=8'd212;
8'd164: srgb=8'd213;
8'd165: srgb=8'd213;
8'd166: srgb=8'd214;
8'd167: srgb=8'd215;
8'd168: srgb=8'd215;
8'd169: srgb=8'd216;
8'd170: srgb=8'd216;
8'd171: srgb=8'd217;
8'd172: srgb=8'd217;
8'd173: srgb=8'd218;
8'd174: srgb=8'd218;
8'd175: srgb=8'd219;
8'd176: srgb=8'd220;
8'd177: srgb=8'd220;
8'd178: srgb=8'd221;
8'd179: srgb=8'd221;
8'd180: srgb=8'd222;
8'd181: srgb=8'd222;
8'd182: srgb=8'd223;
8'd183: srgb=8'd223;
8'd184: srgb=8'd224;
8'd185: srgb=8'd224;
8'd186: srgb=8'd225;
8'd187: srgb=8'd226;
8'd188: srgb=8'd226;
8'd189: srgb=8'd227;
8'd190: srgb=8'd227;
8'd191: srgb=8'd228;
8'd192: srgb=8'd228;
8'd193: srgb=8'd229;
8'd194: srgb=8'd229;
8'd195: srgb=8'd230;
8'd196: srgb=8'd230;
8'd197: srgb=8'd231;
8'd198: srgb=8'd231;
8'd199: srgb=8'd232;
8'd200: srgb=8'd232;
8'd201: srgb=8'd233;
8'd202: srgb=8'd233;
8'd203: srgb=8'd234;
8'd204: srgb=8'd234;
8'd205: srgb=8'd235;
8'd206: srgb=8'd235;
8'd207: srgb=8'd236;
8'd208: srgb=8'd236;
8'd209: srgb=8'd237;
8'd210: srgb=8'd237;
8'd211: srgb=8'd238;
8'd212: srgb=8'd238;
8'd213: srgb=8'd239;
8'd214: srgb=8'd239;
8'd215: srgb=8'd240;
8'd216: srgb=8'd240;
8'd217: srgb=8'd241;
8'd218: srgb=8'd241;
8'd219: srgb=8'd242;
8'd220: srgb=8'd242;
8'd221: srgb=8'd243;
8'd222: srgb=8'd243;
8'd223: srgb=8'd244;
8'd224: srgb=8'd244;
8'd225: srgb=8'd245;
8'd226: srgb=8'd245;
8'd227: srgb=8'd246;
8'd228: srgb=8'd246;
8'd229: srgb=8'd247;
8'd230: srgb=8'd247;
8'd231: srgb=8'd248;
8'd232: srgb=8'd248;
8'd233: srgb=8'd249;
8'd234: srgb=8'd249;
8'd235: srgb=8'd249;
8'd236: srgb=8'd250;
8'd237: srgb=8'd250;
8'd238: srgb=8'd251;
8'd239: srgb=8'd251;
8'd240: srgb=8'd252;
8'd241: srgb=8'd252;
8'd242: srgb=8'd253;
8'd243: srgb=8'd253;
8'd244: srgb=8'd254;
8'd245: srgb=8'd254;
8'd246: srgb=8'd255;
8'd247: srgb=8'd255;
8'd248: srgb=8'd255;
8'd249: srgb=8'd255;
8'd250: srgb=8'd255;
8'd251: srgb=8'd255;
8'd252: srgb=8'd255;
8'd253: srgb=8'd255;
8'd254: srgb=8'd255;
8'd255: srgb=8'd255;
default: srgb=0;
endcase end endfunction
function signed [10:0] enhance;
 input [7:0] c,a,b;
 reg signed [11:0] cc,aa,bb;
 begin
 cc={4'b0,c}; aa={4'b0,a}; bb={4'b0,b};
 enhance = cc + (((cc <<< 1) - aa - bb) >>> 4);
 end
endfunction
function [7:0] clip;
 input signed [10:0] c;
 begin
 if(c<0) clip=0; else if(c>255) clip=255; else clip=c[7:0];
 end
endfunction
// Lab 1.5: common RGB scale selected by peak encoded channel.
// This is a fixed display-contrast curve, not physical haze estimation.
// Five stages: sRGB -> peak/scale+delay -> common scale -> saturation -> clip.
function [7:0] peak_rgb;
 input [23:0] rgb;
 reg [7:0] rg;
 begin rg=(rgb[7:0]>rgb[15:8])?rgb[7:0]:rgb[15:8];
 peak_rgb=(rg>rgb[23:16])?rg:rgb[23:16]; end
endfunction
function [8:0] contrast_gain;
 input [7:0] peak;
 begin case(peak)
8'd0: contrast_gain=9'd115;
8'd1: contrast_gain=9'd116;
8'd2: contrast_gain=9'd116;
8'd3: contrast_gain=9'd117;
8'd4: contrast_gain=9'd117;
8'd5: contrast_gain=9'd118;
8'd6: contrast_gain=9'd118;
8'd7: contrast_gain=9'd119;
8'd8: contrast_gain=9'd119;
8'd9: contrast_gain=9'd120;
8'd10: contrast_gain=9'd121;
8'd11: contrast_gain=9'd121;
8'd12: contrast_gain=9'd122;
8'd13: contrast_gain=9'd122;
8'd14: contrast_gain=9'd123;
8'd15: contrast_gain=9'd123;
8'd16: contrast_gain=9'd124;
8'd17: contrast_gain=9'd124;
8'd18: contrast_gain=9'd125;
8'd19: contrast_gain=9'd126;
8'd20: contrast_gain=9'd126;
8'd21: contrast_gain=9'd127;
8'd22: contrast_gain=9'd127;
8'd23: contrast_gain=9'd128;
8'd24: contrast_gain=9'd128;
8'd25: contrast_gain=9'd129;
8'd26: contrast_gain=9'd129;
8'd27: contrast_gain=9'd130;
8'd28: contrast_gain=9'd130;
8'd29: contrast_gain=9'd131;
8'd30: contrast_gain=9'd132;
8'd31: contrast_gain=9'd132;
8'd32: contrast_gain=9'd133;
8'd33: contrast_gain=9'd133;
8'd34: contrast_gain=9'd134;
8'd35: contrast_gain=9'd134;
8'd36: contrast_gain=9'd135;
8'd37: contrast_gain=9'd135;
8'd38: contrast_gain=9'd136;
8'd39: contrast_gain=9'd137;
8'd40: contrast_gain=9'd137;
8'd41: contrast_gain=9'd138;
8'd42: contrast_gain=9'd138;
8'd43: contrast_gain=9'd139;
8'd44: contrast_gain=9'd139;
8'd45: contrast_gain=9'd140;
8'd46: contrast_gain=9'd140;
8'd47: contrast_gain=9'd141;
8'd48: contrast_gain=9'd142;
8'd49: contrast_gain=9'd142;
8'd50: contrast_gain=9'd143;
8'd51: contrast_gain=9'd143;
8'd52: contrast_gain=9'd144;
8'd53: contrast_gain=9'd144;
8'd54: contrast_gain=9'd145;
8'd55: contrast_gain=9'd145;
8'd56: contrast_gain=9'd146;
8'd57: contrast_gain=9'd147;
8'd58: contrast_gain=9'd147;
8'd59: contrast_gain=9'd148;
8'd60: contrast_gain=9'd148;
8'd61: contrast_gain=9'd149;
8'd62: contrast_gain=9'd149;
8'd63: contrast_gain=9'd150;
8'd64: contrast_gain=9'd150;
8'd65: contrast_gain=9'd151;
8'd66: contrast_gain=9'd151;
8'd67: contrast_gain=9'd152;
8'd68: contrast_gain=9'd153;
8'd69: contrast_gain=9'd153;
8'd70: contrast_gain=9'd154;
8'd71: contrast_gain=9'd154;
8'd72: contrast_gain=9'd155;
8'd73: contrast_gain=9'd155;
8'd74: contrast_gain=9'd156;
8'd75: contrast_gain=9'd156;
8'd76: contrast_gain=9'd157;
8'd77: contrast_gain=9'd158;
8'd78: contrast_gain=9'd158;
8'd79: contrast_gain=9'd159;
8'd80: contrast_gain=9'd159;
8'd81: contrast_gain=9'd160;
8'd82: contrast_gain=9'd160;
8'd83: contrast_gain=9'd161;
8'd84: contrast_gain=9'd161;
8'd85: contrast_gain=9'd162;
8'd86: contrast_gain=9'd163;
8'd87: contrast_gain=9'd163;
8'd88: contrast_gain=9'd164;
8'd89: contrast_gain=9'd164;
8'd90: contrast_gain=9'd165;
8'd91: contrast_gain=9'd165;
8'd92: contrast_gain=9'd166;
8'd93: contrast_gain=9'd166;
8'd94: contrast_gain=9'd167;
8'd95: contrast_gain=9'd168;
8'd96: contrast_gain=9'd168;
8'd97: contrast_gain=9'd169;
8'd98: contrast_gain=9'd169;
8'd99: contrast_gain=9'd170;
8'd100: contrast_gain=9'd170;
8'd101: contrast_gain=9'd171;
8'd102: contrast_gain=9'd171;
8'd103: contrast_gain=9'd172;
8'd104: contrast_gain=9'd173;
8'd105: contrast_gain=9'd173;
8'd106: contrast_gain=9'd174;
8'd107: contrast_gain=9'd174;
8'd108: contrast_gain=9'd175;
8'd109: contrast_gain=9'd175;
8'd110: contrast_gain=9'd176;
8'd111: contrast_gain=9'd176;
8'd112: contrast_gain=9'd177;
8'd113: contrast_gain=9'd177;
8'd114: contrast_gain=9'd178;
8'd115: contrast_gain=9'd179;
8'd116: contrast_gain=9'd179;
8'd117: contrast_gain=9'd180;
8'd118: contrast_gain=9'd180;
8'd119: contrast_gain=9'd181;
8'd120: contrast_gain=9'd181;
8'd121: contrast_gain=9'd182;
8'd122: contrast_gain=9'd182;
8'd123: contrast_gain=9'd183;
8'd124: contrast_gain=9'd184;
8'd125: contrast_gain=9'd184;
8'd126: contrast_gain=9'd185;
8'd127: contrast_gain=9'd185;
8'd128: contrast_gain=9'd186;
8'd129: contrast_gain=9'd186;
8'd130: contrast_gain=9'd187;
8'd131: contrast_gain=9'd187;
8'd132: contrast_gain=9'd188;
8'd133: contrast_gain=9'd189;
8'd134: contrast_gain=9'd189;
8'd135: contrast_gain=9'd190;
8'd136: contrast_gain=9'd190;
8'd137: contrast_gain=9'd191;
8'd138: contrast_gain=9'd191;
8'd139: contrast_gain=9'd192;
8'd140: contrast_gain=9'd192;
8'd141: contrast_gain=9'd193;
8'd142: contrast_gain=9'd194;
8'd143: contrast_gain=9'd194;
8'd144: contrast_gain=9'd195;
8'd145: contrast_gain=9'd195;
8'd146: contrast_gain=9'd196;
8'd147: contrast_gain=9'd196;
8'd148: contrast_gain=9'd197;
8'd149: contrast_gain=9'd197;
8'd150: contrast_gain=9'd198;
8'd151: contrast_gain=9'd198;
8'd152: contrast_gain=9'd199;
8'd153: contrast_gain=9'd200;
8'd154: contrast_gain=9'd200;
8'd155: contrast_gain=9'd201;
8'd156: contrast_gain=9'd201;
8'd157: contrast_gain=9'd202;
8'd158: contrast_gain=9'd202;
8'd159: contrast_gain=9'd203;
8'd160: contrast_gain=9'd203;
8'd161: contrast_gain=9'd204;
8'd162: contrast_gain=9'd205;
8'd163: contrast_gain=9'd205;
8'd164: contrast_gain=9'd206;
8'd165: contrast_gain=9'd206;
8'd166: contrast_gain=9'd207;
8'd167: contrast_gain=9'd207;
8'd168: contrast_gain=9'd208;
8'd169: contrast_gain=9'd208;
8'd170: contrast_gain=9'd209;
8'd171: contrast_gain=9'd210;
8'd172: contrast_gain=9'd210;
8'd173: contrast_gain=9'd211;
8'd174: contrast_gain=9'd211;
8'd175: contrast_gain=9'd212;
8'd176: contrast_gain=9'd212;
8'd177: contrast_gain=9'd213;
8'd178: contrast_gain=9'd213;
8'd179: contrast_gain=9'd214;
8'd180: contrast_gain=9'd215;
8'd181: contrast_gain=9'd215;
8'd182: contrast_gain=9'd216;
8'd183: contrast_gain=9'd216;
8'd184: contrast_gain=9'd217;
8'd185: contrast_gain=9'd217;
8'd186: contrast_gain=9'd218;
8'd187: contrast_gain=9'd218;
8'd188: contrast_gain=9'd219;
8'd189: contrast_gain=9'd220;
8'd190: contrast_gain=9'd220;
8'd191: contrast_gain=9'd221;
8'd192: contrast_gain=9'd221;
8'd193: contrast_gain=9'd222;
8'd194: contrast_gain=9'd222;
8'd195: contrast_gain=9'd223;
8'd196: contrast_gain=9'd223;
8'd197: contrast_gain=9'd224;
8'd198: contrast_gain=9'd224;
8'd199: contrast_gain=9'd225;
8'd200: contrast_gain=9'd226;
8'd201: contrast_gain=9'd226;
8'd202: contrast_gain=9'd227;
8'd203: contrast_gain=9'd227;
8'd204: contrast_gain=9'd228;
8'd205: contrast_gain=9'd228;
8'd206: contrast_gain=9'd229;
8'd207: contrast_gain=9'd229;
8'd208: contrast_gain=9'd230;
8'd209: contrast_gain=9'd231;
8'd210: contrast_gain=9'd231;
8'd211: contrast_gain=9'd232;
8'd212: contrast_gain=9'd232;
8'd213: contrast_gain=9'd233;
8'd214: contrast_gain=9'd233;
8'd215: contrast_gain=9'd234;
8'd216: contrast_gain=9'd234;
8'd217: contrast_gain=9'd235;
8'd218: contrast_gain=9'd236;
8'd219: contrast_gain=9'd236;
8'd220: contrast_gain=9'd237;
8'd221: contrast_gain=9'd237;
8'd222: contrast_gain=9'd238;
8'd223: contrast_gain=9'd238;
8'd224: contrast_gain=9'd239;
8'd225: contrast_gain=9'd239;
8'd226: contrast_gain=9'd240;
8'd227: contrast_gain=9'd241;
8'd228: contrast_gain=9'd241;
8'd229: contrast_gain=9'd242;
8'd230: contrast_gain=9'd242;
8'd231: contrast_gain=9'd243;
8'd232: contrast_gain=9'd243;
8'd233: contrast_gain=9'd244;
8'd234: contrast_gain=9'd244;
8'd235: contrast_gain=9'd245;
8'd236: contrast_gain=9'd245;
8'd237: contrast_gain=9'd246;
8'd238: contrast_gain=9'd247;
8'd239: contrast_gain=9'd247;
8'd240: contrast_gain=9'd248;
8'd241: contrast_gain=9'd248;
8'd242: contrast_gain=9'd249;
8'd243: contrast_gain=9'd249;
8'd244: contrast_gain=9'd250;
8'd245: contrast_gain=9'd250;
8'd246: contrast_gain=9'd251;
8'd247: contrast_gain=9'd252;
8'd248: contrast_gain=9'd252;
8'd249: contrast_gain=9'd253;
8'd250: contrast_gain=9'd253;
8'd251: contrast_gain=9'd254;
8'd252: contrast_gain=9'd254;
8'd253: contrast_gain=9'd255;
8'd254: contrast_gain=9'd255;
8'd255: contrast_gain=9'd256;
default: contrast_gain=9'd256;
 endcase end
endfunction
function [7:0] scale_channel;
 input [7:0] c;
 input [8:0] gain;
 reg [16:0] product;
 begin product=c*gain+17'd128;scale_channel=product[15:8];end
endfunction
wire [95:0] encoded_rom;
wire [95:0] encoded=rst_n?encoded_rom:96'd0;
reg [95:0] encoded_delay,contrasted;
wire [8:0] gain [0:3];
wire [16:0] gain_rom [0:3];
wire [7:0] peak_scaled [0:3];
wire [1:0] peak_channel [0:3];
wire [7:0] low_a[0:3],low_b[0:3],scaled_a[0:3],scaled_b[0:3];
genvar q;
generate
for(q=0;q<6;q=q+1)begin: srgb_pairs
    image_srgb_pair_rom u_rom(.clk(clk),.a(din[q*16+:8]),.b(din[q*16+8+:8]),
        .qa(encoded_rom[q*16+:8]),.qb(encoded_rom[q*16+8+:8]));
end
for(q=0;q<2;q=q+1)begin: gain_pairs
    image_gain_pair_rom u_rom(.clk(clk),.a(peak_rgb(encoded[q*48+:24])),.b(peak_rgb(encoded[q*48+24+:24])),
        .qa(gain_rom[q*2]),.qb(gain_rom[q*2+1]));
end
for(q=0;q<4;q=q+1)begin: gain_reset
    assign gain[q]=rst_n?gain_rom[q][16:8]:9'd256;
    assign peak_scaled[q]=rst_n?gain_rom[q][7:0]:8'd0;
    // One RGB channel equals peak_rgb. Its exact scaled result shares the
    // existing gain ROM word, leaving only two dynamic multipliers per pixel.
    assign peak_channel[q]=encoded_delay[q*24+16+:8]>=encoded_delay[q*24+8+:8] &&
        encoded_delay[q*24+16+:8]>=encoded_delay[q*24+:8]?2'd0:
        encoded_delay[q*24+8+:8]>=encoded_delay[q*24+:8]?2'd1:2'd2;
    assign low_a[q]=peak_channel[q]==0?encoded_delay[q*24+8+:8]:encoded_delay[q*24+16+:8];
    assign low_b[q]=peak_channel[q]==2?encoded_delay[q*24+8+:8]:encoded_delay[q*24+:8];
    assign scaled_a[q]=scale_channel(low_a[q],gain[q]);
    assign scaled_b[q]=scale_channel(low_b[q],gain[q]);
end
endgenerate
reg signed [10:0] saturated [0:11];
reg [4:0] v,u,l;
integer i;
always @(posedge clk or negedge rst_n) begin
 if(!rst_n) begin
  encoded_delay<=0;contrasted<=0;dout<=0;v<=0;u<=0;l<=0;
  for(i=0;i<12;i=i+1) saturated[i]<=0;
 end else begin
  v<={v[3:0],valid_in};u<={u[3:0],user_in};l<={l[3:0],last_in};
  encoded_delay<=encoded;
  for(i=0;i<4;i=i+1) begin
   contrasted[i*24 +:8]<=peak_channel[i]==2?peak_scaled[i]:scaled_b[i];
   contrasted[i*24+8 +:8]<=peak_channel[i]==0?scaled_a[i]:peak_channel[i]==1?peak_scaled[i]:scaled_b[i];
   contrasted[i*24+16 +:8]<=peak_channel[i]==0?peak_scaled[i]:scaled_a[i];
   saturated[i*3]<=enhance(contrasted[i*24 +:8],contrasted[i*24+8 +:8],contrasted[i*24+16 +:8]);
   saturated[i*3+1]<=enhance(contrasted[i*24+8 +:8],contrasted[i*24 +:8],contrasted[i*24+16 +:8]);
   saturated[i*3+2]<=enhance(contrasted[i*24+16 +:8],contrasted[i*24 +:8],contrasted[i*24+8 +:8]);
  end
  for(i=0;i<12;i=i+1) dout[i*8 +:8]<=v[3]?clip(saturated[i]):8'd0;
 end
end
assign valid_out=v[4];assign user_out=u[4];assign last_out=l[4];
endmodule
