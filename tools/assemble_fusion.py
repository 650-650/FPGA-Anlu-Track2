from pathlib import Path
import re

R=Path(__file__).resolve().parents[1]
H=R/'user_source/hdl_source'
if 'output wire [11:0] O_center_x' in (H/'visual_flame_alarm.v').read_text(encoding='utf-8'):
    raise SystemExit('Integration already assembled. Use build.ps1; do not reapply the one-time source patch.')
def patch(name, pairs):
    p=H/name;s=p.read_text(encoding='utf-8')
    for before,after in pairs:
        assert before in s,(name,before[:90]);s=s.replace(before,after,1)
    p.write_text(s,encoding='utf-8',newline='\n')

patch('visual_flame_alarm.v',[
 ('output reg O_frame_done, O_video_lost','output wire [11:0] O_center_x,O_center_y,\n    output reg O_frame_done, O_video_lost'),
 ('reg [11:0] bx0, bx1, by0, by1;','reg [11:0] bx0, bx1, by0, by1;\n    assign O_center_x=O_target_present ? (({1\'b0,bx0}+{1\'b0,bx1}) >> 1):12\'d0;\n    assign O_center_y=O_target_present ? (({1\'b0,by0}+{1\'b0,by1}) >> 1):12\'d0;')])
patch('awb.v',[
 ('input I_wb_allow,I_wb_relearn,','input I_wb_allow,I_wb_relearn,\n    output wire O_wb_locked,'),
 ('reg wb_locked;','reg wb_locked;\n    assign O_wb_locked=wb_locked;')])
p=H/'isp/isp_top.v';s=p.read_text(encoding='utf-8')
s=s.replace('input I_key_mode_n,            // KEY4（C7），按下为低：切换风格化模式\n    input [1:0] I_btn_n,           // K1/K2，按下为低：单独按 K1 开/关去灰（K1+K2 仍是白平衡重学）',
'''input [1:0] I_mode_req,
    output wire O_wb_locked,''')
assert 'I_btn_n' not in s.split(');',1)[0]
s=s.replace('.I_wb_allow(wb_allow_sync[1]),.I_wb_relearn(wb_relearn_sync[1]),',
            '.I_wb_allow(wb_allow_sync[1]),.I_wb_relearn(wb_relearn_sync[1]),.O_wb_locked(O_wb_locked),')
a=s.index('    (* ASYNC_REG="TRUE" *) reg [1:0] k1_sync')
b=s.index('    wire [95:0] ab_data;',a)
s=s[:a]+'    // Preserve the accepted V3 dehaze policy in every UI group.\n    wire dehaze_en=1\'b1;\n\n'+s[b:]
a=s.index('    localparam DEMO_FRAMES')
b=s.index('    wire [95:0] sty_data;',a)
s=s[:a]+'    // Mode is delivered coherently at the earlier RAW frame boundary.\n    wire [1:0] sty_mode=I_mode_req;\n\n'+s[b:]
# Remove obsolete key/demo explanations, leaving all arithmetic modules intact.
s=re.sub(r'    // 切换：KEY4.*?    // ---------------------------------------------------------------------\n', '', s,flags=re.S)
s=s.replace('    // 单独按一下 K1（松开时生效，按住期间没按过 K2）：开/关去灰，便于对比；上电默认开。',
            '    // The new control mapping keeps dehaze enabled; image arithmetic is unchanged.')
p.write_text(s,encoding='utf-8',newline='\n')

patch('hdmi_mixer.v',[
 ('parameter integer DEBUG_MODE = 0','parameter integer DEBUG_MODE = 0,\n    parameter integer SHOW_COUNTER = 1,\n    parameter integer AUX_PIPELINED = 0'),
 ('output reg[23:0]  O_hdmi_data','output reg[23:0]  O_clean_data,\n    output reg O_overlay_hit,\n    output reg[23:0]  O_hdmi_data'),
 ('if((!S_osd_hit) &&','if(SHOW_COUNTER && (!S_osd_hit) &&'),
 ('else if(S_video_de_2d && osd_enable_d[1] && aux_hit_d[1])\n                    O_hdmi_data <= aux_color_2d;',
  'else if(S_video_de_2d && osd_enable_d[1] && (AUX_PIPELINED ? I_aux_hit:aux_hit_d[1]))\n                    O_hdmi_data <= AUX_PIPELINED ? I_aux_color:aux_color_2d;')])
