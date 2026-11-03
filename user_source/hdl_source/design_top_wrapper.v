

module design_top_wrapper (
    input wire        I_sys_clk,
    input wire        I_rst_n,
    input wire [3:0]  I_switches, // SW1/A4 SW2/B4 SW3/E11 SW4/D11
    output wire [3:0] O_led,
    output wire O_buzzer_n,
      
    output wire       O_cam_scl,
    inout  wire       IO_cam_sda,
    output wire       O_cam_24m,
    output wire       O_cam_rst,
      
    input wire [1:0]  I_button,
    input wire        I_key_mode, // K4; I_rst_n is now the raw K3 GPIO.

    output wire       O_tmds_ch0_p,
    output wire       O_tmds_ch1_p,
    output wire       O_tmds_ch2_p,
    output wire       O_tmds_clk_p,

    inout wire        IO_rx_clk_pad_n, 
    inout wire        IO_rx_clk_pad_p, 
    inout wire[3:0]   IO_rx_data_pad_n,
    inout wire[3:0]   IO_rx_data_pad_p,

    output wire[12:0] ddr_addr,
    output wire[ 1:0] ddr_ba,
    output wire[ 0:0] ddr_cke,
    output wire[ 0:0] ddr_odt,
    output wire[ 0:0] ddr_cs_n,
    output wire       ddr_ras_n,
    output wire       ddr_cas_n,
    output wire       ddr_we_n,
    output wire[ 0:0] ddr_ck_p,
    output wire[ 0:0] ddr_ck_n,
    inout wire[1:0]   ddr_dm,
    inout wire[15:0]  ddr_dq,
    inout wire[1:0]   ddr_dqs_p,
    inout wire[1:0]   ddr_dqs_n   
);


    wire        	S_100m_clk;
    wire        	S_24m_clk;
    wire        	S_aux_50m_clk;
	wire        	S_10m_clk;
		
	wire        	S_pll_lock;
    wire        	S_rst_n;
	
	wire [15:0] 	S_ae;
    wire [15:0] 	S_ag;
    wire 			S_cam_cfg_done;
    wire 			S_ae_cfg_done;
    wire 			S_ae_req; 
	
	wire        	S_csi_rx_clk;  
    wire        	S_hs_rx_valid;  
    wire[15:0]  	S_hs_rx_data;   
	wire[1:0]   	S_lane_error;
	
	wire        	S_csi_frame_start;       
	wire        	S_csi_frame_end;         
	wire        	S_csi_valid;             
	wire[31:0]  	S_csi_data;  
		
	wire        	S_raw10_frame_start; 
	wire        	S_raw10_frame_end;   
	wire        	S_raw10_valid;       
	wire [39:0] 	S_raw10_data;
		
	wire 			S_axis_tlast;  
	wire 			S_axis_tuser;  
	wire [39:0]		S_axis_tdata;  
	wire 			S_axis_tvalid; 
	
	wire [39:0]		S_raw_tdata ;
	wire			S_raw_tlast ;
	wire 			S_raw_tvalid;
	wire 			S_raw_tuser ;
	
	wire			S_ISP_O_tready;
	wire [127:0]	S_ISP_O_tdata ;
	wire 			S_ISP_O_tlast ;
	wire 			S_ISP_O_tuser ;
	wire 			S_ISP_O_tvalid; 
	

    wire        S_ddr_clk;
    wire        S_hdmi_pixel_clk;
    wire        S_hdmi_serial_clk;
    wire        S_hdmi_rst_n;
    wire        S_video_out_rst_n;


    wire        S_vi_128b_frame_start;
    wire        S_vi_128b_valid;      
    wire[127:0] S_vi_128b_data;    
    
    wire        S_video_out_rd_busy;
    wire        S_video_in_wr_busy; 
    wire[1:0]   S_video_out_rp;     

    wire        S_ddr_user_wr_en;       
    wire        S_ddr_user_rd_en;       
    wire[24:0]  S_ddr_user_addr;        
    wire[127:0] S_ddr_user_wr_data;     
    wire        S_ddr_user_ready;       
    wire        S_ddr_user_rd_valid;    
    wire[127:0] S_ddr_user_rd_data;     

    wire        S_vi_ddr_wr_en;   
    wire[24:0]  S_vi_ddr_wr_addr; 
    wire[127:0] S_vi_ddr_wr_data;
    wire        S_vi_ddr_wr_ready;

    wire        S_vo_ddr_rd_en;   
    wire[24:0]  S_vo_ddr_rd_addr; 
    wire        S_vo_ddr_rd_ready;
    wire        S_vo_dbg_fifo_rst;
    wire        S_vo_dbg_ddr_rd_valid;
    wire        S_vo_dbg_fifo_rd_en;
    wire        S_vo_dbg_fifo_empty;

    wire        S_init_calib_complete; 
    wire[24:0]  S_mc_app_addr;          
    wire[2:0]   S_mc_app_cmd;           
    wire        S_mc_app_en;            
    wire[127:0] S_mc_app_wdf_data;      
    wire        S_mc_app_wdf_end;       
    wire[15:0]  S_mc_app_wdf_mask;      
    wire        S_mc_app_wdf_wren;      
    wire[127:0] S_mc_app_rd_data;       
    wire        S_mc_app_rd_data_end;   
    wire        S_mc_app_rd_data_valid; 
    wire        S_mc_app_rdy;           
    wire        S_mc_app_wdf_rdy;       
    wire        S_mc_dbg_fifo_afull;
    wire        S_mc_dbg_app_rdy;
    wire        S_mc_dbg_wdf_rdy;
    wire        S_mc_dbg_cmd_pop;

    wire        S_hdmi_vsync;
    wire        S_hdmi_hsync;
    wire        S_hdmi_de;
    wire        S_hdmi_user;
    wire        S_hdmi_last;
    wire        S_video_out_vsync;
    wire        S_hdmi_window_rd_en;
    wire        S_hdmi_out_vsync;
    wire        S_hdmi_out_hsync;
    wire        S_hdmi_out_de;
    wire[23:0]  S_hdmi_out_data;

    wire[23:0]  S_video_rd_data;
    reg         S_dbg_raw_seen;
    reg         S_dbg_isp_seen;
    reg         S_dbg_ddr_wr_seen;
    reg         S_dbg_ddr_rd_seen;
    reg         S_dbg_cam_cfg_seen;
    reg         S_dbg_hs_seen;
    reg         S_dbg_csi_seen;
    reg         S_dbg_raw10_seen;
    reg         S_dbg_isp_fs_seen;
    reg         S_dbg_isp_valid_seen;
    reg         S_dbg_ddr_req_seen;
    reg         S_dbg_ddr_ready_seen;
    reg [1:0]   S_dbg_raw_seen_sync;
    reg [1:0]   S_dbg_isp_seen_sync;
    reg [1:0]   S_dbg_ddr_wr_seen_sync;
    reg [1:0]   S_dbg_ddr_rd_seen_sync;
    reg [1:0]   S_dbg_cam_cfg_seen_sync;
    reg [1:0]   S_dbg_hs_seen_sync;
    reg [1:0]   S_dbg_csi_seen_sync;
    reg [1:0]   S_dbg_raw10_seen_sync;
    reg [1:0]   S_dbg_isp_fs_seen_sync;
    reg [1:0]   S_dbg_isp_valid_seen_sync;
    reg [1:0]   S_dbg_ddr_req_seen_sync;
    reg [1:0]   S_dbg_ddr_ready_seen_sync;
    reg         S_dbg_video_nonzero_seen;
    reg         S_dbg_rd_req_seen;
    reg         S_dbg_rd_valid_seen;
    reg         S_dbg_rd_nonzero_seen;
    reg [1:0]   S_dbg_rd_req_seen_sync;
    reg [1:0]   S_dbg_rd_valid_seen_sync;
    reg [1:0]   S_dbg_rd_nonzero_seen_sync;
    reg         S_dbg_mc_init_seen;
    reg         S_dbg_mc_app_rdy_seen;
    reg         S_dbg_mc_wdf_rdy_seen;
    reg         S_dbg_mc_cmd_pop_seen;
    reg [1:0]   S_dbg_mc_init_seen_sync;
    reg [1:0]   S_dbg_mc_app_rdy_seen_sync;
    reg [1:0]   S_dbg_mc_wdf_rdy_seen_sync;
    reg [1:0]   S_dbg_mc_cmd_pop_seen_sync;
    // 720p input-format diagnostics.  One RAW10 line from the factory
    // 1280-pixel mode contains 1600 bytes, i.e. 400 valid 32-bit CSI words.
    reg         S_dbg_hs_valid_d;
    reg [10:0]  S_dbg_csi_words;
    reg [10:0]  S_dbg_good_lines;
    reg         S_dbg_frame_seen_once;
    reg         S_dbg_frame_repeat_seen;
    reg         S_dbg_width_1280_seen;
    reg         S_dbg_height_720_seen;
    reg         S_dbg_isp_frame_seen_once;
    reg         S_dbg_isp_frame_repeat_seen;
    reg [1:0]   S_dbg_frame_repeat_sync;
    reg [1:0]   S_dbg_width_1280_sync;
    reg [1:0]   S_dbg_height_720_sync;
    reg [1:0]   S_dbg_isp_frame_repeat_sync;
    wire[3:0]   S_hdmi_debug_status;
    wire        S_lane_error_any;

    assign S_video_out_vsync = ~S_hdmi_vsync;
	
	
    assign S_rst_n 		= S_pll_lock;
    assign S_hdmi_rst_n = S_pll_lock;

    always @(posedge S_csi_rx_clk or negedge S_rst_n) begin
        if(!S_rst_n)
            S_dbg_raw_seen <= 1'b0;
        else if(S_raw10_frame_start | S_axis_tvalid)
            S_dbg_raw_seen <= 1'b1;
    end

    always @(posedge S_csi_rx_clk or negedge S_rst_n) begin
        if(!S_rst_n)
            S_dbg_isp_seen <= 1'b0;
        else if(S_ISP_O_tuser | S_ISP_O_tvalid)
            S_dbg_isp_seen <= 1'b1;
    end

    always @(posedge S_ddr_clk or negedge S_rst_n) begin
        if(!S_rst_n)
            S_dbg_ddr_wr_seen <= 1'b0;
        else if(S_vi_ddr_wr_en)
            S_dbg_ddr_wr_seen <= 1'b1;
    end

    always @(posedge S_ddr_clk or negedge S_rst_n) begin
        if(!S_rst_n)
            S_dbg_ddr_rd_seen <= 1'b0;
        else if(S_ddr_user_rd_valid)
            S_dbg_ddr_rd_seen <= 1'b1;
    end

    always @(posedge S_24m_clk or negedge S_rst_n) begin
        if(!S_rst_n)
            S_dbg_cam_cfg_seen <= 1'b0;
        else if(S_cam_cfg_done)
            S_dbg_cam_cfg_seen <= 1'b1;
    end

    always @(posedge S_csi_rx_clk or negedge S_rst_n) begin
        if(!S_rst_n)
            S_dbg_hs_seen <= 1'b0;
        else if(S_hs_rx_valid)
            S_dbg_hs_seen <= 1'b1;
    end

    always @(posedge S_csi_rx_clk or negedge S_rst_n) begin
        if(!S_rst_n)
            S_dbg_csi_seen <= 1'b0;
        else if(S_csi_frame_start | S_csi_valid)
            S_dbg_csi_seen <= 1'b1;
    end

    always @(posedge S_csi_rx_clk or negedge S_rst_n) begin
        if(!S_rst_n)
            S_dbg_raw10_seen <= 1'b0;
        else if(S_raw10_frame_start | S_raw10_valid)
            S_dbg_raw10_seen <= 1'b1;
    end

    always @(posedge S_csi_rx_clk or negedge S_rst_n) begin
        if(!S_rst_n)
            S_dbg_isp_fs_seen <= 1'b0;
        else if(S_ISP_O_tuser)
            S_dbg_isp_fs_seen <= 1'b1;
    end

    always @(posedge S_csi_rx_clk or negedge S_rst_n) begin
        if(!S_rst_n)
            S_dbg_isp_valid_seen <= 1'b0;
        else if(S_ISP_O_tvalid)
            S_dbg_isp_valid_seen <= 1'b1;
    end

    always @(posedge S_ddr_clk or negedge S_rst_n) begin
        if(!S_rst_n)
            S_dbg_ddr_req_seen <= 1'b0;
        else if(S_vi_ddr_wr_en)
            S_dbg_ddr_req_seen <= 1'b1;
    end

    always @(posedge S_ddr_clk or negedge S_rst_n) begin
        if(!S_rst_n)
            S_dbg_ddr_ready_seen <= 1'b0;
        else if(S_ddr_user_ready)
            S_dbg_ddr_ready_seen <= 1'b1;
    end

    always @(posedge S_ddr_clk or negedge S_video_out_rst_n) begin
        if(!S_video_out_rst_n)
            S_dbg_rd_req_seen <= 1'b0;
        else if(S_vo_ddr_rd_en)
            S_dbg_rd_req_seen <= 1'b1;
    end

    // Count CSI payload words between HS packet boundaries.  This avoids
    // probing an internal net of csi_unpacket_2lane (which ChipWatcher cannot
    // legally connect to) and verifies the received line length externally.
    always @(posedge S_csi_rx_clk or negedge S_rst_n) begin
        if(!S_rst_n) begin
            S_dbg_hs_valid_d          <= 1'b0;
            S_dbg_csi_words           <= 11'd0;
            S_dbg_good_lines          <= 11'd0;
            S_dbg_frame_seen_once     <= 1'b0;
            S_dbg_frame_repeat_seen   <= 1'b0;
            S_dbg_width_1280_seen     <= 1'b0;
            S_dbg_height_720_seen     <= 1'b0;
            S_dbg_isp_frame_seen_once <= 1'b0;
            S_dbg_isp_frame_repeat_seen <= 1'b0;
        end
        else begin
            S_dbg_hs_valid_d <= S_hs_rx_valid;

            if(!S_dbg_hs_valid_d && S_hs_rx_valid)
                S_dbg_csi_words <= 11'd0;
            else if(S_csi_valid)
                S_dbg_csi_words <= S_dbg_csi_words + 11'd1;

            // A packet with CSI payload is an image line.  Ignore short
            // frame-start/frame-end packets, whose payload count is zero.
            if(S_dbg_hs_valid_d && !S_hs_rx_valid && (S_dbg_csi_words != 0)) begin
                if(S_dbg_csi_words == 11'd400) begin
                    S_dbg_width_1280_seen <= 1'b1;
                    S_dbg_good_lines <= S_dbg_good_lines + 11'd1;
                end
            end

            if(S_csi_frame_start) begin
                if(S_dbg_frame_seen_once) begin
                    S_dbg_frame_repeat_seen <= 1'b1;
                    if(S_dbg_good_lines == 11'd720)
                        S_dbg_height_720_seen <= 1'b1;
                end
                else
                    S_dbg_frame_seen_once <= 1'b1;
                S_dbg_good_lines <= 11'd0;
            end

            if(S_ISP_O_tuser) begin
                if(S_dbg_isp_frame_seen_once)
                    S_dbg_isp_frame_repeat_seen <= 1'b1;
                else
                    S_dbg_isp_frame_seen_once <= 1'b1;
            end
        end
    end

    always @(posedge S_ddr_clk or negedge S_video_out_rst_n) begin
        if(!S_video_out_rst_n)
            S_dbg_rd_valid_seen <= 1'b0;
        else if(S_ddr_user_rd_valid)
            S_dbg_rd_valid_seen <= 1'b1;
    end

    always @(posedge S_hdmi_pixel_clk or negedge S_video_out_rst_n) begin
        if(!S_video_out_rst_n)
            S_dbg_rd_nonzero_seen <= 1'b0;
        else if(S_hdmi_window_rd_en && (S_video_rd_data != 24'd0))
            S_dbg_rd_nonzero_seen <= 1'b1;
    end

    always @(posedge S_ddr_clk or negedge S_rst_n) begin
        if(!S_rst_n)
            S_dbg_mc_init_seen <= 1'b0;
        else if(S_init_calib_complete)
            S_dbg_mc_init_seen <= 1'b1;
    end

    always @(posedge S_ddr_clk or negedge S_rst_n) begin
        if(!S_rst_n)
            S_dbg_mc_app_rdy_seen <= 1'b0;
        else if(S_mc_dbg_app_rdy)
            S_dbg_mc_app_rdy_seen <= 1'b1;
    end

    always @(posedge S_ddr_clk or negedge S_rst_n) begin
        if(!S_rst_n)
            S_dbg_mc_wdf_rdy_seen <= 1'b0;
        else if(S_mc_dbg_wdf_rdy)
            S_dbg_mc_wdf_rdy_seen <= 1'b1;
    end

    always @(posedge S_ddr_clk or negedge S_rst_n) begin
        if(!S_rst_n)
            S_dbg_mc_cmd_pop_seen <= 1'b0;
        else if(S_mc_dbg_cmd_pop)
            S_dbg_mc_cmd_pop_seen <= 1'b1;
    end

    always @(posedge S_hdmi_pixel_clk or negedge S_hdmi_rst_n) begin
        if(!S_hdmi_rst_n) begin
            S_dbg_cam_cfg_seen_sync <= 2'b00;
            S_dbg_hs_seen_sync      <= 2'b00;
            S_dbg_csi_seen_sync     <= 2'b00;
            S_dbg_raw10_seen_sync   <= 2'b00;
            S_dbg_raw_seen_sync    <= 2'b00;
            S_dbg_isp_seen_sync    <= 2'b00;
            S_dbg_ddr_wr_seen_sync <= 2'b00;
            S_dbg_ddr_rd_seen_sync <= 2'b00;
            S_dbg_isp_fs_seen_sync  <= 2'b00;
            S_dbg_isp_valid_seen_sync <= 2'b00;
            S_dbg_ddr_req_seen_sync <= 2'b00;
            S_dbg_ddr_ready_seen_sync <= 2'b00;
            S_dbg_video_nonzero_seen <= 1'b0;
            S_dbg_rd_req_seen_sync <= 2'b00;
            S_dbg_rd_valid_seen_sync <= 2'b00;
            S_dbg_rd_nonzero_seen_sync <= 2'b00;
            S_dbg_mc_init_seen_sync <= 2'b00;
            S_dbg_mc_app_rdy_seen_sync <= 2'b00;
            S_dbg_mc_wdf_rdy_seen_sync <= 2'b00;
            S_dbg_mc_cmd_pop_seen_sync <= 2'b00;
            S_dbg_frame_repeat_sync <= 2'b00;
            S_dbg_width_1280_sync <= 2'b00;
            S_dbg_height_720_sync <= 2'b00;
            S_dbg_isp_frame_repeat_sync <= 2'b00;
        end
        else begin
            S_dbg_cam_cfg_seen_sync <= {S_dbg_cam_cfg_seen_sync[0], S_dbg_cam_cfg_seen};
            S_dbg_hs_seen_sync      <= {S_dbg_hs_seen_sync[0],      S_dbg_hs_seen};
            S_dbg_csi_seen_sync     <= {S_dbg_csi_seen_sync[0],     S_dbg_csi_seen};
            S_dbg_raw10_seen_sync   <= {S_dbg_raw10_seen_sync[0],   S_dbg_raw10_seen};
            S_dbg_raw_seen_sync    <= {S_dbg_raw_seen_sync[0],    S_dbg_raw_seen};
            S_dbg_isp_seen_sync    <= {S_dbg_isp_seen_sync[0],    S_dbg_isp_seen};
            S_dbg_ddr_wr_seen_sync <= {S_dbg_ddr_wr_seen_sync[0], S_dbg_ddr_wr_seen};
            S_dbg_ddr_rd_seen_sync <= {S_dbg_ddr_rd_seen_sync[0], S_dbg_ddr_rd_seen};
            S_dbg_isp_fs_seen_sync  <= {S_dbg_isp_fs_seen_sync[0],  S_dbg_isp_fs_seen};
            S_dbg_isp_valid_seen_sync <= {S_dbg_isp_valid_seen_sync[0], S_dbg_isp_valid_seen};
            S_dbg_ddr_req_seen_sync <= {S_dbg_ddr_req_seen_sync[0], S_dbg_ddr_req_seen};
            S_dbg_ddr_ready_seen_sync <= {S_dbg_ddr_ready_seen_sync[0], S_dbg_ddr_ready_seen};
            S_dbg_rd_req_seen_sync <= {S_dbg_rd_req_seen_sync[0], S_dbg_rd_req_seen};
            S_dbg_rd_valid_seen_sync <= {S_dbg_rd_valid_seen_sync[0], S_dbg_rd_valid_seen};
            S_dbg_rd_nonzero_seen_sync <= {S_dbg_rd_nonzero_seen_sync[0], S_dbg_rd_nonzero_seen};
            S_dbg_mc_init_seen_sync <= {S_dbg_mc_init_seen_sync[0], S_dbg_mc_init_seen};
            S_dbg_mc_app_rdy_seen_sync <= {S_dbg_mc_app_rdy_seen_sync[0], S_dbg_mc_app_rdy_seen};
            S_dbg_mc_wdf_rdy_seen_sync <= {S_dbg_mc_wdf_rdy_seen_sync[0], S_dbg_mc_wdf_rdy_seen};
            S_dbg_mc_cmd_pop_seen_sync <= {S_dbg_mc_cmd_pop_seen_sync[0], S_dbg_mc_cmd_pop_seen};
            S_dbg_frame_repeat_sync <= {S_dbg_frame_repeat_sync[0], S_dbg_frame_repeat_seen};
            S_dbg_width_1280_sync <= {S_dbg_width_1280_sync[0], S_dbg_width_1280_seen};
            S_dbg_height_720_sync <= {S_dbg_height_720_sync[0], S_dbg_height_720_seen};
            S_dbg_isp_frame_repeat_sync <= {S_dbg_isp_frame_repeat_sync[0], S_dbg_isp_frame_repeat_seen};
            if(S_hdmi_window_rd_en && (S_video_rd_data != 24'd0))
                S_dbg_video_nonzero_seen <= 1'b1;
        end
    end

    assign S_lane_error_any = |S_lane_error;

    assign S_vo_dbg_fifo_rst = 1'b0;
    assign S_vo_dbg_ddr_rd_valid = 1'b0;
    assign S_vo_dbg_fifo_rd_en = 1'b0;
    assign S_vo_dbg_fifo_empty = 1'b0;
    assign S_mc_dbg_fifo_afull = 1'b0;
    assign S_mc_dbg_app_rdy = 1'b0;
    assign S_mc_dbg_wdf_rdy = 1'b0;
    assign S_mc_dbg_cmd_pop = 1'b0;

    // On-screen bring-up status, from left to right in DEBUG_MODE=3:
    // I2C configuration completed, MIPI HS activity seen, repeated CSI frames,
    // and a 1280-pixel RAW10 line (400 x 32-bit CSI payload words) seen.
    assign S_hdmi_debug_status = {
        S_dbg_width_1280_sync[1],
        S_dbg_frame_repeat_sync[1],
        S_dbg_hs_seen_sync[1],
        S_dbg_cam_cfg_seen_sync[1]
    };
	
	assign O_cam_rst 	= 1'b1;
    assign O_cam_24m 	= S_24m_clk;
	
	
	
	

    wire fusion_reset_n,wb_toggle,wb_locked;
    wire [7:0] controls_50,controls_camera,controls_hdmi;
    wire [11:0] style_levels_50,style_levels_camera,style_levels_hdmi;
    wire osd_enable_50,osd_enable_hdmi;
    wire [5:0] color_control_50,color_control_hdmi;
    wire [12:0] color_gain_r,color_gain_b;
    wire [1:0] fusion_mode=controls_camera[7:5]==1 ? controls_camera[4:3]:2'd0;
    fusion_controls u_controls(.I_clk(I_sys_clk),.I_keys_n({I_key_mode,I_rst_n,I_button}),
        .I_switches(I_switches),.O_system_rst_n(fusion_reset_n),.O_control(controls_50),
        .O_osd_enable(osd_enable_50),.O_wb_toggle(wb_toggle),.O_color_control(color_control_50),
        .O_style_levels(style_levels_50));
    fusion_control_cdc #(.WIDTH(20)) u_control_camera(.I_source_clk(I_sys_clk),.I_dest_clk(S_csi_rx_clk),
        .I_rst_n(S_rst_n),.I_commit(S_raw_tuser),
        .I_data({style_levels_50,controls_50}),.O_data({style_levels_camera,controls_camera}));
    fusion_control_cdc #(.WIDTH(27)) u_control_hdmi(.I_source_clk(I_sys_clk),.I_dest_clk(S_hdmi_pixel_clk),
        .I_rst_n(S_hdmi_rst_n),.I_commit(S_hdmi_user),
        .I_data({style_levels_50,color_control_50,osd_enable_50,controls_50}),
        .O_data({style_levels_hdmi,color_control_hdmi,osd_enable_hdmi,controls_hdmi}));
    (* ASYNC_REG="TRUE" *) reg [2:0] wb_toggle_sync;
    wire wb_relearn_pulse=wb_toggle_sync[2]!=wb_toggle_sync[1];
    always @(posedge S_csi_rx_clk or negedge S_rst_n) begin
        if(!S_rst_n)wb_toggle_sync<=0;
        else wb_toggle_sync<={wb_toggle_sync[1:0],wb_toggle};
    end

    PLL u_PLL(
        .refclk      ( I_sys_clk         ),
        .reset    	 ( ~fusion_reset_n  ),
        
        .clk0_out    ( S_100m_clk        ),
        .clk1_out    ( S_24m_clk         ),

        .clk4_out    ( S_hdmi_pixel_clk  ),
        .clk5_out    ( S_hdmi_serial_clk ),

        .lock        ( S_pll_lock        )

    );


	

  
  wire [95:0] meter_rgb;
  wire meter_valid,meter_sof,stats_valid;
  wire [31:0] stats_sum;
  wire [19:0] stats_count,stats_hot;
  wire wb_allow,wb_relearn;
  ae_stats_cdc u_meter (
    .src_clk(S_csi_rx_clk),.dst_clk(S_24m_clk),.rst_n(S_rst_n),
    .rgb(meter_rgb),.valid(meter_valid),.sof(meter_sof),
    .stats_valid(stats_valid),.stats_sum(stats_sum),
    .stats_count(stats_count),.stats_hot(stats_hot));
  ae_auto_control u_ae_set (
    .clk(S_24m_clk),.rst_n(S_rst_n),.cam_done(S_cam_cfg_done),.ae_done(S_ae_cfg_done),
    .stats_valid(stats_valid),.stats_sum(stats_sum),.stats_count(stats_count),.stats_hot(stats_hot),
    .buttons_n(2'b11),.request(S_ae_req),.exposure(S_ae),.gain_index(S_ag),
    .wb_allow(wb_allow),.wb_relearn(wb_relearn));

    uicfgcs500_720p #(
      .CLK_DIV(24000000 / 100000 - 1)
  ) u_uicfgcs500 (
      .I_clk(S_24m_clk),  //系统时钟输入
      .I_rst_n(S_rst_n),  //系统复位输入
      .I_ae_req(S_ae_req),
      .I_ae(S_ae),
      .I_ag(S_ag),
      .O_cam_scl(O_cam_scl),  //I2C总线，SCL时钟
      .IO_cam_sda(IO_cam_sda),  //I2C总线，SDA数据
      .O_cfg_done(S_cam_cfg_done),  //摄像头寄存器初始化完成
      .O_ae_cfg_done(S_ae_cfg_done)  //AE配置完成
  );
	
    mipi_dphy_rx_ph1p_mipiio_wrapper#(
        .DPHY_RX_LOCATION      ( "DPHY0" ),
        .HS_EQUALIZER          ( "0dB"   ),//"0dB","1.5dB","3dB","4.5dB","6dB","7.5dB","9dB","10.5dB"
        .HS_VGA_GAIN           ( "8dB" ),//"-3dB","-1.5dB","0dB","1.5dB","3dB","4.5dB","6dB","7.5dB"
        .LANE_NUM              ( 2       ),
        .BYTE_NUM              ( 1       )
    )u_mipi_dphy_rx_ph1p_mipiio_wrapper(
        .I_lp_clk              ( S_100m_clk       ),
        .I_rst                 ( ~S_rst_n         ),

        .I_clk_lane_in_delay   ( 6'd0             ),
        .I_data_lane0_in_delay ( 6'd0             ),
        .I_data_lane1_in_delay ( 6'd0             ),
        .I_data_lane2_in_delay ( 6'd0             ),
        .I_data_lane3_in_delay ( 6'd0             ),

        .I_lane_invert         ( 4'b0000          ),
     
        .O_hs_rx_clk           ( S_csi_rx_clk     ),
        .O_hs_rx_valid         ( S_hs_rx_valid    ),
        .O_hs_rx_data          ( S_hs_rx_data     ),
      
        .O_lp_rx_lane0_p       (  ),
        .O_lp_rx_lane0_n       (  ),
      
        .I_lp_tx_en            ( 1'b0             ),
        .I_lp_tx_lane0_p       ( 1'b1             ),
        .I_lp_tx_lane0_n       ( 1'b1             ),
      
        .O_lane_match_error    (                  ),
        .O_lane_error          ( S_lane_error     ),
      
        .IO_rx_clk_pad_n       ( IO_rx_clk_pad_n  ),
        .IO_rx_clk_pad_p       ( IO_rx_clk_pad_p  ),
        .IO_rx_data_pad_n      ( IO_rx_data_pad_n ),
        .IO_rx_data_pad_p      ( IO_rx_data_pad_p )
    );
	
	
 //  cwc cwc_inst
 //(
 //    .probe0(S_hs_rx_valid),
 //    .probe1(S_hs_rx_data),
 //    .probe2(S_lane_error),
 //    .clk(S_csi_rx_clk)
 //);

 //csi 解码为RAW数据
csi_unpacket_2lane u_csi_unpacket(
.I_clk                 ( S_csi_rx_clk       ),
.I_rst_n               ( S_rst_n        	),
.I_hs_valid            ( S_hs_rx_valid     ),
.I_hs_data             ( S_hs_rx_data      ),

.O_csi_frame_start     ( S_csi_frame_start ),
.O_csi_frame_end       ( S_csi_frame_end   ),
.O_csi_valid           ( S_csi_valid       ),
.O_csi_data            ( S_csi_data        )
);


//解码为RAW8
raw10_unpacket_2lane u_raw10_unpacket (
.I_camera_black_level(10'd0),
.I_clk  (S_csi_rx_clk),
.I_rst_n(S_rst_n),

.I_csi_frame_start(S_csi_frame_start),
.I_csi_frame_end  (S_csi_frame_end),
.I_csi_valid      (S_csi_valid),
.I_csi_data       (S_csi_data),

.O_raw10_frame_start(S_raw10_frame_start),
.O_raw10_frame_end  (S_raw10_frame_end),
.O_raw10_valid      (S_raw10_valid),
.O_raw10_data       (S_raw10_data)
  );


//将数据转为stream流
uial2axis #(
.IMG_WIDTH(1280),
.IMG_HEIGHT(720),
.INPUT_DATA_WIDTH(40)
) 
u_uial2axis (
.I_native_clk(S_csi_rx_clk),
.I_rst_n     (S_rst_n),
.I_data      (S_raw10_data       ),
.I_data_valid(S_raw10_valid      ),
.I_data_start(S_raw10_frame_start),
.I_data_end  (S_raw10_frame_end  ),
.axis_tvalid (S_axis_tvalid),
.axis_tdata  (S_axis_tdata ),
.axis_tuser  (S_axis_tuser ),
.axis_tlast  (S_axis_tlast )
);
	

// SC500 factory HD mode already outputs native 1280x720 RAW10.
assign S_raw_tdata  = S_axis_tdata;
assign S_raw_tvalid = S_axis_tvalid;
assign S_raw_tlast  = S_axis_tlast;
assign S_raw_tuser  = S_axis_tuser;


//cwc1 cwc1_Inst
//  (
//      .probe0(S_axis_tuser),
//      .probe1(S_axis_tvalid),
//      .probe2(S_axis_tlast),
//      .probe3(S_axis_tdata),
//      .probe4(S_ISP_O_tuser),
//      .probe5(S_ISP_O_tvalid),
//      .probe6(S_ISP_O_tlast),
//      .probe7(S_ISP_O_tdata),
//      .probe8 (S_raw_tdata ),
//      .probe9 (S_raw_tlast ),
//      .probe10(S_raw_tvalid),
//      .probe11(S_raw_tuser ),
//      .clk(S_csi_rx_clk)
//  );


//ISP算法顶层模块
isp_top u_isp_top (
.I_wb_allow(wb_allow),.I_wb_relearn(wb_relearn | wb_relearn_pulse),.I_mode_req(fusion_mode),.I_style_levels(style_levels_camera),.O_wb_locked(wb_locked),
.O_color_gain_r(color_gain_r),.O_color_gain_b(color_gain_b),
.O_meter_data(meter_rgb),.O_meter_valid(meter_valid),.O_meter_sof(meter_sof),
.axi4s_video_aclk(S_csi_rx_clk),
.I_rst_n         (S_rst_n),
.I_tlast         (S_raw_tlast	),
.I_tuser         (S_raw_tuser	),
.I_tdata         (S_raw_tdata	),
.I_tvalid        (S_raw_tvalid	),
.I_tdest         (),
.O_tready        (S_ISP_O_tready),
.O_tdata         (S_ISP_O_tdata ),
.O_tlast         (S_ISP_O_tlast ),
.O_tuser         (S_ISP_O_tuser ),
.O_tvalid        (S_ISP_O_tvalid),
.I_tready        ()
  );


    wire latency_write_start,latency_read_start,latency_input_overflow;
    wire latency_read_fifo_reset,latency_output_underflow;
    wire [1:0] latency_write_slot,latency_read_slot;
    video_in u_video_in(
        .I_rst_n              (  S_rst_n             ),

        .I_camera_clk         ( S_csi_rx_clk          ),
        .I_camera_frame_start ( S_ISP_O_tuser  ),
        .I_camera_valid       ( S_ISP_O_tvalid ),
        .I_camera_data        ( S_ISP_O_tdata  ),
        .I_mipi_rx_error      ( 1'b0			      ),

        .I_ddr_clk            ( S_ddr_clk             ),
		.I_display_pause      ( 1'b0                  ),
        .I_video_out_rd_busy  ( S_video_out_rd_busy   ),
        .O_video_in_wr_busy   ( S_video_in_wr_busy    ),
        .O_video_out_rp       ( S_video_out_rp        ),

        .O_ddr_user_wr_en     ( S_vi_ddr_wr_en        ),
        .O_ddr_user_addr      ( S_vi_ddr_wr_addr      ),
        .O_ddr_user_wr_data   ( S_vi_ddr_wr_data      ),
        .I_ddr_user_ready     ( S_ddr_user_ready      ),
        .O_observe_frame_start(latency_write_start),.O_observe_write_slot(latency_write_slot),
        .O_observe_overflow(latency_input_overflow)
    );



    assign S_ddr_user_wr_en    = S_vi_ddr_wr_en;

    assign S_ddr_user_rd_en    = S_vo_ddr_rd_en;

    assign S_ddr_user_addr     = S_vi_ddr_wr_en ? S_vi_ddr_wr_addr :
                                 S_vo_ddr_rd_en ? S_vo_ddr_rd_addr : 'd0;

    assign S_ddr_user_wr_data  = S_vi_ddr_wr_data;


    assign S_video_out_rst_n = S_hdmi_rst_n;

    video_out u_video_out(
        .I_rst_n             ( S_video_out_rst_n    ),
        .I_ddr_clk           ( S_ddr_clk            ),
 
        .O_video_out_rd_busy ( S_video_out_rd_busy  ),
        .I_video_in_wr_busy  ( S_video_in_wr_busy   ),
        .I_video_out_rp      ( S_video_out_rp       ),
 
        .O_ddr_user_rd_en    ( S_vo_ddr_rd_en       ),
        .O_ddr_user_addr     ( S_vo_ddr_rd_addr     ),
        .I_ddr_user_ready    ( S_ddr_user_ready     ),
        .I_ddr_user_rd_valid ( S_ddr_user_rd_valid  ),
        .I_ddr_user_rd_data  ( S_ddr_user_rd_data   ),

        .I_dsi_clk           ( S_hdmi_pixel_clk     ),
        .I_video_vsync       ( S_video_out_vsync    ),
        .I_video_rd_en       ( S_hdmi_window_rd_en  ),
        .O_vdieo_data        ( S_video_rd_data      ),
        .O_observe_read_start(latency_read_start),.O_observe_read_slot(latency_read_slot),
        .O_observe_fifo_reset(latency_read_fifo_reset),.O_observe_underflow(latency_output_underflow)
    );



    mc_to_user_interface u_mc_to_user_interface(
        .I_clk                   ( S_ddr_clk               ),
        .I_rst_n                 ( S_rst_n                 ),

        .I_ddr_user_wr_en        ( S_ddr_user_wr_en        ),
        .I_ddr_user_rd_en        ( S_ddr_user_rd_en        ),
        .I_ddr_user_addr         ( S_ddr_user_addr         ),
        .I_ddr_user_wr_data      ( S_ddr_user_wr_data      ),
        .O_ddr_user_ready        ( S_ddr_user_ready        ),
        .O_ddr_user_rd_valid     ( S_ddr_user_rd_valid     ),
        .O_ddr_user_rd_data      ( S_ddr_user_rd_data      ),
            
        .O_mc_app_en             ( S_mc_app_en             ),
        .O_mc_app_addr           ( S_mc_app_addr           ),
        .O_mc_app_cmd            ( S_mc_app_cmd            ),
        .I_mc_app_rdy            ( S_mc_app_rdy            ),
        .O_mc_app_wdf_wren       ( S_mc_app_wdf_wren       ),
        .O_mc_app_wdf_data       ( S_mc_app_wdf_data       ),
        .O_mc_app_wdf_end        ( S_mc_app_wdf_end        ),
        .O_mc_app_wdf_mask       ( S_mc_app_wdf_mask       ),
        .I_mc_app_wdf_rdy        ( S_mc_app_wdf_rdy        ),
        .I_mc_app_rd_data        ( S_mc_app_rd_data        ),
        .I_mc_app_rd_data_end    ( S_mc_app_rd_data_end    ),
        .I_mc_app_rd_data_valid  ( S_mc_app_rd_data_valid  )
    );



    ph1p35_324_ddr_wrapper u_ph1p35_324_ddr_wrapper(
        .I_sys_clk              ( I_sys_clk              ),
        .I_sys_rst_n            ( S_rst_n                ),

        .O_ddr_clk              ( S_ddr_clk              ),
        .O_init_calib_complete  ( S_init_calib_complete  ),
        .I_mc_app_addr          ( S_mc_app_addr          ),
        .I_mc_app_cmd           ( S_mc_app_cmd           ),
        .I_mc_app_en            ( S_mc_app_en            ),
        .I_mc_app_wdf_data      ( S_mc_app_wdf_data      ),
        .I_mc_app_wdf_end       ( S_mc_app_wdf_end       ),
        .I_mc_app_wdf_mask      ( S_mc_app_wdf_mask      ),
        .I_mc_app_wdf_wren      ( S_mc_app_wdf_wren      ),
        .O_mc_app_rd_data       ( S_mc_app_rd_data       ),
        .O_mc_app_rd_data_end   ( S_mc_app_rd_data_end   ),
        .O_mc_app_rd_data_valid ( S_mc_app_rd_data_valid ),
        .O_mc_app_rdy           ( S_mc_app_rdy           ),
        .O_mc_app_wdf_rdy       ( S_mc_app_wdf_rdy       ),

        .ddr_addr               ( ddr_addr               ),
        .ddr_ba                 ( ddr_ba                 ),
        .ddr_cke                ( ddr_cke                ),
        .ddr_odt                ( ddr_odt                ),
        .ddr_cs_n               ( ddr_cs_n               ),
        .ddr_ras_n              ( ddr_ras_n              ),
        .ddr_cas_n              ( ddr_cas_n              ),
        .ddr_we_n               ( ddr_we_n               ),
        .ddr_ck_p               ( ddr_ck_p               ),
        .ddr_ck_n               ( ddr_ck_n               ),
        .ddr_dm                 ( ddr_dm                 ),
        .ddr_dq                 ( ddr_dq                 ),
        .ddr_dqs_p              ( ddr_dqs_p              ),
        .ddr_dqs_n              ( ddr_dqs_n              )
    );



    uivtc #(
        .H_ActiveSize ( 1280 ),
        .H_FrameSize  ( 1650 ),
        .H_SyncStart  ( 1390 ),
        .H_SyncEnd    ( 1430 ),
        .V_ActiveSize ( 720  ),
        .V_FrameSize  ( 750  ),
        .V_SyncStart  ( 725  ),
        .V_SyncEnd    ( 730  )
    )u_hdmi_vtc(
        .I_vtc_rstn    ( S_hdmi_rst_n    ),
        .I_vtc_clk     ( S_hdmi_pixel_clk ),
        .O_vtc_vs      ( S_hdmi_vsync     ),
        .O_vtc_hs      ( S_hdmi_hsync     ),
        .O_vtc_de_valid( S_hdmi_de        ),
        .O_vtc_user    ( S_hdmi_user      ),
        .O_vtc_last    ( S_hdmi_last      )
    );

    wire [11:0] hud_x,hud_y;
    wire hud_hit,mix_overlay,mix_vs,mix_hs,mix_de;
    wire [23:0] hud_color,mix_clean,mix_rgb;
    wire alarm,target,source_ok,video_lost,armed;
    wire [31:0] candidate_pixels;
    wire [11:0] target_x,target_y;
    wire [32:0] isp_status;
    fusion_control_cdc #(.WIDTH(33)) u_isp_status(.I_source_clk(S_24m_clk),.I_dest_clk(S_hdmi_pixel_clk),
        .I_rst_n(S_rst_n),.I_commit(S_hdmi_user),.I_data({wb_allow,S_ag,S_ae}),.O_data(isp_status));
    (* ASYNC_REG="TRUE" *) reg [1:0] cfg_h,ddr_h,wb_h;
    always @(posedge S_hdmi_pixel_clk or negedge S_hdmi_rst_n) begin
        if(!S_hdmi_rst_n)begin cfg_h<=0;ddr_h<=0;wb_h<=0;end
        else begin cfg_h<={cfg_h[0],S_cam_cfg_done};ddr_h<={ddr_h[0],S_init_calib_complete};wb_h<={wb_h[0],wb_locked};end
    end
    wire [31:0] latency_us;
    wire [15:0] latency_frame_id;
    wire [15:0] latency_debug_reason;
    wire latency_valid,latency_repeat,latency_skip;
    wire [7:0] latency_status;
    wire [19:0] latency_bcd;
    reg [31:0] latency_hud_us;
    reg [15:0] latency_hud_id,latency_hud_reason;
    reg [2:0] latency_hud_flags;
    reg [7:0] latency_hud_status;
    // Freeze one complete HUD tuple for the scan, including late/invalid
    // results. The shared BCD converter reads this snapshot later in the scan.
    always @(posedge S_hdmi_pixel_clk or negedge S_hdmi_rst_n)begin
        if(!S_hdmi_rst_n)begin latency_hud_us<=0;latency_hud_id<=0;latency_hud_reason<=0;latency_hud_flags<=0;latency_hud_status<=8'h80;end
        else if(S_hdmi_user)begin
            latency_hud_us<=latency_us;latency_hud_id<=latency_frame_id;
            latency_hud_reason<=latency_debug_reason;
            latency_hud_flags<={latency_valid,latency_repeat,latency_skip};
            latency_hud_status<=latency_status;
        end
    end
    frame_latency_monitor u_frame_latency(
        .sys_clk(I_sys_clk),.cam_clk(S_csi_rx_clk),.ddr_clk(S_ddr_clk),.hdmi_clk(S_hdmi_pixel_clk),
        .rst_n(S_rst_n && S_hdmi_rst_n),
        .raw_user(S_raw_tuser),.raw_valid(S_raw_tvalid),.raw_error(S_lane_error_any),
        .packed_user(S_ISP_O_tuser),.input_overflow(latency_input_overflow),
        .write_start(latency_write_start),.write_slot(latency_write_slot),
        .write_en(S_vi_ddr_wr_en),.write_address(S_vi_ddr_wr_addr),
        .read_start(latency_read_start),.read_slot(latency_read_slot),
        .read_en(S_vo_ddr_rd_en),.read_address(S_vo_ddr_rd_addr),
        .read_return(S_ddr_user_rd_valid),.read_fifo_reset(latency_read_fifo_reset),
        .raw_hdmi_vs(S_hdmi_vsync),.final_hdmi_vs(S_hdmi_out_vsync),
        .final_hdmi_de(S_hdmi_out_de),.output_underflow(latency_output_underflow),
        .O_latency_us(latency_us),.O_frame_id(latency_frame_id),
        .O_valid(latency_valid),.O_repeat(latency_repeat),.O_skip(latency_skip),.O_status(latency_status),.O_debug_reason(latency_debug_reason));
    wire [15:0] xb,yb;
    wire [23:0] pb;
    wire [19:0] seconds_bcd,exposure_bcd;
    wire [7:0] camera_fps_bcd,output_fps_bcd;
    wire [11:0] gain_bcd;
    fusion_telemetry u_telemetry(.I_clk(S_hdmi_pixel_clk),.I_rst_n(S_hdmi_rst_n),.I_frame(S_hdmi_user),
        .I_source_clk(S_csi_rx_clk),.I_source_frame(S_csi_frame_start),.I_x(target_x),.I_y(target_y),
        .I_pixels(candidate_pixels),.I_exposure(isp_status[15:0]),.I_gain(isp_status[31:16]),
        .I_latency_us(latency_hud_us),.O_latency_bcd(latency_bcd),
        .O_x_bcd(xb),.O_y_bcd(yb),.O_pixels_bcd(pb),.O_seconds_bcd(seconds_bcd),
        .O_exposure_bcd(exposure_bcd),.O_camera_fps_bcd(camera_fps_bcd),.O_output_fps_bcd(output_fps_bcd),.O_gain_bcd(gain_bcd));
    fusion_hud u_hud(.I_clk(S_hdmi_pixel_clk),.I_rst_n(S_hdmi_rst_n),.I_x(hud_x),.I_y(hud_y),
        .I_control(controls_hdmi),.I_style_levels(style_levels_hdmi),.I_x_bcd(xb),.I_y_bcd(yb),.I_pixels_bcd(pb),
        .I_seconds_bcd(seconds_bcd),.I_exposure_bcd(exposure_bcd),.I_camera_fps_bcd(camera_fps_bcd),
        .I_output_fps_bcd(output_fps_bcd),.I_gain_bcd(gain_bcd),
        .I_latency_bcd(latency_bcd),
        .I_latency_frame_id((controls_hdmi[7:5]==3'd3 && controls_hdmi[4:3]==2'd2) ? latency_hud_reason : latency_hud_id),
        .I_latency_valid(latency_hud_flags[2]),.I_latency_repeat(latency_hud_flags[1]),.I_latency_skip(latency_hud_flags[0]),
        .I_latency_status(latency_hud_status),
        .I_target(target),.I_alarm(alarm),
        .I_audio(controls_hdmi[7:5]==2 && controls_hdmi[4:3]==2 && !controls_hdmi[2] && source_ok && armed),
        .I_cam_cfg(cfg_h[1]),.I_ddr_ready(ddr_h[1]),.I_source_ok(source_ok),.I_wb_locked(wb_h[1]),
        .I_armed(armed),.I_debug(S_hdmi_debug_status),.I_color_control(color_control_hdmi),
        .I_aid_h_zone(target_x<427?2'd0:target_x<854?2'd1:2'd2),
        .I_aid_v_zone(target_y<240?2'd0:target_y<480?2'd1:2'd2),
        .O_hit(hud_hit),.O_color(hud_color));
    wire [25:0] color_gains_hdmi;
    fusion_control_cdc #(.WIDTH(26)) u_color_gains(.I_source_clk(S_csi_rx_clk),.I_dest_clk(S_hdmi_pixel_clk),
        .I_rst_n(S_hdmi_rst_n),.I_commit(S_hdmi_user),.I_data({color_gain_r,color_gain_b}),.O_data(color_gains_hdmi));
    wire color_vs,color_hs,color_de;
    wire [23:0] color_clean,auto_clean;
    reg [23:0] composite_c0,composite_c1,composite_c2;
    reg [2:0] overlay_c;
    // Colour follows the mixer, so DDR read-request timing and the Logo/HUD
    // coordinates are untouched. Delay the unmodified overlay by the same 3 clocks.
    color_luma_preserve u_color_pixels(.clk(S_hdmi_pixel_clk),.rst_n(S_hdmi_rst_n),
        .vs(mix_vs),.hs(mix_hs),.de(mix_de),.user(1'b0),.last(1'b0),.rgb(mix_clean),
        .gain_r(color_gains_hdmi[25:13]),.gain_b(color_gains_hdmi[12:0]),.trim(color_control_hdmi),
        // V8 cartoon retains actual filtered RGB and no longer learns a second
        // colour plane. Use the same single display calibration as clear mode.
        .bypass(controls_hdmi[7:5]==1 && controls_hdmi[4]),
        .O_vs(color_vs),.O_hs(color_hs),.O_de(color_de),.O_user(),.O_last(),.O_rgb(color_clean));
    color_luma_preserve u_detection_color(.clk(S_hdmi_pixel_clk),.rst_n(S_hdmi_rst_n),
        .vs(mix_vs),.hs(mix_hs),.de(mix_de),.user(1'b0),.last(1'b0),.rgb(mix_clean),
        .gain_r(color_gains_hdmi[25:13]),.gain_b(color_gains_hdmi[12:0]),.trim(6'd0),.bypass(1'b0),
        .O_vs(),.O_hs(),.O_de(),.O_user(),.O_last(),.O_rgb(auto_clean));
    always @(posedge S_hdmi_pixel_clk or negedge S_hdmi_rst_n)begin
        if(!S_hdmi_rst_n)begin composite_c0<=0;composite_c1<=0;composite_c2<=0;overlay_c<=0;end
        else begin composite_c0<=mix_rgb;composite_c1<=composite_c0;composite_c2<=composite_c1;
            overlay_c<={overlay_c[1:0],mix_overlay};end
    end
    wire core_hdmi_vs,core_hdmi_hs,core_hdmi_de;
    wire [23:0] core_hdmi_rgb;
    fusion_flame_pipeline #(.SEPARATE_INPUT(1)) u_flame_fusion(.I_clk(S_hdmi_pixel_clk),.I_rst_n(S_hdmi_rst_n),
        .I_source_clk(S_csi_rx_clk),.I_source_frame(S_csi_frame_start),.I_cam_cfg_done(S_cam_cfg_done),
        .I_ddr_ready(S_init_calib_complete),.I_mipi_error(S_lane_error_any),.I_mode_clear(fusion_mode==0),
        .I_wb_locked(wb_locked),
        .I_control(controls_hdmi),.I_vsync(color_vs),.I_hsync(color_hs),.I_de(color_de),
        .I_clean_rgb(color_clean),.I_detector_rgb(auto_clean),.I_composite_rgb(composite_c2),.I_overlay_hit(overlay_c[2]),
        .O_vsync(core_hdmi_vs),.O_hsync(core_hdmi_hs),.O_de(core_hdmi_de),.O_rgb(core_hdmi_rgb),
        .O_led(O_led),.O_buzzer_n(O_buzzer_n),.O_alarm(alarm),.O_target(target),.O_source_ok(source_ok),
        .O_video_lost(video_lost),.O_armed(armed),.O_candidate_pixels(candidate_pixels),.O_center_x(target_x),.O_center_y(target_y));

    reg [23:0] display_plain_d;
    reg display_overlay_d;
    always @(posedge S_hdmi_pixel_clk or negedge S_hdmi_rst_n)begin
        if(!S_hdmi_rst_n)begin display_plain_d<=0;display_overlay_d<=0;end
        else begin display_plain_d<=color_clean;display_overlay_d<=overlay_c[2];end
    end
    wire denoise_vs,denoise_hs,denoise_de,denoise_overlay;
    wire [23:0] denoise_rgb;
    wire [7:0] denoise_control;
    // Classification has already produced the cartoon regions. Keep their
    // colours closed: do not average RGB across the palette after rendering.
    // Recognition has consumed its unchanged input upstream of this stage.
    display_denoise_v11 #(.H_TOTAL(1650),.ROI_Y0(176),.ROI_Y1(208)) u_display_denoise(
        .clk(S_hdmi_pixel_clk),.rst_n(S_hdmi_rst_n),
        .vs(core_hdmi_vs),.hs(core_hdmi_hs),.de(core_hdmi_de),.rgb(core_hdmi_rgb),
        .overlay(display_overlay_d || core_hdmi_rgb!=display_plain_d),.control(controls_hdmi),
        .O_vs(denoise_vs),.O_hs(denoise_hs),.O_de(denoise_de),.O_rgb(denoise_rgb),
        .O_overlay(denoise_overlay),.O_control(denoise_control));
    wire [5:0] display_offset;
    display_contrast u_display_contrast(.clk(S_hdmi_pixel_clk),.rst_n(S_hdmi_rst_n),
        .vs(denoise_vs),.hs(denoise_hs),.de(denoise_de),.rgb(denoise_rgb),
        .overlay(denoise_overlay),
        .clear_level(denoise_control[7:5]==1 && denoise_control[4:3]==0 ? style_levels_hdmi[2:0] : 3'd2),
        .bypass(denoise_control[7:5]==1 && denoise_control[4]),
        .cartoon(denoise_control[7:5]==1 && denoise_control[4:3]==1),
        .keep_legacy(denoise_control[7:5]>=2),
        .stat_vs(color_vs),.stat_de(color_de),.stat_rgb(auto_clean),
        .stat_enable(controls_hdmi[7:5]!=1 || controls_hdmi[4:3]==0),
        .O_vs(S_hdmi_out_vsync),.O_hs(S_hdmi_out_hsync),.O_de(S_hdmi_out_de),.O_rgb(S_hdmi_out_data),.O_offset(display_offset));

    hdmi_mixer #(
        .H_OFFSET   ( 0    ),
        .V_OFFSET   ( 0    ),
        .IMG_WIDTH  ( 1280 ),
        .IMG_HEIGHT ( 720  ),
        .DEBUG_MODE ( 0    ),
        .SHOW_COUNTER(0), .AUX_PIPELINED(1) // Normal SC500 1280x720 camera image
    )u_hdmi_mixer(
        .I_clk           ( S_hdmi_pixel_clk   ),
        .I_rst_n         ( S_hdmi_rst_n       ),
        .I_video_vsync   ( S_hdmi_vsync       ),
        .I_video_hsync   ( S_hdmi_hsync       ),
        .I_video_de      ( S_hdmi_de          ),
        .I_video_user    ( S_hdmi_user        ),
        .I_video_last    ( S_hdmi_last        ),
        .I_debug_status  ( S_hdmi_debug_status),
        .I_osd_enable    ( osd_enable_hdmi ),
        .O_overlay_x     (hud_x),
        .O_overlay_y     (hud_y),
        .I_aux_hit       ( hud_hit ),
        .I_aux_color     ( hud_color ),
        .O_video_rd_en   ( S_hdmi_window_rd_en),
        .I_video_rd_data ( S_video_rd_data    ),
        .O_hdmi_vsync    ( mix_vs ), .O_clean_data(mix_clean), .O_overlay_hit(mix_overlay),
        .O_hdmi_hsync    ( mix_hs ),
        .O_hdmi_de       ( mix_de ),
        .O_hdmi_data     ( mix_rgb )
    );

    hdmi_tx u_hdmi_tx(
        .I_pixel_clk        ( S_hdmi_pixel_clk  ),
        .I_serial_clk       ( S_hdmi_serial_clk ),
        .I_rst              ( ~S_hdmi_rst_n     ),
        .I_key_in           ( 1'b0              ),
        .I_edid_read_trig   ( 1'b0              ),
        .O_edid_read_valid  (                   ),
        .O_edid_read_data   (                   ),
        .I_video_rgb_enable ( 1'b1              ),
        .I_video_in_vs      ( S_hdmi_out_vsync  ),
        .I_video_in_de      ( S_hdmi_out_de     ),
        .I_video_in_user    ( 1'b0              ),
        .I_video_in_valid   ( 1'b0              ),
        .I_video_in_last    ( 1'b0              ),
        .O_video_in_ready   (                   ),
        .I_video_in_data    ( S_hdmi_out_data   ),
        .I_audio_valid      ( 1'b0              ),
        .I_audio_left_data  ( 24'd0             ),
        .I_audio_right_data ( 24'd0             ),
        .I_i2s_BCLK         ( 1'b0              ),
        .I_i2s_LRCK         ( 1'b0              ),
        .I_i2s_DOUT         ( 1'b0              ),
        .O_ddc_scl          (                   ),
        .O_hdmi_clk_p       (                   ),
        .O_hdmi_tx_p        (                   ),
        .O_tmds_ch0_p       ( O_tmds_ch0_p      ),
        .O_tmds_ch1_p       ( O_tmds_ch1_p      ),
        .O_tmds_ch2_p       ( O_tmds_ch2_p      ),
        .O_tmds_clk_p       ( O_tmds_clk_p      )
    );


    
endmodule
