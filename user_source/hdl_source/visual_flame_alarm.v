// Experimental yellow/orange tip detector, NOT a life-safety fire alarm.
// Thresholds are engineering starting points, not calibrated camera readings.
module flame_pixel_classifier #(
    parameter integer WARM_R_MIN = 144,
    parameter integer WARM_G_MIN = 72,
    parameter integer WARM_RG_TOL = 24,
    parameter integer WARM_GB_MARGIN = 16
)(
    input wire [23:0] I_rgb,
    output wire O_candidate
);
    wire [7:0] r = I_rgb[23:16];
    wire [7:0] g = I_rgb[15:8];
    wire [7:0] b = I_rgb[7:0];
    wire warm = r >= WARM_R_MIN && g >= WARM_G_MIN &&
                ({g,1'b0} >= {1'b0,r}) &&
                ({1'b0,r} + WARM_RG_TOL >= {1'b0,g}) &&
                ({1'b0,g} >= {1'b0,b} + WARM_GB_MARGIN);
    // Deliberately reject neutral white, cyan, blue and saturated red.
    // A washed-out warm rim remains usable in daylight. Neutral white still
    // fails this test and can only enter through a recent spatial warm anchor.
    wire pale_warm=r>=208 && g>=176 && {1'b0,r}>={1'b0,b}+10 &&
        {1'b0,g}>={1'b0,b}+4 && {1'b0,r}+12>={1'b0,g};
    assign O_candidate = warm || pale_warm;
endmodule