p=H/'hdmi_mixer.v';s=p.read_text(encoding='utf-8')
idx=s.rfind('endmodule')
s=s[:idx]+'''    // Same pixel and sync latency as the original V3 mixer output.
    // Recognition reads this clean path, while Logo and HUD retain priority.
    always @(posedge I_clk or negedge I_rst_n) begin
        if(!I_rst_n) begin O_clean_data<=0;O_overlay_hit<=0;end
        else begin
            O_clean_data<=S_video_data_2d;
            O_overlay_hit<=S_video_de_2d && osd_enable_d[1] &&
                (S_osd_hit || (AUX_PIPELINED ? I_aux_hit:aux_hit_d[1]));
        end
    end
''' + s[idx:]
p.write_text(s,encoding='utf-8',newline='\n')

patch('design_top_wrapper.v',[
 ('input wire        I_osd_enable, // SW1/A4: 1 shows Logo/text; 0 clean video',
  'input wire [3:0]  I_switches, // SW1/A4 SW2/B4 SW3/E11 SW4/D11\n    output wire [3:0] O_led,\n    output wire O_buzzer_n,'),
 ('inout wire [1:0]  I_button,','input wire [1:0]  I_button,'),
 ('input wire        I_key_mode,     // KEY4（C7）：风格化模式切换，按下为低','input wire        I_key_mode, // K4; I_rst_n is now the raw K3 GPIO.'),
 ('assign S_rst_n \t\t= S_pll_lock;','assign S_rst_n \t\t= S_pll_lock && fusion_reset_n;'),
 ('assign S_hdmi_rst_n = S_pll_lock;','assign S_hdmi_rst_n = S_pll_lock && fusion_reset_n;'),
 ('( ~I_rst_n          )','( ~fusion_reset_n  )'),
 ('.buttons_n(I_button)', '.buttons_n(2\'b11)'),
 ('.I_wb_allow(wb_allow),.I_wb_relearn(wb_relearn),.I_key_mode_n(I_key_mode),.I_btn_n(I_button),',
  '.I_wb_allow(wb_allow),.I_wb_relearn(wb_relearn | wb_relearn_pulse),.I_mode_req(fusion_mode),.O_wb_locked(wb_locked),')])
