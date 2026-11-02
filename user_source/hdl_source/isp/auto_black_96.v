// =============================================================================
// auto_black_96 : 自适应黑电平 / 去灰（每帧统计、下一帧校正），用于 1.5 工程
//
// 问题：板上画面整体发灰、偏粉紫。实测照片中最暗 5% 的像素约 100~120（手机直拍同场景约 55），
//   且 R、B 高于 G。原因是白平衡输出里仍有一个“黑底”：传感器黑电平只减了固定的 8，
//   残余部分又被白平衡的 R/B 增益放大（所以暗部偏粉紫），再加上镜头杂散光；
//   这个底经过 sRGB 伽马（暗部斜率约 12 倍）后被大幅抬高，整幅画面就灰了。
//
// 做法（相当于每帧自动“定黑场”，按通道分别做）：
//   统计：每拍取最左像素，分别统计 R/G/B 中 <= 当前黑点 b 的像素个数 cnt。
//         帧首时：cnt > N/128 → b 减 1；cnt < N/512 → b 加 1（目标约为最暗 0.4% 的值）。
//         同时用同样方法跟踪 G 的中位数 med（步长 2），b 上限 = min(63, med/2)，
//         避免整幅画面都很亮（例如对着白墙）时把正常内容当成黑底减掉。
//         每帧最多变化 1，约 1 秒收敛，画面不会闪。
//   校正：out = (in - b) * 255/(255 - b)，白点不变，只把黑底拉回到 0。
//   I_enable = 0 时 b 按 0 处理（直通），统计照常进行，可用按键做开/关对比。
//
// 数据流水 2 拍，valid/user/last 同步延迟 2 拍。
// =============================================================================
module auto_black_96 (
    input             clk,
    input             rst_n,
    input             I_enable,
    input      [95:0] din,
    input             valid_in,
    input             user_in,
    input             last_in,
    output reg [95:0] dout,
    output            valid_out,
    output            user_out,
    output            last_out,
    output     [17:0] O_black          // {b_r[5:0], b_g[5:0], b_b[5:0]}，调试用
);

localparam [5:0] BMAX = 6'd63;

// 255*256/(255-b)，b = 0..63
function [9:0] kgain;
    input [5:0] b;
    begin
        case(b)
        6'd0: kgain = 10'd256;
        6'd1: kgain = 10'd257;
        6'd2: kgain = 10'd258;
        6'd3: kgain = 10'd259;
        6'd4: kgain = 10'd260;
        6'd5: kgain = 10'd261;
        6'd6: kgain = 10'd262;
        6'd7: kgain = 10'd263;
        6'd8: kgain = 10'd264;
        6'd9: kgain = 10'd265;
        6'd10: kgain = 10'd266;
        6'd11: kgain = 10'd268;
        6'd12: kgain = 10'd269;
        6'd13: kgain = 10'd270;
        6'd14: kgain = 10'd271;
        6'd15: kgain = 10'd272;
        6'd16: kgain = 10'd273;
        6'd17: kgain = 10'd274;
        6'd18: kgain = 10'd275;
        6'd19: kgain = 10'd277;
        6'd20: kgain = 10'd278;
        6'd21: kgain = 10'd279;
        6'd22: kgain = 10'd280;
        6'd23: kgain = 10'd281;
        6'd24: kgain = 10'd283;
        6'd25: kgain = 10'd284;
        6'd26: kgain = 10'd285;
        6'd27: kgain = 10'd286;
        6'd28: kgain = 10'd288;
        6'd29: kgain = 10'd289;
        6'd30: kgain = 10'd290;
        6'd31: kgain = 10'd291;
        6'd32: kgain = 10'd293;
        6'd33: kgain = 10'd294;
        6'd34: kgain = 10'd295;
        6'd35: kgain = 10'd297;
        6'd36: kgain = 10'd298;
        6'd37: kgain = 10'd299;
        6'd38: kgain = 10'd301;
        6'd39: kgain = 10'd302;
        6'd40: kgain = 10'd304;
        6'd41: kgain = 10'd305;
        6'd42: kgain = 10'd306;
        6'd43: kgain = 10'd308;
        6'd44: kgain = 10'd309;
        6'd45: kgain = 10'd311;
        6'd46: kgain = 10'd312;
        6'd47: kgain = 10'd314;
        6'd48: kgain = 10'd315;
        6'd49: kgain = 10'd317;
        6'd50: kgain = 10'd318;
        6'd51: kgain = 10'd320;
        6'd52: kgain = 10'd322;
        6'd53: kgain = 10'd323;
        6'd54: kgain = 10'd325;
        6'd55: kgain = 10'd326;
        6'd56: kgain = 10'd328;
        6'd57: kgain = 10'd330;
        6'd58: kgain = 10'd331;
        6'd59: kgain = 10'd333;
        6'd60: kgain = 10'd335;
        6'd61: kgain = 10'd336;
        6'd62: kgain = 10'd338;
        6'd63: kgain = 10'd340;
        default: kgain = 10'd256;
        endcase
    end
endfunction

