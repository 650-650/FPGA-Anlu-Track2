"""Historical initial scaffold only, NOT a final reconstruction entrypoint.

The delivered source additionally contains the verified 24-clock transport
alignment, atomic HUD snapshot and verdict-priority fixes. Do not replay this
one-shot on the delivered tree. Use prepare_project.py and build.ps1 instead.
"""
from pathlib import Path
import re
R=Path(__file__).resolve().parents[1];H=R/'user_source/hdl_source'
def edit(name,old,new):
 p=H/name;s=p.read_text(encoding='utf-8');assert old in s,(name,old[:100]);s=s.replace(old,new,1);p.write_text(s,encoding='utf-8',newline='\n')
edit('video_in.v','    input wire         I_ddr_user_ready\n','''    input wire         I_ddr_user_ready,
    output wire O_observe_frame_start,
    output wire [1:0] O_observe_write_slot,
    output wire O_observe_overflow
''')
edit('video_in.v','    wire        S_fifo_rst;','''    wire S_input_fifo_full;
    assign O_observe_frame_start=S_frame_start;
    assign O_observe_write_slot=S_video_in_wp;
    assign O_observe_overflow=I_camera_valid && S_input_fifo_full;
    wire        S_fifo_rst;''')
edit('video_in.v','.full_flag  (),','.full_flag  (S_input_fifo_full),')
edit('video_out.v','    output reg[23:0]  O_vdieo_data\n','''    output reg[23:0]  O_vdieo_data,
    output wire O_observe_read_start,
    output wire [1:0] O_observe_read_slot,
    output wire O_observe_fifo_reset,
    output wire O_observe_underflow
''')
edit('video_out.v','    reg         S_fifo_rst;','''    assign O_observe_read_start=S_video_frame_start;
    assign O_observe_read_slot=I_video_out_rp;
    assign O_observe_fifo_reset=S_fifo_rst;
    assign O_observe_underflow=S_fifo_rd_en && S_fifo_emtpy;
    reg         S_fifo_rst;''')
edit('design_top_wrapper.v','    video_in u_video_in(','''    wire latency_write_start,latency_read_start,latency_input_overflow;
    wire latency_read_fifo_reset,latency_output_underflow;
    wire [1:0] latency_write_slot,latency_read_slot;
    video_in u_video_in(''')
edit('design_top_wrapper.v','        .I_ddr_user_ready     ( S_ddr_user_ready      )\n','''        .I_ddr_user_ready     ( S_ddr_user_ready      ),
        .O_observe_frame_start(latency_write_start),.O_observe_write_slot(latency_write_slot),
        .O_observe_overflow(latency_input_overflow)
''')
edit('design_top_wrapper.v','        .O_vdieo_data        ( S_video_rd_data      )\n','''        .O_vdieo_data        ( S_video_rd_data      ),
        .O_observe_read_start(latency_read_start),.O_observe_read_slot(latency_read_slot),
        .O_observe_fifo_reset(latency_read_fifo_reset),.O_observe_underflow(latency_output_underflow)
''')
edit('design_top_wrapper.v','    wire [15:0] xb,yb;','''    wire [31:0] latency_us;
    wire [15:0] latency_frame_id;
    wire latency_valid,latency_repeat,latency_skip;
    wire [19:0] latency_bcd;
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
        .O_valid(latency_valid),.O_repeat(latency_repeat),.O_skip(latency_skip));
    wire [15:0] xb,yb;''')
edit('design_top_wrapper.v','        .I_pixels(candidate_pixels),.I_exposure(isp_status[15:0]),.I_gain(isp_status[31:16]),','''        .I_pixels(candidate_pixels),.I_exposure(isp_status[15:0]),.I_gain(isp_status[31:16]),
        .I_latency_us(latency_us),.O_latency_bcd(latency_bcd),''')
edit('design_top_wrapper.v','        .I_output_fps_bcd(output_fps_bcd),.I_gain_bcd(gain_bcd),.I_target(target),.I_alarm(alarm),','''        .I_output_fps_bcd(output_fps_bcd),.I_gain_bcd(gain_bcd),
        .I_latency_bcd(latency_bcd),.I_latency_frame_id(latency_frame_id),
        .I_latency_valid(latency_valid),.I_latency_repeat(latency_repeat),.I_latency_skip(latency_skip),
        .I_target(target),.I_alarm(alarm),''')