p=H/'design_top_wrapper.v';s=p.read_text(encoding='utf-8')
insert='''
    wire fusion_reset_n,wb_toggle,wb_locked;
    wire [7:0] controls_50,controls_camera,controls_hdmi;
    wire [1:0] fusion_mode=(controls_camera[7:5]==1 && controls_camera[4:3]<3) ? controls_camera[4:3]:2'd0;
    fusion_controls u_controls(.I_clk(I_sys_clk),.I_keys_n({I_key_mode,I_rst_n,I_button}),
        .I_switches(I_switches),.O_system_rst_n(fusion_reset_n),.O_control(controls_50),.O_wb_toggle(wb_toggle));
    fusion_control_cdc u_control_camera(.I_source_clk(I_sys_clk),.I_dest_clk(S_csi_rx_clk),
        .I_rst_n(S_rst_n),.I_commit(S_raw_tuser),.I_data(controls_50),.O_data(controls_camera));
    fusion_control_cdc u_control_hdmi(.I_source_clk(I_sys_clk),.I_dest_clk(S_hdmi_pixel_clk),
        .I_rst_n(S_hdmi_rst_n),.I_commit(S_hdmi_user),.I_data(controls_50),.O_data(controls_hdmi));
    (* ASYNC_REG="TRUE" *) reg [2:0] wb_toggle_sync;
    wire wb_relearn_pulse=wb_toggle_sync[2]!=wb_toggle_sync[1];
    always @(posedge S_csi_rx_clk or negedge S_rst_n) begin
        if(!S_rst_n)wb_toggle_sync<=0;
        else wb_toggle_sync<={wb_toggle_sync[1:0],wb_toggle};
    end
'''
s=s.replace('    PLL u_PLL(',insert+'\n    PLL u_PLL(',1)
a=s.index('    // The switch is asynchronous')
b=s.index('    hdmi_mixer #(',a)
s=s[:a]+'''    wire [11:0] hud_x,hud_y;
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
    wire [15:0] xb,yb;
    wire [23:0] pb;
    wire [19:0] seconds_bcd,exposure_bcd;
    wire [7:0] camera_fps_bcd,output_fps_bcd;
    wire [11:0] gain_bcd;
    fusion_telemetry u_telemetry(.I_clk(S_hdmi_pixel_clk),.I_rst_n(S_hdmi_rst_n),.I_frame(S_hdmi_user),
        .I_source_clk(S_csi_rx_clk),.I_source_frame(S_csi_frame_start),.I_x(target_x),.I_y(target_y),
        .I_pixels(candidate_pixels),.I_exposure(isp_status[15:0]),.I_gain(isp_status[31:16]),
        .O_x_bcd(xb),.O_y_bcd(yb),.O_pixels_bcd(pb),.O_seconds_bcd(seconds_bcd),
        .O_exposure_bcd(exposure_bcd),.O_camera_fps_bcd(camera_fps_bcd),.O_output_fps_bcd(output_fps_bcd),.O_gain_bcd(gain_bcd));
    fusion_hud u_hud(.I_clk(S_hdmi_pixel_clk),.I_rst_n(S_hdmi_rst_n),.I_x(hud_x),.I_y(hud_y),
        .I_control(controls_hdmi),.I_x_bcd(xb),.I_y_bcd(yb),.I_pixels_bcd(pb),
        .I_seconds_bcd(seconds_bcd),.I_exposure_bcd(exposure_bcd),.I_camera_fps_bcd(camera_fps_bcd),
        .I_output_fps_bcd(output_fps_bcd),.I_gain_bcd(gain_bcd),.I_target(target),.I_alarm(alarm),
        .I_audio(controls_hdmi[7:5]==2 && controls_hdmi[4:3]==2 && !controls_hdmi[2] && source_ok && armed),
        .I_cam_cfg(cfg_h[1]),.I_ddr_ready(ddr_h[1]),.I_source_ok(source_ok),.I_wb_locked(wb_h[1]),
        .I_armed(armed),.I_debug(S_hdmi_debug_status),.O_hit(hud_hit),.O_color(hud_color));
    fusion_flame_pipeline u_flame_fusion(.I_clk(S_hdmi_pixel_clk),.I_rst_n(S_hdmi_rst_n),
        .I_source_clk(S_csi_rx_clk),.I_source_frame(S_csi_frame_start),.I_cam_cfg_done(S_cam_cfg_done),
        .I_ddr_ready(S_init_calib_complete),.I_mipi_error(S_lane_error_any),.I_mode_clear(fusion_mode==0),
        .I_control(controls_hdmi),.I_vsync(mix_vs),.I_hsync(mix_hs),.I_de(mix_de),
        .I_clean_rgb(mix_clean),.I_composite_rgb(mix_rgb),.I_overlay_hit(mix_overlay),
        .O_vsync(S_hdmi_out_vsync),.O_hsync(S_hdmi_out_hsync),.O_de(S_hdmi_out_de),.O_rgb(S_hdmi_out_data),
        .O_led(O_led),.O_buzzer_n(O_buzzer_n),.O_alarm(alarm),.O_target(target),.O_source_ok(source_ok),
        .O_video_lost(video_lost),.O_armed(armed),.O_candidate_pixels(candidate_pixels),.O_center_x(target_x),.O_center_y(target_y));

''' + s[b:]
s=s.replace('.DEBUG_MODE ( 0    )','.DEBUG_MODE ( 0    ),\n        .SHOW_COUNTER(0), .AUX_PIPELINED(1)',1)
s=s.replace('( osd_enable_sync[1] )',"( 1'b1 )",1)
s=s.replace('.O_overlay_x     ()','.O_overlay_x     (hud_x)',1).replace('.O_overlay_y     ()','.O_overlay_y     (hud_y)',1)
s=s.replace(".I_aux_hit       ( 1'b0 )",'.I_aux_hit       ( hud_hit )',1).replace(".I_aux_color     ( 24'd0 )",'.I_aux_color     ( hud_color )',1)
s=s.replace('.O_hdmi_vsync    ( S_hdmi_out_vsync   )','.O_hdmi_vsync    ( mix_vs ), .O_clean_data(mix_clean), .O_overlay_hit(mix_overlay)',1)
s=s.replace('.O_hdmi_hsync    ( S_hdmi_out_hsync   )','.O_hdmi_hsync    ( mix_hs )',1)
s=s.replace('.O_hdmi_de       ( S_hdmi_out_de      )','.O_hdmi_de       ( mix_de )',1)
s=s.replace('.O_hdmi_data     ( S_hdmi_out_data    )','.O_hdmi_data     ( mix_rgb )',1)
assert 'osd_enable_sync' not in s
p.write_text(s,encoding='utf-8',newline='\n')

p=R/'user_source/constraints_source/pin.adc';s=p.read_text(encoding='utf-8')
s=re.sub(r'set_pin_assignment\s*\{ I_osd_enable \}[^\n]*', '',s)
for signal,pin in [('I_switches[0]','A4'),('I_switches[1]','B4'),('I_switches[2]','E11'),('I_switches[3]','D11'),
                   ('O_led[0]','D10'),('O_led[1]','E10'),('O_led[2]','C6'),('O_led[3]','D6'),('O_buzzer_n','C12')]:
    s+=f'\nset_pin_assignment {{ {signal} }} {{ LOCATION = {pin}; IOSTANDARD = LVCMOS33; PULLTYPE = '+('PULLUP' if signal.startswith('I_') else 'NONE')+'; }'
p.write_text(s+'\n',encoding='utf-8',newline='\n')
print('Fusion sources connected; arithmetic cores retained')