module visual_flame_alarm #(
    parameter integer SEPARATE_INPUT = 0,
    parameter integer FRAME_WIDTH = 1280,
    parameter integer FRAME_HEIGHT = 720,
    parameter integer MIN_PIXELS = 80,
    parameter integer MIN_WIDTH = 3,
    parameter integer MIN_HEIGHT = 6,
    parameter integer MAX_WIDTH = FRAME_WIDTH / 3,
    parameter integer MAX_HEIGHT = FRAME_HEIGHT * 3 / 4,
    parameter integer MIN_FILL_SHIFT = 3,
    parameter integer WARM_R_MIN = 144, WARM_G_MIN = 72,
    parameter integer WARM_RG_TOL = 24, WARM_GB_MARGIN = 16,
    parameter integer CHANGE_MIN_PIXELS = 4,
    parameter integer CHANGE_SHIFT = 4,
    parameter integer CHANGE_WINDOW = 16,
    parameter integer CHANGE_EVENTS = 3,
    parameter integer USE_SHAPE_CHANGE = 0,
    parameter integer ASSOC_MARGIN = 32,
    parameter integer ASSERT_FRAMES = 3,
    parameter integer RELEASE_FRAMES = 5,
    parameter integer WATCHDOG_CYCLES = 37500000,
    parameter integer BORDER_WIDTH = 2
)(
    input wire I_clk, I_rst_n, I_enable, I_vsync, I_hsync, I_de,
    input wire [23:0] I_rgb,I_detector_rgb,
    output reg O_vsync, O_hsync, O_de,
    output reg [23:0] O_rgb,
    output reg O_alarm, O_target_present,
    output reg [31:0] O_candidate_pixels,
    output wire [11:0] O_center_x,O_center_y,
    output reg O_frame_done, O_video_lost
);
    localparam integer COUNT_BITS = $clog2(FRAME_WIDTH * FRAME_HEIGHT + 1);
    localparam integer WD_BITS = (WATCHDOG_CYCLES < 2) ? 1 : $clog2(WATCHDOG_CYCLES + 1);
    localparam integer HIT_BITS = (ASSERT_FRAMES < 2) ? 1 : $clog2(ASSERT_FRAMES + 1);
    localparam integer MISS_BITS = (RELEASE_FRAMES < 2) ? 1 : $clog2(RELEASE_FRAMES + 1);
    localparam integer EVENT_BITS = $clog2(CHANGE_WINDOW + 1);
    reg vsync_d, frame_active;
    reg [11:0] x, y;
    reg [COUNT_BITS-1:0] count;
    reg [WD_BITS-1:0] watchdog;
    reg [11:0] xmin, xmax, ymin, ymax;
    reg work_valid;
    wire start = I_vsync && !vsync_d;
    wire [11:0] px = start ? 12'd0 : x;
    wire [11:0] py = start ? 12'd0 : y;
    wire accept = I_enable && I_de && (start || frame_active);
    wire complete = accept && px == FRAME_WIDTH-1 && py == FRAME_HEIGHT-1;
    wire timeout_now = !complete && watchdog == WATCHDOG_CYCLES-1;
    wire [23:0] classifier_rgb=SEPARATE_INPUT?I_detector_rgb:I_rgb;
    wire color_candidate;
    flame_pixel_classifier #(
        .WARM_R_MIN(WARM_R_MIN), .WARM_G_MIN(WARM_G_MIN),
        .WARM_RG_TOL(WARM_RG_TOL), .WARM_GB_MARGIN(WARM_GB_MARGIN)
    ) u_color(.I_rgb(classifier_rgb), .O_candidate(color_candidate));
    localparam LUMA_BITS=COUNT_BITS+8;
    localparam SEED_MIN=MIN_PIXELS<12?MIN_PIXELS:12;
    reg [COUNT_BITS-1:0] warm_count;
    reg [11:0] wx0,wx1,wy0,wy1,seed_x0,seed_x1,seed_y0,seed_y1;
    reg seed_valid;
    reg [LUMA_BITS-1:0] luma_sum;
    wire [7:0] r=classifier_rgb[23:16],g=classifier_rgb[15:8],b=classifier_rgb[7:0];
    wire [7:0] maximum=r>g?(r>b?r:b):(g>b?g:b);
    wire [7:0] minimum=r<g?(r<b?r:b):(g<b?g:b);
    wire bright_core=(minimum>=176 && maximum-minimum<=48) ||
        (b>=160 && g>=100 && r>=64 && {1'b0,b}>={1'b0,r}+32);
    wire in_seed=seed_valid && {1'b0,px}+13'd12>={1'b0,seed_x0} &&
        {1'b0,px}<={1'b0,seed_x1}+13'd12 && {1'b0,py}+13'd16>={1'b0,seed_y0} &&
        {1'b0,py}<={1'b0,seed_y1}+13'd16;
    wire candidate = accept && (color_candidate || (in_seed && bright_core));
    wire warm_pixel=accept && color_candidate;
    wire [COUNT_BITS-1:0] warm_next=(start?0:warm_count)+warm_pixel;
    wire [11:0] wx0_next=warm_pixel && (start || warm_count==0 || px<wx0)?px:wx0;
    wire [11:0] wx1_next=warm_pixel && (start || warm_count==0 || px>wx1)?px:wx1;
    wire [11:0] wy0_next=warm_pixel && (start || warm_count==0 || py<wy0)?py:wy0;
    wire [11:0] wy1_next=warm_pixel && (start || warm_count==0 || py>wy1)?py:wy1;
    wire [9:0] luminance={2'd0,r}+{1'b0,g,1'b0}+{2'd0,b};
    wire [LUMA_BITS-1:0] luma_next=(start?0:luma_sum)+(candidate?luminance[9:2]:8'd0);
    wire valid_base = work_valid && !start;
    wire [COUNT_BITS-1:0] count_next = (start ? {COUNT_BITS{1'b0}} : count) + candidate;
    wire [11:0] xmin_next = candidate && (!valid_base || px < xmin) ? px : xmin;
    wire [11:0] xmax_next = candidate && (!valid_base || px > xmax) ? px : xmax;
    wire [11:0] ymin_next = candidate && (!valid_base || py < ymin) ? py : ymin;
    wire [11:0] ymax_next = candidate && (!valid_base || py > ymax) ? py : ymax;

    // Snapshot at EOF; expensive frame decisions do not extend the pixel path.
    reg eval_pending, eval_valid;
    reg [COUNT_BITS-1:0] eval_count,eval_warm;
    reg [LUMA_BITS-1:0] eval_luma,previous_luma;
    reg [11:0] ex0, ex1, ey0, ey1;
    reg commit_pending, commit_geometry, commit_hit;
    reg [COUNT_BITS-1:0] commit_count;
    reg [11:0] cx0, cx1, cy0, cy1;
    reg box_valid;
    reg [11:0] bx0, bx1, by0, by1;
    assign O_center_x=O_target_present ? (({1'b0,bx0}+{1'b0,bx1}) >> 1):12'd0;
    assign O_center_y=O_target_present ? (({1'b0,by0}+{1'b0,by1}) >> 1):12'd0;
    reg previous_valid;
    reg [COUNT_BITS-1:0] previous_count;
    reg [11:0] previous_x0, previous_x1, previous_y0, previous_y1;
    reg [CHANGE_WINDOW-1:0] change_history;
    reg [EVENT_BITS-1:0] change_score;
    reg [HIT_BITS-1:0] hit_frames;
    reg [MISS_BITS-1:0] miss_frames;

    wire [12:0] width_value = {1'b0,ex1} - {1'b0,ex0} + 13'd1;
    wire [12:0] height_value = {1'b0,ey1} - {1'b0,ey0} + 13'd1;
    wire [25:0] box_area = width_value * height_value;
    wire geometry = eval_valid && eval_count >= MIN_PIXELS && eval_warm>=SEED_MIN &&
                    width_value >= MIN_WIDTH && height_value >= MIN_HEIGHT &&
                    width_value <= MAX_WIDTH && height_value <= MAX_HEIGHT &&
                    {1'b0,width_value} <= {height_value,1'b0} &&
                    {6'd0,eval_count} >= (box_area >> MIN_FILL_SHIFT);
    wire associated = previous_valid &&
                     {1'b0,ex0} <= {1'b0,previous_x1} + ASSOC_MARGIN &&
                     {1'b0,previous_x0} <= {1'b0,ex1} + ASSOC_MARGIN &&
                     {1'b0,ey0} <= {1'b0,previous_y1} + ASSOC_MARGIN &&
                     {1'b0,previous_y0} <= {1'b0,ey1} + ASSOC_MARGIN;
    wire [COUNT_BITS-1:0] delta = eval_count >= previous_count ?
                      eval_count - previous_count : previous_count - eval_count;
    wire [COUNT_BITS-1:0] relative_change = previous_count >> CHANGE_SHIFT;
    wire [COUNT_BITS-1:0] change_limit = relative_change > CHANGE_MIN_PIXELS ?
                      relative_change : CHANGE_MIN_PIXELS;
    // Width/height changes detect equal-area flame-tip deformation. A rigid
    // translation keeps both dimensions and cannot supply this evidence.
    wire [12:0] previous_width={1'b0,previous_x1}-{1'b0,previous_x0}+13'd1;
    wire [12:0] previous_height={1'b0,previous_y1}-{1'b0,previous_y0}+13'd1;
    // Require at least two pixels of dimension change; one-pixel threshold
    // jitter at a corner must not confirm an otherwise static yellow object.
    wire shape_changed=({1'b0,width_value}>={1'b0,previous_width}+14'd2) ||
                       ({1'b0,previous_width}>={1'b0,width_value}+14'd2) ||
                       ({1'b0,height_value}>={1'b0,previous_height}+14'd2) ||
                       ({1'b0,previous_height}>={1'b0,height_value}+14'd2);
    // Equal-area intensity flicker is evidence even when the flame's outline
    // is steady. Rigid translation of an unchanged coloured object still is not.
    wire [LUMA_BITS-1:0] luma_delta=eval_luma>=previous_luma?eval_luma-previous_luma:previous_luma-eval_luma;
    wire [LUMA_BITS-1:0] luma_limit={{8{1'b0}},eval_count}<<2;
    wire intensity_changed=eval_count==previous_count && luma_delta>=luma_limit;
    wire change_event = geometry && associated &&
                        (delta >= change_limit || (USE_SHAPE_CHANGE && shape_changed) || intensity_changed);
    wire [EVENT_BITS-1:0] next_score = !geometry || !associated ? 0 :
                      change_score - change_history[CHANGE_WINDOW-1] + change_event;
    wire qualified = geometry && next_score >= CHANGE_EVENTS;

    wire inside_box = box_valid && accept && px >= bx0 && px <= bx1 && py >= by0 && py <= by1;
    wire border = BORDER_WIDTH > 0 && inside_box &&
                  (px < bx0 + BORDER_WIDTH || px + BORDER_WIDTH > bx1 ||
                   py < by0 + BORDER_WIDTH || py + BORDER_WIDTH > by1);
    always @(posedge I_clk or negedge I_rst_n) begin
        if(!I_rst_n) begin
            O_vsync <= 0; O_hsync <= 0; O_de <= 0; O_rgb <= 0;
        end else begin
            O_vsync <= I_vsync; O_hsync <= I_hsync; O_de <= I_de;
            O_rgb <= !I_de ? 24'd0 : border ?
                     (O_alarm ? 24'hff0000 : 24'hffcc00) : I_rgb;
        end
    end

    always @(posedge I_clk or negedge I_rst_n) begin
        if(!I_rst_n) begin
            vsync_d <= 0; frame_active <= 0; x <= 0; y <= 0; count <= 0; watchdog <= 0;
            xmin <= 0; xmax <= 0; ymin <= 0; ymax <= 0; work_valid <= 0;
            eval_pending <= 0; eval_valid <= 0; eval_count <= 0;
            ex0 <= 0; ex1 <= 0; ey0 <= 0; ey1 <= 0;
            O_video_lost <= 1;
            warm_count<=0;wx0<=0;wx1<=0;wy0<=0;wy1<=0;
            seed_valid<=0;seed_x0<=0;seed_x1<=0;seed_y0<=0;seed_y1<=0;luma_sum<=0;
            eval_warm<=0;eval_luma<=0;
        end else begin
            vsync_d <= I_vsync;
            eval_pending <= 0;
            if(!I_enable || timeout_now) begin
                frame_active <= 0; x <= 0; y <= 0; count <= 0; work_valid <= 0;
                if(!I_enable) watchdog <= 0;
                else watchdog <= WATCHDOG_CYCLES;
                eval_valid <= 0; O_video_lost <= 1;warm_count<=0;seed_valid<=0;luma_sum<=0;
            end else begin
                if(watchdog < WATCHDOG_CYCLES) watchdog <= watchdog + 1'b1;
                if(start) begin
                    frame_active <= 1; x <= 0; y <= 0; count <= 0; work_valid <= 0;warm_count<=0;luma_sum<=0;
                end
                if(accept) begin
                    count <= count_next; work_valid <= valid_base || candidate;
                    warm_count<=warm_next;luma_sum<=luma_next;
                    wx0<=wx0_next;wx1<=wx1_next;wy0<=wy0_next;wy1<=wy1_next;
                    xmin <= xmin_next; xmax <= xmax_next; ymin <= ymin_next; ymax <= ymax_next;
                    if(px == FRAME_WIDTH-1) begin x <= 0; y <= py + 1'b1; end
                    else begin x <= px + 1'b1; y <= py; end
                end
                if(complete) begin
                    frame_active <= 0; watchdog <= 0; O_video_lost <= 0;
                    eval_pending <= 1; eval_valid <= valid_base || candidate; eval_count <= count_next;
                    ex0 <= xmin_next; ex1 <= xmax_next; ey0 <= ymin_next; ey1 <= ymax_next;
                    eval_warm<=warm_next;eval_luma<=luma_next;
                    seed_valid<=warm_next>=SEED_MIN && wx1_next-wx0_next>=1 && wy1_next-wy0_next>=3 &&
                        wx1_next-wx0_next<MAX_WIDTH && wy1_next-wy0_next<MAX_HEIGHT;
                    seed_x0<=wx0_next;seed_x1<=wx1_next;seed_y0<=wy0_next;seed_y1<=wy1_next;
                end
            end
        end
    end

    always @(posedge I_clk or negedge I_rst_n) begin
        if(!I_rst_n) begin
            commit_pending <= 0; commit_geometry <= 0; commit_hit <= 0; commit_count <= 0;
            cx0 <= 0; cx1 <= 0; cy0 <= 0; cy1 <= 0;
            previous_valid <= 0; previous_count <= 0;previous_luma<=0;
            previous_x0 <= 0; previous_x1 <= 0; previous_y0 <= 0; previous_y1 <= 0;
            change_history <= 0; change_score <= 0;
            hit_frames <= 0; miss_frames <= 0; box_valid <= 0;
            bx0 <= 0; bx1 <= 0; by0 <= 0; by1 <= 0;
            O_alarm <= 0; O_target_present <= 0; O_candidate_pixels <= 0; O_frame_done <= 0;
        end else begin
            O_frame_done <= 0; commit_pending <= 0;
            if(!I_enable || timeout_now) begin
                previous_valid <= 0; previous_luma<=0;change_history <= 0; change_score <= 0;
                hit_frames <= 0; miss_frames <= 0; box_valid <= 0;
                O_alarm <= 0; O_target_present <= 0; O_candidate_pixels <= 0;
            end else begin
                if(eval_pending) begin
                    previous_valid <= geometry; previous_count <= eval_count;previous_luma<=eval_luma;
                    previous_x0 <= ex0; previous_x1 <= ex1; previous_y0 <= ey0; previous_y1 <= ey1;
                    change_history <= !geometry || !associated ? 0 :
                                      {change_history[CHANGE_WINDOW-2:0],change_event};
                    change_score <= next_score;
                    commit_pending <= 1; commit_geometry <= geometry; commit_hit <= qualified;
                    commit_count <= eval_count; cx0 <= ex0; cx1 <= ex1; cy0 <= ey0; cy1 <= ey1;
                end
                if(commit_pending) begin
                    O_frame_done <= 1; O_candidate_pixels <= commit_count; O_target_present <= commit_geometry;
                    box_valid <= commit_geometry; bx0 <= cx0; bx1 <= cx1; by0 <= cy0; by1 <= cy1;
                    if(commit_hit) begin
                        miss_frames <= 0;
                        if(hit_frames < ASSERT_FRAMES) hit_frames <= hit_frames + 1'b1;
                        if(hit_frames >= ASSERT_FRAMES-1) O_alarm <= 1;
                    end else begin
                        hit_frames <= 0;
                        if(miss_frames < RELEASE_FRAMES) miss_frames <= miss_frames + 1'b1;
                        if(miss_frames >= RELEASE_FRAMES-1) O_alarm <= 0;
                    end
                end
            end
        end
    end

    // synthesis translate_off
    initial begin
        if(FRAME_WIDTH < 2 || FRAME_WIDTH > 4096 || FRAME_HEIGHT < 2 || FRAME_HEIGHT > 4096 ||
           MIN_PIXELS < 1 || MIN_PIXELS > FRAME_WIDTH*FRAME_HEIGHT ||
           WARM_R_MIN < 0 || WARM_R_MIN > 255 || WARM_G_MIN < 0 || WARM_G_MIN > 255 ||
           WARM_RG_TOL < 0 || WARM_RG_TOL > 255 || WARM_GB_MARGIN < 1 || WARM_GB_MARGIN > 255 ||
           MIN_WIDTH < 1 || MIN_HEIGHT < 1 || MAX_WIDTH < MIN_WIDTH || MAX_HEIGHT < MIN_HEIGHT ||
           MAX_WIDTH > FRAME_WIDTH || MAX_HEIGHT > FRAME_HEIGHT ||
           CHANGE_WINDOW < 2 || CHANGE_EVENTS < 1 || CHANGE_EVENTS > CHANGE_WINDOW ||
           CHANGE_MIN_PIXELS < 1 || CHANGE_MIN_PIXELS > FRAME_WIDTH*FRAME_HEIGHT ||
           CHANGE_SHIFT < 0 || CHANGE_SHIFT > 16 || MIN_FILL_SHIFT < 0 || MIN_FILL_SHIFT > 8 ||
           ASSOC_MARGIN < 0 || ASSOC_MARGIN > 4096 || ASSERT_FRAMES < 1 || RELEASE_FRAMES < 1 ||
           WATCHDOG_CYCLES < 1 || BORDER_WIDTH < 0 || BORDER_WIDTH > 32) begin
            $display("ERROR: invalid flame parameters"); $finish;
        end
    end
    // synthesis translate_on
endmodule
