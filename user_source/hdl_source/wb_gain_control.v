// Deterministic startup (05_stylize_on_v4 policy): unity gains, locked.
// Only an explicit request learns a scene. Candidate gains stay invisible
// until a complete learning window succeeds; failure preserves the last gain.
module wb_gain_control #(
    parameter integer CALIBRATION_FRAMES=64,
    parameter integer TIMEOUT_FRAMES=300
)(
    input wire I_clk,I_rst_n,I_frame_start,I_allow,I_relearn,
    input wire I_result_valid,
    input wire [47:0] I_ratio_r,I_ratio_b,
    output reg [19:0] O_gain_r,O_gain_b,
    output reg O_locked
);
    localparam integer CB=$clog2(CALIBRATION_FRAMES+1);
    localparam integer AB=$clog2(TIMEOUT_FRAMES+1);
    reg [CB-1:0] qualified_frames;
    reg [AB-1:0] age;
    reg [19:0] next_r,next_b,shadow_r,shadow_b;
    reg fresh,relearn_d,frame_d;
    wire frame=I_frame_start && !frame_d;
    wire request=I_relearn && !relearn_d;
    wire [22:0] filtered_r=((({3'b0,shadow_r}<<3)-{3'b0,shadow_r})+{3'b0,next_r}+23'd4)>>3;
    wire [22:0] filtered_b=((({3'b0,shadow_b}<<3)-{3'b0,shadow_b})+{3'b0,next_b}+23'd4)>>3;
    function [19:0] bounded_gain;
        input [47:0] ratio;
        begin
            if(ratio<48'h0c000)bounded_gain=20'h0c000;
            else if(ratio>48'h18000)bounded_gain=20'h18000;
            else bounded_gain=ratio[19:0];
        end
    endfunction
    always @(posedge I_clk or negedge I_rst_n)begin
        if(!I_rst_n)begin
            O_gain_r<=20'h10000;O_gain_b<=20'h10000;O_locked<=1;
            next_r<=20'h10000;next_b<=20'h10000;
            shadow_r<=20'h10000;shadow_b<=20'h10000;
            qualified_frames<=0;age<=0;fresh<=0;relearn_d<=0;frame_d<=0;
        end else begin
            relearn_d<=I_relearn;frame_d<=I_frame_start;
            if(request)begin
                O_locked<=0;qualified_frames<=0;age<=0;fresh<=0;
                shadow_r<=O_gain_r;shadow_b<=O_gain_b;
            end else if(!O_locked)begin
                if(I_result_valid && I_ratio_r!=0 && I_ratio_b!=0)begin
                    next_r<=bounded_gain(I_ratio_r);next_b<=bounded_gain(I_ratio_b);fresh<=1;
                end
                if(frame)begin
                    fresh<=0;
                    if(I_allow && fresh)begin
                        shadow_r<=filtered_r[19:0];shadow_b<=filtered_b[19:0];
                        if(qualified_frames==CALIBRATION_FRAMES-1)begin
                            O_gain_r<=filtered_r[19:0];O_gain_b<=filtered_b[19:0];O_locked<=1;
                        end else qualified_frames<=qualified_frames+1'b1;
                    end
                    if(age==TIMEOUT_FRAMES-1)O_locked<=1;
                    else age<=age+1'b1;
                end
            end
        end
    end
endmodule
