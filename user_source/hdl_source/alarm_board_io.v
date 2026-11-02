module alarm_board_io #(
    parameter integer PIXEL_CLK_HZ = 75000000,
    parameter integer TONE_HZ = 2000
)(
    input wire I_clk,
    input wire I_rst_n,
    input wire I_alarm,
    input wire I_source_ok,
    input wire I_video_lost,
    output wire [3:0] O_led,
    output wire O_buzzer_n
);
    localparam integer HALF_SECOND = PIXEL_CLK_HZ / 2;
    localparam integer TONE_HALF_PERIOD = PIXEL_CLK_HZ / (2 * TONE_HZ);
    localparam integer SLOW_BITS = (HALF_SECOND < 2) ? 1 : $clog2(HALF_SECOND);
    localparam integer TONE_BITS = (TONE_HALF_PERIOD < 2) ? 1 : $clog2(TONE_HALF_PERIOD);
    reg [SLOW_BITS-1:0] S_heartbeat_count;
    reg [SLOW_BITS-1:0] S_beep_count;
    reg [TONE_BITS-1:0] S_tone_count;
    reg S_heartbeat;
    reg S_tone;

    // HX1P35A: LEDs are active high; the PNP buzzer driver is active low.
    assign O_led = I_rst_n ?
        {S_heartbeat, (!I_source_ok || I_video_lost),
         (I_source_ok && !I_video_lost), I_alarm} : 4'd0;
    assign O_buzzer_n = (!I_rst_n || !I_alarm || S_beep_count >= PIXEL_CLK_HZ / 4) ?
                         1'b1 : S_tone;

    always @(posedge I_clk or negedge I_rst_n) begin
        if(!I_rst_n) begin
            S_heartbeat_count <= 0;
            S_beep_count <= 0;
            S_tone_count <= 0;
            S_heartbeat <= 1'b0;
            S_tone <= 1'b1;
        end
        else begin
            if(S_heartbeat_count == HALF_SECOND - 1) begin
                S_heartbeat_count <= 0;
                S_heartbeat <= !S_heartbeat;
            end
            else
                S_heartbeat_count <= S_heartbeat_count + 1'b1;

            if(!I_alarm) begin
                S_beep_count <= 0;
                S_tone_count <= 0;
                S_tone <= 1'b1;
            end
            else begin
                if(S_beep_count == HALF_SECOND - 1)
                    S_beep_count <= 0;
                else
                    S_beep_count <= S_beep_count + 1'b1;
                if(S_tone_count == TONE_HALF_PERIOD - 1) begin
                    S_tone_count <= 0;
                    S_tone <= !S_tone;
                end
                else
                    S_tone_count <= S_tone_count + 1'b1;
            end
        end
    end
endmodule
