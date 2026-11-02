module camera_frame_watchdog #(
    parameter integer TIMEOUT_CYCLES = 37500000
)(
    input wire I_source_clk,
    input wire I_source_rst_n,
    input wire I_source_frame,
    input wire I_pixel_clk,
    input wire I_pixel_rst_n,
    output reg O_source_alive
);
    localparam integer COUNT_BITS = (TIMEOUT_CYCLES < 2) ? 1 : $clog2(TIMEOUT_CYCLES);
    reg S_frame_d;
    reg S_frame_toggle;
    (* ASYNC_REG = "TRUE" *) reg [2:0] S_toggle_sync;
    reg [COUNT_BITS-1:0] S_idle_count;

    always @(posedge I_source_clk or negedge I_source_rst_n) begin
        if(!I_source_rst_n) begin
            S_frame_d <= 1'b0;
            S_frame_toggle <= 1'b0;
        end
        else begin
            S_frame_d <= I_source_frame;
            if(I_source_frame && !S_frame_d)
                S_frame_toggle <= !S_frame_toggle;
        end
    end

    // Transfer a slow camera-frame event, not a narrow pulse, across clocks.
    always @(posedge I_pixel_clk or negedge I_pixel_rst_n) begin
        if(!I_pixel_rst_n) begin
            S_toggle_sync <= 3'd0;
            S_idle_count <= 0;
            O_source_alive <= 1'b0;
        end
        else begin
            S_toggle_sync <= {S_toggle_sync[1:0], S_frame_toggle};
            if(S_toggle_sync[2] != S_toggle_sync[1]) begin
                S_idle_count <= 0;
                O_source_alive <= 1'b1;
            end
            else if(S_idle_count >= TIMEOUT_CYCLES - 1)
                O_source_alive <= 1'b0;
            else
                S_idle_count <= S_idle_count + 1'b1;
        end
    end
endmodule
