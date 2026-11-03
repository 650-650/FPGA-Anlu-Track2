"""Compare extracted, unedited production HDMI wiring against preserved V7."""
from pathlib import Path
import hashlib,json,subprocess,sys,time
sys.stdout.reconfigure(encoding='utf-8')
R=Path(__file__).resolve().parents[1];H=R/'user_source/hdl_source'
B=R.with_name('07_stylize_flame_fusion_v7_shadow_clean');BH=B/'user_source/hdl_source'
V=R/'validation/display_v8_integration';V.mkdir(exist_ok=True)
IV=Path(r'D:\anlu\iverilog\bin\iverilog.exe')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return p.read_text(encoding='utf-8')
files=['design_top_wrapper.v','display_contrast.v','display_tone.dat','display_denoise_v8.v',
 'color_luma_preserve.v','fusion_controls.v','fusion_flame_pipeline.v','visual_flame_alarm.v',
 'first_aid_detector.v','camera_frame_watchdog.v','alarm_board_io.v']
hashes={(H/f).relative_to(R).as_posix():sha(H/f) for f in files}
header='''module NAME(
 input S_csi_rx_clk,S_hdmi_pixel_clk,S_hdmi_rst_n,S_hdmi_user,
 input [12:0] color_gain_r,color_gain_b,input [23:0] mix_clean,mix_rgb,
 input mix_vs,mix_hs,mix_de,mix_overlay,input [5:0] color_control_hdmi,input [7:0] controls_hdmi,
 input [1:0] fusion_mode,input S_csi_frame_start,S_cam_cfg_done,S_init_calib_complete,S_lane_error_any,wb_locked,
 output O_vs,O_hs,O_de,output [23:0] O_rgb,O_detect,O_clean,O_core,O_detector_port,
 output O_color_de,output [65:0] O_detection_state);
 wire S_hdmi_out_vsync,S_hdmi_out_hsync,S_hdmi_out_de;wire [23:0] S_hdmi_out_data;wire [3:0] O_led;
 wire O_buzzer_n,alarm,target,source_ok,video_lost,armed;wire [31:0] candidate_pixels;wire [11:0] target_x,target_y;
'''
tail='''
 assign O_vs=S_hdmi_out_vsync;assign O_hs=S_hdmi_out_hsync;assign O_de=S_hdmi_out_de;assign O_rgb=S_hdmi_out_data;
 assign O_detect=auto_clean;assign O_clean=color_clean;assign O_core=core_hdmi_rgb;assign O_color_de=color_de;
 assign O_detector_port=u_flame_fusion.I_detector_rgb;
 assign O_detection_state={O_led,O_buzzer_n,alarm,target,source_ok,video_lost,armed,candidate_pixels,target_x,target_y};
endmodule
'''
for label,base in [('v8',H),('v7',BH)]:
 s=read(base/'design_top_wrapper.v');block=s[s.index('    wire [25:0] color_gains_hdmi;'):s.index('    hdmi_mixer #(')]
 if label=='v7':block=block.replace('display_contrast u_display_contrast','display_contrast_v7 u_display_contrast')
 (V/('production_'+label+'_display.v')).write_text(header.replace('NAME','production_'+label+'_display')+block+tail,encoding='utf-8')
reference=read(BH/'display_contrast.v').replace('module display_contrast #','module display_contrast_v7 #').replace('display_tone_rom','display_tone_rom_v7')
(V/'display_contrast_v7.v').write_text(reference,encoding='utf-8')
sources=[R/'validation/display_integration_v8_tb.v',V/'production_v8_display.v',V/'production_v7_display.v',V/'display_contrast_v7.v']+[H/f for f in files if f not in ['design_top_wrapper.v','display_tone.dat']]
start=time.time();binary=V/'test.vvp'
for phase,cmd in [('compile',[IV,'-g2012','-s','display_integration_v8_tb','-o',binary]+sources),('run',[IV.with_name('vvp.exe'),binary])]:
 p=subprocess.run(list(map(str,cmd)),cwd=R,capture_output=True,text=True,timeout=240)
 log=p.stdout+p.stderr;(V/(phase+'.log')).write_text(log,encoding='utf-8')
 assert p.returncode==0,(phase,log[-3000:])
 if phase=='run':assert 'DISPLAY_INTEGRATION_V8_PASS' in log;print(log[-2200:],flush=True)
for f,digest in hashes.items():assert sha(R/f)==digest,('DUT changed during test',f)
result={'tests':{'actual_top_against_v7':{'pass':True,'actual_fusion_pipeline':True,'detection_state_equal_same_clock':True,
 'detector_input_equal_same_clock':True,'sw2_sw3_pixels_equal_v7_delayed_four_clocks':True,'overlay_exact':True,
 'sketch_edge_no_second_tone_or_colour':True,'latency_clocks':10,'log':(V/'run.log').relative_to(R).as_posix()}},
 'source_sha256':hashes,'oracle_sha256':{p.relative_to(R).as_posix():sha(p) for p in [Path(__file__),R/'validation/display_integration_v8_tb.v']},
 'wrapper_sha256':{p.relative_to(R).as_posix():sha(p) for p in V.glob('production_*.v')},
 'seconds':round(time.time()-start,2),'scope':'Actual production HDMI block and actual recognition pipeline; sensor, DDR, PHY, physical buzzer and scene accuracy are not simulated.'}
(V/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('DISPLAY_V8_INTEGRATION_PASS',flush=True)
