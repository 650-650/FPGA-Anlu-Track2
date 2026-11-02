module fusion_flame_pipeline #(
    parameter integer WIDTH=1280, HEIGHT=720,
    parameter integer PIXEL_CLK_HZ=75000000,
    parameter integer TIMEOUT_CYCLES=PIXEL_CLK_HZ/2,
    parameter integer ARM_FRAMES=8,
    parameter integer ERROR_HOLD_CYCLES=PIXEL_CLK_HZ/20,
    parameter integer SEPARATE_INPUT=0,
    parameter integer MIN_PIXELS=80, MIN_WIDTH=3, MIN_HEIGHT=6,
    parameter integer MAX_WIDTH=WIDTH/3, MAX_HEIGHT=HEIGHT*3/4
)(
    input wire I_clk,I_rst_n,I_source_clk,I_source_frame,
    input wire I_cam_cfg_done,I_ddr_ready,I_mipi_error,
    input wire I_mode_clear,I_wb_locked,
    input wire [7:0] I_control,
    input wire I_vsync,I_hsync,I_de,
    input wire [23:0] I_clean_rgb,I_composite_rgb,I_detector_rgb,
    input wire I_overlay_hit,
    output wire O_vsync,O_hsync,O_de,
    output wire [23:0] O_rgb,
    output wire [3:0] O_led,
    output wire O_buzzer_n,O_alarm,O_target,O_source_ok,O_video_lost,O_armed,
    output wire [31:0] O_candidate_pixels,
    output wire [11:0] O_center_x,O_center_y
);
    wire alive;
    camera_frame_watchdog #(.TIMEOUT_CYCLES(TIMEOUT_CYCLES)) u_watchdog(
        .I_source_clk(I_source_clk),.I_source_rst_n(I_rst_n),.I_source_frame(I_source_frame),
        .I_pixel_clk(I_clk),.I_pixel_rst_n(I_rst_n),.O_source_alive(alive));
    (* ASYNC_REG="TRUE" *) reg [2:0] cfg_sync,ddr_sync,error_sync,clear_sync,wb_sync;
    localparam EB=$clog2(ERROR_HOLD_CYCLES+1);
    reg [EB-1:0] error_age;
    wire persistent_error=error_age==ERROR_HOLD_CYCLES;
    always @(posedge I_clk or negedge I_rst_n)begin
        if(!I_rst_n)error_age<=0;
        else if(!error_sync[2])error_age<=0;
        else if(!persistent_error)error_age<=error_age+1'b1;
    end
    reg source_toggle;
    reg source_frame_d;
    (* ASYNC_REG="TRUE" *) reg [2:0] source_sync;
    always @(posedge I_source_clk or negedge I_rst_n) begin
        if(!I_rst_n) begin source_toggle<=0;source_frame_d<=0;end
        else begin
            source_frame_d<=I_source_frame;
            if(I_source_frame && !source_frame_d) source_toggle<=~source_toggle;
        end
    end
    wire camera_event=source_sync[2]!=source_sync[1];
    reg vs_d;
    wire new_frame=I_vsync && !vs_d;
    localparam AB=$clog2(ARM_FRAMES+1);
    reg [AB-1:0] camera_guard,display_guard;
    wire selected=I_control[7:5]==2;
    wire aid_view=selected && I_control[4:3]==3;
    wire alarm_view=selected && I_control[4:3]==2;
    // A brief lane-alignment indication does not erase many good frames.
    // Sustained error, lost source, missing display EOF or DDR loss still stop it.
    assign O_source_ok=alive && cfg_sync[2] && ddr_sync[2] && !persistent_error;
    assign O_armed=selected && O_source_ok && clear_sync[2] && wb_sync[2] &&
                   camera_guard==ARM_FRAMES && display_guard==ARM_FRAMES;
    always @(posedge I_clk or negedge I_rst_n) begin
        if(!I_rst_n) begin
            cfg_sync<=0;ddr_sync<=0;error_sync<=0;clear_sync<=0;wb_sync<=0;source_sync<=0;
            camera_guard<=0;display_guard<=0;vs_d<=0;
        end else begin
            cfg_sync<={cfg_sync[1:0],I_cam_cfg_done};
            ddr_sync<={ddr_sync[1:0],I_ddr_ready};
            error_sync<={error_sync[1:0],I_mipi_error};
            clear_sync<={clear_sync[1:0],I_mode_clear};
            wb_sync<={wb_sync[1:0],I_wb_locked};
            source_sync<={source_sync[1:0],source_toggle};vs_d<=I_vsync;
            if(!selected || !O_source_ok || !clear_sync[2] || !wb_sync[2]) begin camera_guard<=0;display_guard<=0;end
            else begin
                if(camera_event && camera_guard<ARM_FRAMES) camera_guard<=camera_guard+1'b1;
                if(new_frame && display_guard<ARM_FRAMES) display_guard<=display_guard+1'b1;
            end
        end
    end
    wire [23:0] detection_rgb=SEPARATE_INPUT?I_detector_rgb:I_clean_rgb;
    wire [23:0] detector_rgb;
    wire detector_lost;
    wire fire_alarm,fire_target;
    wire [31:0] fire_pixels;
    wire [11:0] fire_x,fire_y;
    visual_flame_alarm #(.FRAME_WIDTH(WIDTH),.FRAME_HEIGHT(HEIGHT),
        .MIN_PIXELS(MIN_PIXELS),.MIN_WIDTH(MIN_WIDTH),.MIN_HEIGHT(MIN_HEIGHT),
        .MAX_WIDTH(MAX_WIDTH),.MAX_HEIGHT(MAX_HEIGHT),.WATCHDOG_CYCLES(TIMEOUT_CYCLES),
        .CHANGE_SHIFT(5),.CHANGE_EVENTS(2),.USE_SHAPE_CHANGE(1),.SEPARATE_INPUT(1)) u_detector(
        .I_clk(I_clk),.I_rst_n(I_rst_n),.I_enable(O_armed && !aid_view),
        .I_vsync(I_vsync),.I_hsync(I_hsync),.I_de(I_de),.I_rgb(I_clean_rgb),.I_detector_rgb(detection_rgb),
        .O_vsync(O_vsync),.O_hsync(O_hsync),.O_de(O_de),.O_rgb(detector_rgb),
        .O_alarm(fire_alarm),.O_target_present(fire_target),.O_candidate_pixels(fire_pixels),
        .O_frame_done(),.O_video_lost(detector_lost),
        .O_center_x(fire_x),.O_center_y(fire_y));
    reg [11:0] aid_x,aid_y;
    wire [11:0] pixel_x=new_frame?12'd0:aid_x;
    wire [11:0] pixel_y=new_frame?12'd0:aid_y;
    always @(posedge I_clk or negedge I_rst_n)begin
        if(!I_rst_n)begin aid_x<=0;aid_y<=0;end
        else begin
            if(new_frame)begin aid_x<=0;aid_y<=0;end
            if(I_de)begin
                if(pixel_x==WIDTH-1)begin aid_x<=0;aid_y<=pixel_y+1'b1;end
                else begin aid_x<=pixel_x+1'b1;aid_y<=pixel_y;end
            end
        end
    end
    wire aid_hit,aid_target;
    wire [23:0] aid_color;
    wire [11:0] aid_center_x,aid_center_y;
    first_aid_detector u_aid(.clk(I_clk),.rst_n(I_rst_n),.frame_start(new_frame),
        .de(I_de),.enable(O_armed && aid_view),.x(pixel_x),.y(pixel_y),.rgb(detection_rgb),
        .hit(aid_hit),.color(aid_color),.target(aid_target),.center_x(aid_center_x),.center_y(aid_center_y));
    assign O_alarm=aid_view?1'b0:fire_alarm;
    assign O_target=aid_view?aid_target:fire_target;
    assign O_center_x=aid_view?aid_center_x:fire_x;
    assign O_center_y=aid_view?aid_center_y:fire_y;
    assign O_candidate_pixels=aid_view?32'd0:fire_pixels;
    // The hardware video watchdog remains meaningful outside the detection group.
    assign O_video_lost=!O_source_ok || (selected && !aid_view && O_armed && detector_lost);
    reg overlay_d,aid_hit_d;
    reg [23:0] composite_d;
    always @(posedge I_clk or negedge I_rst_n) begin
        if(!I_rst_n) begin overlay_d<=0;composite_d<=0;aid_hit_d<=0;end
        else begin overlay_d<=I_overlay_hit;composite_d<=I_composite_rgb;aid_hit_d<=aid_hit;end
    end
    assign O_rgb=overlay_d ? composite_d : aid_hit_d ? 24'h00ff40:detector_rgb;
    wire raw_buzzer;
    alarm_board_io #(.PIXEL_CLK_HZ(PIXEL_CLK_HZ)) u_io(
        .I_clk(I_clk),.I_rst_n(I_rst_n),.I_alarm(O_alarm && O_armed && alarm_view),
        .I_source_ok(O_source_ok),.I_video_lost(O_video_lost),.O_led(O_led),.O_buzzer_n(raw_buzzer));
    // Mute changes audio only. Leaving SW2 or losing the source silences immediately.
    assign O_buzzer_n=I_control[2] || !selected || !alarm_view || !O_source_ok ? 1'b1:raw_buzzer;
endmodule