// ------------------------------- 统计 ---------------------------------------
reg  [5:0]  b_r, b_g, b_b;             // 当前帧使用的黑点（I_enable=0 时也照常跟踪）
reg  [7:0]  med;                       // G 中位数估计
reg  [17:0] n_cnt, c_r, c_g, c_b, c_m;
reg         user_d;

wire [7:0] sr = din[95:88];
wire [7:0] sg = din[87:80];
wire [7:0] sb = din[79:72];
wire frame_start = user_in && !user_d;

wire [17:0] t_hi  = n_cnt >> 7;        // 2 倍目标
wire [17:0] t_lo  = n_cnt >> 9;        // 0.5 倍目标
wire [17:0] half  = n_cnt >> 1;
wire [17:0] h_tol = n_cnt >> 4;
wire [5:0]  b_lim = (med[7:1] > {1'b0, BMAX}) ? BMAX : med[6:1];

function [5:0] track;                  // 按计数调整黑点，并限制在 0..lim
    input [5:0]  b;
    input [17:0] cnt, hi, lo;
    input [5:0]  lim;
    reg   [5:0]  nb;
    begin
        if(cnt > hi && b != 0)      nb = b - 1'b1;
        else if(cnt < lo && b < lim) nb = b + 1'b1;
        else                        nb = b;
        track = (nb > lim) ? lim : nb;
    end
endfunction

always @(posedge clk or negedge rst_n) begin
    if(!rst_n) begin
        user_d <= 1'b0;
        b_r <= 6'd0; b_g <= 6'd0; b_b <= 6'd0;
        med <= 8'd64;
        n_cnt <= 18'd0; c_r <= 18'd0; c_g <= 18'd0; c_b <= 18'd0; c_m <= 18'd0;
    end else begin
        user_d <= user_in;
        if(frame_start) begin
            if(n_cnt >= 18'd1024) begin
                b_r <= track(b_r, c_r, t_hi, t_lo, b_lim);
                b_g <= track(b_g, c_g, t_hi, t_lo, b_lim);
                b_b <= track(b_b, c_b, t_hi, t_lo, b_lim);
                if(c_m > half + h_tol)      med <= (med < 8'd2)   ? 8'd0   : med - 8'd2;
                else if(c_m < half - h_tol) med <= (med > 8'd253) ? 8'd255 : med + 8'd2;
            end
            n_cnt <= 18'd0; c_r <= 18'd0; c_g <= 18'd0; c_b <= 18'd0; c_m <= 18'd0;
        end else if(valid_in && !(&n_cnt)) begin
            n_cnt <= n_cnt + 1'b1;
            if(sr <= {2'b0, b_r}) c_r <= c_r + 1'b1;
            if(sg <= {2'b0, b_g}) c_g <= c_g + 1'b1;
            if(sb <= {2'b0, b_b}) c_b <= c_b + 1'b1;
            if(sg <= med)         c_m <= c_m + 1'b1;
        end
    end
end

assign O_black = {b_r, b_g, b_b};

// ------------------------------- 校正 ---------------------------------------
wire [5:0] e_r = I_enable ? b_r : 6'd0;
wire [5:0] e_g = I_enable ? b_g : 6'd0;
wire [5:0] e_b = I_enable ? b_b : 6'd0;

reg  [9:0]  k_r, k_g, k_b;             // 与 e_* 同拍对应的增益
always @(posedge clk) begin
    k_r <= kgain(e_r); k_g <= kgain(e_g); k_b <= kgain(e_b);
end

function [7:0] sub0;                   // max(0, c - b)
    input [7:0] c;
    input [5:0] b;
    begin
        sub0 = (c > {2'b0, b}) ? c - {2'b0, b} : 8'd0;
    end
endfunction

function [7:0] mulk;                   // (d * k + 128) >> 8，限制到 255
    input [7:0] d;
    input [9:0] k;
    reg   [17:0] p;
    begin
        p    = d * k + 18'd128;
        mulk = (p[17:16] != 2'b00) ? 8'd255 : p[15:8];
    end
endfunction

reg [95:0] s1;
reg [1:0]  v, u, l;
integer i;
always @(posedge clk or negedge rst_n) begin
    if(!rst_n) begin
        s1 <= 96'd0; dout <= 96'd0; v <= 2'd0; u <= 2'd0; l <= 2'd0;
    end else begin
        v <= {v[0], valid_in}; u <= {u[0], user_in}; l <= {l[0], last_in};
        for(i = 0; i < 4; i = i + 1) begin
            s1[i*24+16 +: 8] <= sub0(din[i*24+16 +: 8], e_r);
            s1[i*24+8  +: 8] <= sub0(din[i*24+8  +: 8], e_g);
            s1[i*24    +: 8] <= sub0(din[i*24    +: 8], e_b);
            dout[i*24+16 +: 8] <= mulk(s1[i*24+16 +: 8], k_r);
            dout[i*24+8  +: 8] <= mulk(s1[i*24+8  +: 8], k_g);
            dout[i*24    +: 8] <= mulk(s1[i*24    +: 8], k_b);
        end
    end
end

assign valid_out = v[1];
assign user_out  = u[1];
assign last_out  = l[1];

endmodule
