module fusion_telemetry #(parameter integer CLK_HZ=75000000)(
    input wire I_clk,I_rst_n,I_frame,I_source_clk,I_source_frame,
    input wire [11:0] I_x,I_y,
    input wire [31:0] I_pixels,
    input wire [15:0] I_exposure,I_gain,
    input wire [31:0] I_latency_us,
    output reg [19:0] O_latency_bcd,
    output reg [15:0] O_x_bcd,O_y_bcd,
    output reg [23:0] O_pixels_bcd,
    output reg [19:0] O_seconds_bcd,O_exposure_bcd,
    output reg [7:0] O_camera_fps_bcd,O_output_fps_bcd,
    output reg [11:0] O_gain_bcd
);
    localparam TB=$clog2(CLK_HZ);
    reg [TB-1:0] tick;
    reg [15:0] seconds;
    reg [7:0] cam_count,out_count,cam_fps,out_fps;
    reg source_toggle,source_d;
    (* ASYNC_REG="TRUE" *) reg [2:0] source_sync;
    always @(posedge I_source_clk or negedge I_rst_n) begin
        if(!I_rst_n) begin source_toggle<=0;source_d<=0;end
        else begin source_d<=I_source_frame;if(I_source_frame && !source_d) source_toggle<=~source_toggle;end
    end
    wire camera_event=source_sync[2]!=source_sync[1];
    always @(posedge I_clk or negedge I_rst_n) begin
        if(!I_rst_n) begin tick<=0;seconds<=0;cam_count<=0;out_count<=0;cam_fps<=0;out_fps<=0;source_sync<=0;end
        else begin
            source_sync<={source_sync[1:0],source_toggle};
            if(tick==CLK_HZ-1) begin
                tick<=0;seconds<=seconds+1'b1;
                cam_fps<=cam_count+camera_event;out_fps<=out_count+I_frame;
                cam_count<=0;out_count<=0;
            end else begin
                tick<=tick+1'b1;
                if(camera_event && cam_count!=255)cam_count<=cam_count+1'b1;
                if(I_frame && out_count!=255)out_count<=out_count+1'b1;
            end
        end
    end
    // One shared shift/add-3 converter, eight values per video frame.
    // No dividers, multipliers, or additional image buffers.
    reg busy;
    reg [3:0] field;
    reg [5:0] bit_count;
    reg [31:0] binary;
    reg [39:0] bcd;
    reg [39:0] adjusted,next_bcd;
    integer k;
    function [31:0] value_for;
        input [3:0] f;
        begin case(f)
            0:value_for={20'd0,I_x};1:value_for={20'd0,I_y};2:value_for=I_pixels;
            3:value_for={16'd0,seconds};4:value_for={24'd0,cam_fps};5:value_for={24'd0,out_fps};
            6:value_for={16'd0,I_exposure};7:value_for={16'd0,I_gain};default:value_for=I_latency_us;
        endcase end
    endfunction
    always @* begin
        adjusted=bcd;
        for(k=0;k<10;k=k+1)if(bcd[k*4+:4]>=5)adjusted[k*4+:4]=bcd[k*4+:4]+4'd3;
        next_bcd={adjusted[38:0],binary[31]};
    end
    always @(posedge I_clk or negedge I_rst_n) begin
        if(!I_rst_n) begin
            busy<=0;field<=0;bit_count<=0;binary<=0;bcd<=0;
            O_x_bcd<=0;O_y_bcd<=0;O_pixels_bcd<=0;O_seconds_bcd<=0;
            O_camera_fps_bcd<=0;O_output_fps_bcd<=0;O_exposure_bcd<=0;O_gain_bcd<=0;O_latency_bcd<=0;
        end else if(I_frame) begin busy<=1;field<=0;bit_count<=0;binary<=value_for(0);bcd<=0;end
        else if(busy) begin
            binary<={binary[30:0],1'b0};bcd<=next_bcd;
            if(bit_count==31) begin
                case(field)
                    0:O_x_bcd<=next_bcd[15:0];1:O_y_bcd<=next_bcd[15:0];
                    2:O_pixels_bcd<=next_bcd[23:0];3:O_seconds_bcd<=next_bcd[19:0];
                    4:O_camera_fps_bcd<=next_bcd[7:0];5:O_output_fps_bcd<=next_bcd[7:0];
                    6:O_exposure_bcd<=next_bcd[19:0];7:O_gain_bcd<=next_bcd[11:0];
                    // Five digits in 10us units, displayed as XXX.XX ms.
                    8:O_latency_bcd<=next_bcd[23:4];
                endcase
                if(field==8)busy<=0;
                else begin field<=field+1'b1;binary<=value_for(field+1'b1);bit_count<=0;bcd<=0;end
            end else bit_count<=bit_count+1'b1;
        end
    end
endmodule
