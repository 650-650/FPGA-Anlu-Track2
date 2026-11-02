// Two ROM reads, aligned with the mixer's existing two coordinate registers.
module fusion_hud(
    input wire I_clk,I_rst_n,
    input wire [11:0] I_x,I_y,
    input wire [7:0] I_control,
    input wire [15:0] I_x_bcd,I_y_bcd,
    input wire [23:0] I_pixels_bcd,
    input wire [19:0] I_seconds_bcd,I_exposure_bcd,
    input wire [7:0] I_camera_fps_bcd,I_output_fps_bcd,
    input wire [11:0] I_gain_bcd,
    input wire I_target,I_alarm,I_audio,I_cam_cfg,I_ddr_ready,I_source_ok,I_wb_locked,I_armed,
    input wire [3:0] I_debug,
    input wire [1:0] I_aid_h_zone,I_aid_v_zone,
    input wire [5:0] I_color_control,
    output wire O_hit,
    output wire [23:0] O_color
);
    reg [4:0] panel;
    always @* begin
        case(I_control[7:5])
            0:panel=0;
            1:panel=4+I_control[4:3];2:panel=8+I_control[4:3];
            3:panel=12+I_control[4:3];4:panel=16+I_control[4:3];default:panel=28;
        endcase
    end
    wire visible=I_x>=16 && I_x<1040 && I_y>=600 && I_y<696;
    wire [11:0] lx=I_x-12'd16;
    wire [1:0] row=I_y>=672?3:I_y>=648?2:I_y>=624?1:0;
    wire [11:0] row_base=row==3?672:row==2?648:row==1?624:600;
    wire [11:0] ly=I_y-row_base;
    wire [7:0] code;
    fusion_menu_rom u_menu(.I_clk(I_clk),.I_address({panel,row,lx[9:4]}),.O_char(code));
    reg [2:0] col1,col2,font_row1;
    reg visible1,visible2;
    always @(posedge I_clk or negedge I_rst_n) begin
        if(!I_rst_n)begin col1<=0;col2<=0;font_row1<=0;visible1<=0;visible2<=0;end
        else begin
            col1<=lx[3:1];col2<=col1;font_row1<=ly[3:1];
            visible1<=visible && ly<16;visible2<=visible1;
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
    function [6:0] direction_char;
        input vertical;
        input [1:0] zone;
        input [2:0] index;
        begin
            case({vertical,zone,index})
                6'd0:direction_char=7'd76;
                6'd1:direction_char=7'd69;
                6'd2:direction_char=7'd70;
                6'd3:direction_char=7'd84;
                6'd4:direction_char=7'd32;
                6'd5:direction_char=7'd32;
                6'd8:direction_char=7'd67;
                6'd9:direction_char=7'd69;
                6'd10:direction_char=7'd78;
                6'd11:direction_char=7'd84;
                6'd12:direction_char=7'd69;
                6'd13:direction_char=7'd82;
                6'd16:direction_char=7'd82;
                6'd17:direction_char=7'd73;
                6'd18:direction_char=7'd71;
                6'd19:direction_char=7'd72;
                6'd20:direction_char=7'd84;
                6'd21:direction_char=7'd32;
                6'd24:direction_char=7'd82;
                6'd25:direction_char=7'd73;
                6'd26:direction_char=7'd71;
                6'd27:direction_char=7'd72;
                6'd28:direction_char=7'd84;
                6'd29:direction_char=7'd32;
                6'd32:direction_char=7'd84;
                6'd33:direction_char=7'd79;
                6'd34:direction_char=7'd80;
                6'd35:direction_char=7'd32;
                6'd36:direction_char=7'd32;
                6'd37:direction_char=7'd32;
                6'd40:direction_char=7'd77;
                6'd41:direction_char=7'd73;
                6'd42:direction_char=7'd68;
                6'd43:direction_char=7'd32;
                6'd44:direction_char=7'd32;
                6'd45:direction_char=7'd32;
                6'd48:direction_char=7'd66;
                6'd49:direction_char=7'd79;
                6'd50:direction_char=7'd84;
                6'd51:direction_char=7'd84;
                6'd52:direction_char=7'd79;
                6'd53:direction_char=7'd77;
                6'd56:direction_char=7'd66;
                6'd57:direction_char=7'd79;
                6'd58:direction_char=7'd84;
                6'd59:direction_char=7'd84;
                6'd60:direction_char=7'd79;
                6'd61:direction_char=7'd77;
                default:direction_char=7'd32;
            endcase
        end
    endfunction
    wire signed [3:0] temperature=I_color_control[5:2];
    wire [3:0] temperature_abs=temperature[3]?(~temperature+4'd1):temperature;
    wire [6:0] manual_glyph=slot==55?(temperature==0?7'd78:temperature[3]?7'd67:7'd87):
        slot==56?7'd48+temperature_abs:
        slot==57?(I_color_control[1:0]==1?7'd77:I_color_control[1:0]==2?7'd71:7'd78):
        slot==58?(I_color_control==0?7'd65:7'd77):7'd32;
    wire [6:0] dynamic_glyph=slot>=55?manual_glyph:slot<43?7'd48+digit:
        !I_target?7'd32:
        slot<49?direction_char(1'b1,I_aid_v_zone,slot-43):
        slot<55?direction_char(1'b0,I_aid_h_zone,slot-49):7'd32;
    wire [6:0] glyph=code[7]?dynamic_glyph:code[6:0];
    wire [7:0] bits;
    fusion_font_rom u_font(.I_clk(I_clk),.I_address({glyph,font_row1}),.O_bits(bits));
    assign O_hit=visible2 && bits[7-col2];
    assign O_color=24'hfff200;
endmodule
