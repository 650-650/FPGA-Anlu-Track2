// Two ROM reads, aligned with the mixer's existing two coordinate registers.
module fusion_hud(
    input wire I_clk,I_rst_n,
    input wire [11:0] I_x,I_y,
    input wire [7:0] I_control,
    // Internal 0..4 values, packed {edge, sketch, cartoon, clear}; display 1..5.
    input wire [11:0] I_style_levels,
    input wire [15:0] I_x_bcd,I_y_bcd,
    input wire [23:0] I_pixels_bcd,
    input wire [19:0] I_seconds_bcd,I_exposure_bcd,
    input wire [7:0] I_camera_fps_bcd,I_output_fps_bcd,
    input wire [11:0] I_gain_bcd,
    input wire [19:0] I_latency_bcd,
    input wire [15:0] I_latency_frame_id,
    input wire [7:0] I_latency_status,
    input wire I_latency_valid,I_latency_repeat,I_latency_skip,
    input wire I_target,I_alarm,I_audio,I_cam_cfg,I_ddr_ready,I_source_ok,I_wb_locked,I_armed,
    input wire [3:0] I_debug,
    input wire [1:0] I_aid_h_zone,I_aid_v_zone,
    input wire [5:0] I_color_control,
    output wire O_hit,
    output wire [23:0] O_color
);
    // BEGIN GENERATED CHINESE GLYPH IDS
    // Generated compact glyph IDs; do not use ASCII + 48.
    localparam [7:0] ZH_SPACE=8'd0;
    localparam [7:0] ZH_DIGIT_BASE=8'd1;
    localparam [7:0] ZH_HEX_A_BASE=8'd11;
    localparam [7:0] ZH_U4E00=8'd32; // 一
    localparam [7:0] ZH_U4E0A=8'd33; // 上
    localparam [7:0] ZH_U4E0B=8'd34; // 下
    localparam [7:0] ZH_U4E0D=8'd35; // 不
    localparam [7:0] ZH_U4E24=8'd36; // 两
    localparam [7:0] ZH_U4E2A=8'd37; // 个
    localparam [7:0] ZH_U4E2D=8'd38; // 中
    localparam [7:0] ZH_U4EE3=8'd39; // 代
    localparam [7:0] ZH_U4F4D=8'd40; // 位
    localparam [7:0] ZH_U4F7F=8'd41; // 使
    localparam [7:0] ZH_U4FA7=8'd42; // 侧
    localparam [7:0] ZH_U5019=8'd43; // 候
    localparam [7:0] ZH_U504F=8'd44; // 偏
    localparam [7:0] ZH_U505C=8'd45; // 停
    localparam [7:0] ZH_U50CF=8'd46; // 像
    localparam [7:0] ZH_U5149=8'd47; // 光
    localparam [7:0] ZH_U5165=8'd48; // 入
    localparam [7:0] ZH_U5173=8'd49; // 关
    localparam [7:0] ZH_U518D=8'd50; // 再
    localparam [7:0] ZH_U51B7=8'd51; // 冷
    localparam [7:0] ZH_U5207=8'd52; // 切
    localparam [7:0] ZH_U524D=8'd53; // 前
    localparam [7:0] ZH_U529F=8'd54; // 功
    localparam [7:0] ZH_U52A8=8'd55; // 动
    localparam [7:0] ZH_U5341=8'd56; // 十
    localparam [7:0] ZH_U534A=8'd57; // 半
    localparam [7:0] ZH_U5361=8'd58; // 卡
    localparam [7:0] ZH_U539F=8'd59; // 原
    localparam [7:0] ZH_U53BB=8'd60; // 去
    localparam [7:0] ZH_U53C2=8'd61; // 参
    localparam [7:0] ZH_U53D1=8'd62; // 发
    localparam [7:0] ZH_U53EA=8'd63; // 只
    localparam [7:0] ZH_U53F3=8'd64; // 右
    localparam [7:0] ZH_U53F7=8'd65; // 号
    localparam [7:0] ZH_U5408=8'd66; // 合
    localparam [7:0] ZH_U540C=8'd67; // 同
    localparam [7:0] ZH_U542B=8'd68; // 含
    localparam [7:0] ZH_U548C=8'd69; // 和
    localparam [7:0] ZH_U54C1=8'd70; // 品
    localparam [7:0] ZH_U54CD=8'd71; // 响
    localparam [7:0] ZH_U56E0=8'd72; // 因
    localparam [7:0] ZH_U56FE=8'd73; // 图
    localparam [7:0] ZH_U57FA=8'd74; // 基
    localparam [7:0] ZH_U589E=8'd75; // 增
    localparam [7:0] ZH_U58F0=8'd76; // 声
    localparam [7:0] ZH_U5904=8'd77; // 处
    localparam [7:0] ZH_U590D=8'd78; // 复
    localparam [7:0] ZH_U592E=8'd79; // 央
    localparam [7:0] ZH_U5B57=8'd80; // 字
    localparam [7:0] ZH_U5B58=8'd81; // 存
    localparam [7:0] ZH_U5B66=8'd82; // 学
    localparam [7:0] ZH_U5C31=8'd83; // 就
    localparam [7:0] ZH_U5C4F=8'd84; // 屏
    localparam [7:0] ZH_U5DE6=8'd85; // 左
    localparam [7:0] ZH_U5DF2=8'd86; // 已
    localparam [7:0] ZH_U5E27=8'd87; // 帧
    localparam [7:0] ZH_U5E38=8'd88; // 常
    localparam [7:0] ZH_U5E55=8'd89; // 幕
    localparam [7:0] ZH_U5E8F=8'd90; // 序
    localparam [7:0] ZH_U5E94=8'd91; // 应
    localparam [7:0] ZH_U5E95=8'd92; // 底
    localparam [7:0] ZH_U5EF6=8'd93; // 延
    localparam [7:0] ZH_U5F00=8'd94; // 开
    localparam [7:0] ZH_U5F53=8'd95; // 当
    localparam [7:0] ZH_U5FAE=8'd96; // 微
    localparam [7:0] ZH_U5FC3=8'd97; // 心
    localparam [7:0] ZH_U5FD7=8'd98; // 志
    localparam [7:0] ZH_U6001=8'd99; // 态
    localparam [7:0] ZH_U6025=8'd100; // 急
    localparam [7:0] ZH_U6027=8'd101; // 性
    localparam [7:0] ZH_U62A5=8'd102; // 报
    localparam [7:0] ZH_U6309=8'd103; // 按
    localparam [7:0] ZH_U6362=8'd104; // 换
    localparam [7:0] ZH_U63A5=8'd105; // 接
    localparam [7:0] ZH_U63CF=8'd106; // 描
    localparam [7:0] ZH_U6536=8'd107; // 收
    localparam [7:0] ZH_U6548=8'd108; // 效
    localparam [7:0] ZH_U6551=8'd109; // 救
    localparam [7:0] ZH_U6570=8'd110; // 数
    localparam [7:0] ZH_U6587=8'd111; // 文
    localparam [7:0] ZH_U65B9=8'd112; // 方
    localparam [7:0] ZH_U65E0=8'd113; // 无
    localparam [7:0] ZH_U662F=8'd114; // 是
    localparam [7:0] ZH_U663E=8'd115; // 显
    localparam [7:0] ZH_U6670=8'd116; // 晰
    localparam [7:0] ZH_U6696=8'd117; // 暖
    localparam [7:0] ZH_U66DD=8'd118; // 曝
    localparam [7:0] ZH_U6709=8'd119; // 有
    localparam [7:0] ZH_U672A=8'd120; // 未
    localparam [7:0] ZH_U672C=8'd121; // 本
    localparam [7:0] ZH_U673A=8'd122; // 机
    localparam [7:0] ZH_U6807=8'd123; // 标
    localparam [7:0] ZH_U6863=8'd124; // 档
    localparam [7:0] ZH_U68C0=8'd125; // 检
    localparam [7:0] ZH_U6A2A=8'd126; // 横
    localparam [7:0] ZH_U6B64=8'd127; // 此
    localparam [7:0] ZH_U6BEB=8'd128; // 毫
    localparam [7:0] ZH_U6D4B=8'd129; // 测
    localparam [7:0] ZH_U6E05=8'd130; // 清
    localparam [7:0] ZH_U6E90=8'd131; // 源
    localparam [7:0] ZH_U706B=8'd132; // 火
    localparam [7:0] ZH_U7070=8'd133; // 灰
    localparam [7:0] ZH_U7130=8'd134; // 焰
    localparam [7:0] ZH_U72B6=8'd135; // 状
    localparam [7:0] ZH_U7387=8'd136; // 率
    localparam [7:0] ZH_U73B0=8'd137; // 现
    localparam [7:0] ZH_U7406=8'd138; // 理
    localparam [7:0] ZH_U7528=8'd139; // 用
    localparam [7:0] ZH_U7559=8'd140; // 留
    localparam [7:0] ZH_U767D=8'd141; // 白
    localparam [7:0] ZH_U7684=8'd142; // 的
    localparam [7:0] ZH_U76CA=8'd143; // 益
    localparam [7:0] ZH_U76F8=8'd144; // 相
    localparam [7:0] ZH_U7840=8'd145; // 础
    localparam [7:0] ZH_U786E=8'd146; // 确
    localparam [7:0] ZH_U793A=8'd147; // 示
    localparam [7:0] ZH_U79D2=8'd148; // 秒
    localparam [7:0] ZH_U7BA1=8'd149; // 管
    localparam [7:0] ZH_U7D20=8'd150; // 素
    localparam [7:0] ZH_U7EA2=8'd151; // 红
    localparam [7:0] ZH_U7EB5=8'd152; // 纵
    localparam [7:0] ZH_U7EC4=8'd153; // 组
    localparam [7:0] ZH_U7EEA=8'd154; // 绪
    localparam [7:0] ZH_U7EFF=8'd155; // 绿
    localparam [7:0] ZH_U7F13=8'd156; // 缓
    localparam [7:0] ZH_U7F18=8'd157; // 缘
    localparam [7:0] ZH_U7F6E=8'd158; // 置
    localparam [7:0] ZH_U8054=8'd159; // 联
    localparam [7:0] ZH_U80FD=8'd160; // 能
    localparam [7:0] ZH_U81EA=8'd161; // 自
    localparam [7:0] ZH_U81F3=8'd162; // 至
    localparam [7:0] ZH_U8272=8'd163; // 色
    localparam [7:0] ZH_U884C=8'd164; // 行
    localparam [7:0] ZH_U8868=8'd165; // 表
    localparam [7:0] ZH_U89C6=8'd166; // 视
    localparam [7:0] ZH_U8B66=8'd167; // 警
    localparam [7:0] ZH_U8BA4=8'd168; // 认
    localparam [7:0] ZH_U8BF7=8'd169; // 请
    localparam [7:0] ZH_U8C03=8'd170; // 调
    localparam [7:0] ZH_U8DDF=8'd171; // 跟
    localparam [7:0] ZH_U8DEF=8'd172; // 路
    localparam [7:0] ZH_U8DF3=8'd173; // 跳
    localparam [7:0] ZH_U8E2A=8'd174; // 踪
    localparam [7:0] ZH_U8FB9=8'd175; // 边
    localparam [7:0] ZH_U8FD0=8'd176; // 运
    localparam [7:0] ZH_U8FDF=8'd177; // 迟
    localparam [7:0] ZH_U9009=8'd178; // 选
    localparam [7:0] ZH_U901A=8'd179; // 通
    localparam [7:0] ZH_U90E8=8'd180; // 部
    localparam [7:0] ZH_U914D=8'd181; // 配
    localparam [7:0] ZH_U91C7=8'd182; // 采
    localparam [7:0] ZH_U91CD=8'd183; // 重
    localparam [7:0] ZH_U94FE=8'd184; // 链
    localparam [7:0] ZH_U952E=8'd185; // 键
    localparam [7:0] ZH_U957F=8'd186; // 长
    localparam [7:0] ZH_U96C6=8'd187; // 集
    localparam [7:0] ZH_U9759=8'd188; // 静
    localparam [7:0] ZH_U9762=8'd189; // 面
    localparam [7:0] ZH_U97F3=8'd190; // 音
    localparam [7:0] ZH_U9875=8'd191; // 页
    localparam [7:0] ZH_U9884=8'd192; // 预
    localparam [7:0] ZH_U9891=8'd193; // 频
    localparam [7:0] ZH_U989C=8'd194; // 颜
    // END GENERATED CHINESE GLYPH IDS
    reg [4:0] panel;
    always @* begin
        case(I_control[7:5])
            0:panel=0;
            1:panel=4+I_control[4:3];2:panel=8+I_control[4:3];
            3:panel=12+I_control[4:3];4:panel=16+I_control[4:3];default:panel=28;
        endcase
    end
    // 32 columns, native 16x16 CJK pixels doubled to 32x32 display cells.
    // Menu + font remain two synchronous ROM reads, matching the mixer.
    wire visible=I_x>=16 && I_x<1040 && I_y>=552 && I_y<696;
    wire [11:0] lx=I_x-12'd16;
    wire [1:0] row=I_y>=660?3:I_y>=624?2:I_y>=588?1:0;
    wire [11:0] row_base=row==3?660:row==2?624:row==1?588:552;
    wire [11:0] ly=I_y-row_base;
    wire [8:0] code;
    fusion_menu_rom u_menu(.I_clk(I_clk),.I_address({panel,row,lx[9:5]}),.O_char(code));
    reg [3:0] col1,col2,font_row1;
    reg visible1,visible2,latency_panel1,base_panel1,style_panel1;
    reg [2:0] style_level1;
    always @(posedge I_clk or negedge I_rst_n) begin
        if(!I_rst_n)begin
            col1<=0;col2<=0;font_row1<=0;visible1<=0;visible2<=0;
            latency_panel1<=0;base_panel1<=0;style_panel1<=0;style_level1<=3'd2;
        end else begin
            col1<=lx[4:1];col2<=col1;font_row1<=ly[4:1];
            visible1<=visible && ly<32;visible2<=visible1;
            // Align dynamic-slot interpretation with the menu result.
            latency_panel1<=panel==13 || panel==14;base_panel1<=panel==0;
            style_panel1<=panel>=4 && panel<=7;
            // Capture the selected remembered level beside the menu read.
            // These inputs are committed with I_control at the HDMI frame boundary.
            case(I_control[4:3])
                2'd0:style_level1<=I_style_levels[2:0];
                2'd1:style_level1<=I_style_levels[5:3];
                2'd2:style_level1<=I_style_levels[8:6];
                2'd3:style_level1<=I_style_levels[11:9];
            endcase
        end
    end
    reg [3:0] digit;
    wire [5:0] slot=code[5:0];
    always @* begin
        digit=0;
        if(slot<4)digit=I_x_bcd[(3-slot)*4+:4];
        else if(slot<8)digit=I_y_bcd[(7-slot)*4+:4];
        else if(slot<14)digit=I_pixels_bcd[(13-slot)*4+:4];
        else if(slot<19)digit=I_seconds_bcd[(18-slot)*4+:4];
        else if(slot<21)digit=I_camera_fps_bcd[(20-slot)*4+:4];
        else if(slot<23)digit=I_output_fps_bcd[(22-slot)*4+:4];
        else if(slot<28)digit=I_exposure_bcd[(27-slot)*4+:4];
        else if(slot<31)digit=I_gain_bcd[(30-slot)*4+:4];
        else case(slot)
            31:digit={3'd0,I_target};32:digit={3'd0,I_alarm};33:digit={3'd0,I_audio};
            34:digit={3'd0,I_debug[0]};35:digit={3'd0,I_debug[1]};
            36:digit={3'd0,I_debug[2]};37:digit={3'd0,I_debug[3]};
            38:digit={3'd0,I_cam_cfg};39:digit={3'd0,I_ddr_ready};
            40:digit={3'd0,I_source_ok};41:digit={3'd0,I_wb_locked};42:digit={3'd0,I_armed};
            default:digit=0;
        endcase
    end
    function [7:0] direction_char;
        input vertical;
        input [1:0] zone;
        input second;
        begin
            if(vertical)direction_char=second?ZH_U90E8:
                zone==0?ZH_U4E0A:zone==1?ZH_U4E2D:ZH_U4E0B; // 部 上 中 下
            else direction_char=second?(zone==1?ZH_U592E:ZH_U4FA7):
                zone==0?ZH_U5DE6:zone==1?ZH_U4E2D:ZH_U53F3; // 央 侧 左 中 右
        end
    endfunction
    wire signed [3:0] temperature=I_color_control[5:2];
    wire [3:0] temperature_abs=temperature[3]?(~temperature+4'd1):temperature;
    wire [7:0] manual_glyph=slot==55?(temperature==0?ZH_U4E2D:temperature[3]?ZH_U51B7:ZH_U6696):
        slot==56?ZH_DIGIT_BASE+temperature_abs:
        slot==57?(I_color_control[1:0]==1?ZH_U54C1:I_color_control[1:0]==2?ZH_U7EFF:ZH_U4E2D):
        slot==54?(I_color_control[1:0]==1?ZH_U7EA2:I_color_control[1:0]==2?ZH_U8272:ZH_U6027):
        slot==58?(I_color_control==0?ZH_U65E0:ZH_U6709):ZH_SPACE;
    function [7:0] hex_char;
        input [3:0] nibble;
        begin hex_char=nibble<10?ZH_DIGIT_BASE+nibble:ZH_HEX_A_BASE+nibble-10;end
    endfunction
    wire [3:0] latency_digit=I_latency_bcd[(63-slot)*4+:4];
    wire [3:0] frame_nibble=I_latency_frame_id[(47-slot)*4+:4];
    wire [7:0] dynamic_glyph=slot>=59?(I_latency_valid?ZH_DIGIT_BASE+latency_digit:8'd21):
        latency_panel1 && slot==43?ZH_DIGIT_BASE+I_latency_valid:
        latency_panel1 && slot>=44 && slot<=47?hex_char(frame_nibble):
        latency_panel1 && slot==48?ZH_DIGIT_BASE+I_latency_repeat:
        latency_panel1 && slot==49?ZH_DIGIT_BASE+I_latency_skip:
        latency_panel1 && slot==50?hex_char(I_latency_status[7:4]):
        latency_panel1 && slot==51?hex_char(I_latency_status[3:0]):
        style_panel1 && slot==52?ZH_DIGIT_BASE+style_level1+8'd1:
        base_panel1 && slot>=54 && slot<=58?manual_glyph:
        slot<43?ZH_DIGIT_BASE+digit:
        !I_target?ZH_SPACE:
        slot==43 || slot==44?direction_char(1'b1,I_aid_v_zone,slot==44):
        slot==49 || slot==50?direction_char(1'b0,I_aid_h_zone,slot==50):ZH_SPACE;
    wire [7:0] glyph=code[8]?dynamic_glyph:code[7:0];
    wire [15:0] bits;
    fusion_chinese_font_rom u_font(.I_clk(I_clk),.I_address({glyph,font_row1}),.O_bits(bits));
    assign O_hit=visible2 && bits[15-col2];
    assign O_color=24'hfff200;
endmodule
