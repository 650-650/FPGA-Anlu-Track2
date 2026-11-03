"""Native tone ERAM and extracted production V7/V6 display wiring checks."""
from pathlib import Path
import hashlib,json,subprocess,sys,time
sys.stdout.reconfigure(encoding='utf-8')
R=Path(__file__).resolve().parents[1];H=R/'user_source/hdl_source';V=R/'validation/display_v7_native';V.mkdir(exist_ok=True)
B=R.with_name('07_stylize_flame_fusion_v6_visual_aid');BH=B/'user_source/hdl_source'
MS=Path(r'D:\anlu\altera\14.1S\modelsim_ase\win32aloem');L=Path(r'D:\anlu\TD_6.2.1_Engineer_6.2.168.116\sim_release\ph1p');IV=Path(r'D:\anlu\iverilog\bin\iverilog.exe')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return p.read_text(encoding='utf-8')
files=['display_contrast.v','display_tone.dat','design_top_wrapper.v','color_luma_preserve.v','fusion_controls.v','fusion_flame_pipeline.v','visual_flame_alarm.v','first_aid_detector.v','camera_frame_watchdog.v','alarm_board_io.v']
hashes={str((H/f).relative_to(R)).replace('\\','/'):sha(H/f) for f in files}
for f in ['color_luma_preserve.v','fusion_flame_pipeline.v','visual_flame_alarm.v','first_aid_detector.v','camera_frame_watchdog.v','alarm_board_io.v']:
 assert read(H/f)==read(BH/f),('protected source changed',f)
start=time.time();results={}
steps=[('vmap_init',[MS/'vmap.exe','-c']),('vlib',[MS/'vlib.exe','work']),('vmap_work',[MS/'vmap.exe','work','work']),
 ('vlog',[MS/'vlog.exe','-sv','-work','work',L/'ph1p_phy_gsr.v',L/'ph1p_logic_eram.v',H/'display_contrast.v',V/'display_tone_native_tb.v']),
 ('vsim',[MS/'vsim.exe','-c','-do','vsim work.PH1P_PHY_GSR work.display_tone_native_tb; onfinish stop; run -all; quit -f'])]
for name,cmd in steps:
 p=subprocess.run(list(map(str,cmd)),cwd=V,capture_output=True,text=True,timeout=120)
 log=p.stdout+p.stderr;(V/(name+'.log')).write_text(log,encoding='utf-8');assert p.returncode==0 and '** Error' not in log and '** Fatal' not in log,(name,log[-2000:])
 if name=='vsim':assert 'DISPLAY_TONE_NATIVE_PASS' in log;print(log[-1400:],flush=True)
results['display_tone_native_tb']={'pass':True,'native_vendor_model':True,'addresses':2048,'native_reads':4096,'log':str((V/'vsim.log').relative_to(R))}
header='''module NAME(
 input S_csi_rx_clk,S_hdmi_pixel_clk,S_hdmi_rst_n,S_hdmi_user,
 input [12:0] color_gain_r,color_gain_b,input [23:0] mix_clean,mix_rgb,
 input mix_vs,mix_hs,mix_de,mix_overlay,input [5:0] color_control_hdmi,input [7:0] controls_hdmi,
 input [1:0] fusion_mode,input S_csi_frame_start,S_cam_cfg_done,S_init_calib_complete,S_lane_error_any,wb_locked,
 output O_vs,O_hs,O_de,output [23:0] O_rgb,O_detect,O_clean,O_core,O_detector_port,output O_color_de);
 wire S_hdmi_out_vsync,S_hdmi_out_hsync,S_hdmi_out_de;
 wire [23:0] S_hdmi_out_data;wire [3:0] O_led;
 wire O_buzzer_n,alarm,target,source_ok,video_lost,armed;
 wire [31:0] candidate_pixels;wire [11:0] target_x,target_y;
'''
tail='''
 assign O_vs=S_hdmi_out_vsync;assign O_hs=S_hdmi_out_hsync;assign O_de=S_hdmi_out_de;assign O_rgb=S_hdmi_out_data;
 assign O_detect=auto_clean;assign O_clean=color_clean;assign O_core=core_hdmi_rgb;assign O_color_de=color_de;
 assign O_detector_port=u_flame_fusion.I_detector_rgb;
endmodule
'''
for label,base in [('v7',H),('v6',BH)]:
 s=read(base/'design_top_wrapper.v');block=s[s.index('    wire [25:0] color_gains_hdmi;'):s.index('    hdmi_mixer #(')]
 if label=='v6':block=block.replace('display_contrast u_display_contrast','display_contrast_v6 u_display_contrast')
 (V/('production_'+label+'_display.v')).write_text(header.replace('NAME','production_'+label+'_display')+block+tail,encoding='utf-8')
(V/'display_contrast_v6.v').write_text(read(BH/'display_contrast.v').replace('module display_contrast #','module display_contrast_v6 #'),encoding='utf-8')
name='display_integration_v7_tb';binary=V/(name+'.vvp')
sources=[V/(name+'.v'),V/'production_v7_display.v',V/'production_v6_display.v',V/'display_contrast_v6.v']+[H/f for f in files if f not in ['display_tone.dat','design_top_wrapper.v']]
for phase,cmd in [('compile',[IV,'-g2012','-s',name,'-o',binary]+sources),('run',[IV.with_name('vvp.exe'),binary])]:
 p=subprocess.run(list(map(str,cmd)),cwd=R,capture_output=True,text=True,timeout=120)
 log=p.stdout+p.stderr;(V/(name+'_'+phase+'.log')).write_text(log,encoding='utf-8');assert p.returncode==0,(phase,log[-2400:])
 if phase=='run':assert 'DISPLAY_INTEGRATION_V7_PASS' in log;print(log[-1600:],flush=True)
results[name]={'pass':True,'extracted_top_block':True,'actual_fusion_pipeline':True,'detector_input_exact_v6':True,'style_postprocessing_bypassed':True,'latency_clocks':6,'log':str((V/(name+'_run.log')).relative_to(R))}
for f in files:assert hashes[str((H/f).relative_to(R)).replace('\\','/')]==sha(H/f),('DUT changed while testing',f)
result={'tests':results,'source_sha256':hashes,'native_vendor_model':True,'seconds':round(time.time()-start,2),
 'wrapper_sha256':{p.relative_to(R).as_posix():sha(p) for p in V.glob('production_*.v')},'scope':'Tone table/native read timing and real top extracted HDMI stages; sensor/DDR/HDMI PHY not simulated.'}
(V/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('DISPLAY_V7_NATIVE_AND_INTEGRATION_PASS',flush=True)