edit('fusion_telemetry.v','    input wire [15:0] I_exposure,I_gain,','''    input wire [15:0] I_exposure,I_gain,
    input wire [31:0] I_latency_us,
    output reg [19:0] O_latency_bcd,''')
edit('fusion_telemetry.v','reg [2:0] field;','reg [3:0] field;')
edit('fusion_telemetry.v','input [2:0] f;','input [3:0] f;')
edit('fusion_telemetry.v','6:value_for={16\'d0,I_exposure};default:value_for={16\'d0,I_gain};',
 '''6:value_for={16'd0,I_exposure};7:value_for={16'd0,I_gain};default:value_for=I_latency_us;''')
edit('fusion_telemetry.v','O_gain_bcd<=0;','O_gain_bcd<=0;O_latency_bcd<=0;')
edit('fusion_telemetry.v','7:O_gain_bcd<=next_bcd[11:0];', '''7:O_gain_bcd<=next_bcd[11:0];
                    // Five digits in 10us units, displayed as XXX.XX ms.
                    8:O_latency_bcd<=next_bcd[23:4];''')
edit('fusion_telemetry.v','if(field==7)busy<=0;','if(field==8)busy<=0;')
edit('fusion_hud.v','    input wire [11:0] I_gain_bcd,','''    input wire [11:0] I_gain_bcd,
    input wire [19:0] I_latency_bcd,
    input wire [15:0] I_latency_frame_id,
    input wire I_latency_valid,I_latency_repeat,I_latency_skip,''')
edit('fusion_hud.v','    wire [6:0] dynamic_glyph=slot>=55?', '''    function [6:0] hex_char;
        input [3:0] nibble;
        begin hex_char=nibble<10?7'd48+nibble:7'd65+nibble-10;end
    endfunction
    wire [3:0] latency_digit=I_latency_bcd[(63-slot)*4+:4];
    wire [3:0] frame_nibble=I_latency_frame_id[(47-slot)*4+:4];
    wire latency_panel=panel==13;
    wire [6:0] dynamic_glyph=slot>=59?(I_latency_valid?7'd48+latency_digit:7'd45):
        latency_panel && slot==43?7'd48+I_latency_valid:
        latency_panel && slot>=44 && slot<=47?hex_char(frame_nibble):
        latency_panel && slot==48?7'd48+I_latency_repeat:
        latency_panel && slot==49?7'd48+I_latency_skip:
        slot>=55?''')
menu=H/'fusion_menu_rom.v';s=menu.read_text(encoding='utf-8')
start=13*256;end=start+256
s=re.sub(r'rom\[(\d+)\]=8\'d\d+;\n',lambda m:'' if start<=int(m[1])<end else m[0],s)
rows=[list(b'SW3 SAME FRAME DELAY  CAPTURE TO HDMI'),
      list(b'DELAY ')+[128+59,128+60,128+61,ord('.'),128+62,128+63]+list(b' MS   VALID ')+[128+43],
      list(b'SOURCE FRAME ')+[128+44,128+45,128+46,128+47]+list(b'  REPEAT ')+[128+48]+list(b'  SKIP ')+[128+49],
      list(b'FPGA INPUT TO HDMI  NOT MONITOR RESPONSE')]
code=''.join(f"rom[{start+r*64+c}]=8'd{value};\n" for r,row in enumerate(rows) for c,value in enumerate(row) if value!=32)
s=s.replace('\nend\n','\n'+code+'end\n',1);menu.write_text(s,encoding='utf-8',newline='\n')
p=R/'tools/prepare_project.py';s=p.read_text(encoding='utf-8')
s=s.replace("'display_denoise_v11.v']","'display_denoise_v11.v','frame_latency_monitor.v']")
assert 'frame_latency_monitor.v' in s;p.write_text(s,encoding='utf-8',newline='\n')
print('V12 passive integration written; no old datapath expressions changed')
