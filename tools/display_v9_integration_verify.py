"""Extract the actual V9/V8 HDMI connection blocks and compare protected pages."""
from pathlib import Path
import hashlib,json,subprocess,sys,time
sys.stdout.reconfigure(encoding='utf-8')
R=Path(__file__).resolve().parents[1];H=R/'user_source/hdl_source'
B=R.with_name('07_stylize_flame_fusion_v8_visual_denoise');BH=B/'user_source/hdl_source'
V=R/'validation/display_v9_integration';V.mkdir(exist_ok=True)
IV=Path(r'D:\anlu\iverilog\bin\iverilog.exe')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return p.read_text(encoding='utf-8')
files=['design_top_wrapper.v','display_contrast.v','display_tone.dat','display_denoise_v9.v','display_cartoon_finish_v9.v',
 'color_luma_preserve.v','fusion_controls.v','fusion_flame_pipeline.v','visual_flame_alarm.v',
 'first_aid_detector.v','camera_frame_watchdog.v','alarm_board_io.v']
hashes={(H/f).relative_to(R).as_posix():sha(H/f) for f in files}
unit=json.loads(read(R/'validation/display_v9/result.json'))
lag=unit['production_sample_edge_lag'];stages=lag+11;extra=stages-10
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
for label,base in [('v9',H),('v8',BH)]:
 s=read(base/'design_top_wrapper.v');block=s[s.index('    wire [25:0] color_gains_hdmi;'):s.index('    hdmi_mixer #(')]
 if label=='v8':block=block.replace('display_contrast u_display_contrast','display_contrast_v8 u_display_contrast')
 (V/('production_'+label+'_display.v')).write_text(header.replace('NAME','production_'+label+'_display')+block+tail,encoding='utf-8')
reference=read(BH/'display_contrast.v').replace('module display_contrast #','module display_contrast_v8 #').replace('display_tone_rom','display_tone_rom_v8')
(V/'display_contrast_v8.v').write_text(reference,encoding='utf-8')
# Retain the established actual-top bench, now queue all metadata across the
# measured line-centred filter lag; protected comparisons use source control.
tb=read(R/'validation/display_integration_v8_tb.v')
tb=tb.replace('display_integration_v8_tb','display_integration_v9_tb').replace('production_v8_display current','production_v9_display current').replace('production_v7_display prior','production_v8_display prior')
tb=tb.replace('reg [23:0] cq[0:9],pq[0:9],oldq[0:4];reg [3:0] fq[0:9];',f'localparam NS={stages},EX={extra};reg [23:0] cq[0:NS-1],pq[0:NS-1],oldq[0:EX];reg [3:0] fq[0:NS-1];reg [7:0] ctlq[0:NS-1];')
tb=tb.replace('for(j=9;j>0;j=j-1)begin cq[j]=cq[j-1];pq[j]=pq[j-1];fq[j]=fq[j-1];end','for(j=NS-1;j>0;j=j-1)begin cq[j]=cq[j-1];pq[j]=pq[j-1];fq[j]=fq[j-1];ctlq[j]=ctlq[j-1];end')
tb=tb.replace('for(j=4;j>0;j=j-1)','for(j=EX;j>0;j=j-1)').replace('cq[0]=composite;','ctlq[0]=control;cq[0]=composite;')
tb=tb.replace('n>15','n>NS+4').replace('fq[9]','fq[NS-1]').replace('fq[5][3:1]','fq[9][3:1]').replace('V8 ten / V7 six clock RGB sync','V9 measured line-centred / V8 ten clock RGB sync')
tb=tb.replace('cq[9]','cq[NS-1]').replace('pq[9]','pq[NS-1]').replace('oldq[4]','oldq[EX]')
# Only output checks need the delayed page; color input checks stay same clock.
pos=tb.index('   if(nde)begin');end=tb.index('  n=n+1;',pos)
block=tb[pos:end].replace('control[7:5]','ctlq[NS-1][7:5]').replace('control[4]','ctlq[NS-1][4]')
tb=tb[:pos]+block+tb[end:]
tb=tb.replace('for(j=0;j<10;j=j+1)begin cq[j]=0;pq[j]=0;fq[j]=0;end','for(j=0;j<NS;j=j+1)begin cq[j]=0;pq[j]=0;fq[j]=0;ctlq[j]=0;end').replace('for(j=0;j<5;j=j+1)oldq[j]=0;','for(j=0;j<=EX;j=j+1)oldq[j]=0;')
tb=tb.replace('if(detector_checks<250000','idle(NS+350);\n  if(detector_checks<250000')
tb=tb.replace('DISPLAY_INTEGRATION_V8_PASS','DISPLAY_INTEGRATION_V9_PASS').replace('ten_clock_sync actual_top_actual_pipeline',f'{stages}_register_stages actual_top_actual_pipeline')
tb=tb.replace('changed vs V7','changed vs V8').replace('differs: phase','differs: phase')
tb=tb.replace('if(ncolor_de)begin', 'if(ncolor_de)begin\n    if(ncolor!==ocolor)$fatal(1,"HDMI calibration changed vs V8");')
tb=tb.replace('control[4:3]==1 && ncolor!==ocolor','control[4:3]==1 && ncolor===ocolor')
# The source bench used short shift queues. Use equivalent circular scoreboards
# for the measured one-line latency, avoiding hundreds of millions of TB copies.
tb=tb.replace('integer j,n=0,phase', 'integer w,r,oldw,oldr;integer j,n=0,phase')
tb=tb.replace('for(j=NS-1;j>0;j=j-1)begin cq[j]=cq[j-1];pq[j]=pq[j-1];fq[j]=fq[j-1];ctlq[j]=ctlq[j-1];end', 'w=n%NS;r=(w+1)%NS;')
tb=tb.replace('for(j=EX;j>0;j=j-1)oldq[j]=oldq[j-1];oldq[0]=op;', 'oldw=n%(EX+1);oldr=(oldw+1)%(EX+1);oldq[oldw]=op;')
tb=tb.replace('ctlq[0]=control;cq[0]=composite;pq[0]=clean;fq[0]={vs,hs,de,overlay};', 'ctlq[w]=control;cq[w]=composite;pq[w]=clean;fq[w]={vs,hs,de,overlay};')
for name in ['cq','pq','fq','ctlq']:tb=tb.replace(name+'[NS-1]',name+'[r]')
tb=tb.replace('oldq[EX]','oldq[oldr]').replace('fq[9]','fq[(w+NS-9)%NS]').replace('fq[2]','fq[(w+NS-2)%NS]').replace('pq[2]','pq[(w+NS-2)%NS]')
(V/'display_integration_v9_tb.v').write_text(tb,encoding='utf-8')
sources=[V/'display_integration_v9_tb.v',V/'production_v9_display.v',V/'production_v8_display.v',V/'display_contrast_v8.v',BH/'display_denoise_v8.v']+[H/f for f in files if f not in ['design_top_wrapper.v','display_tone.dat']]
start=time.time();binary=V/'test.vvp'
for phase,cmd in [('compile',[IV,'-g2012','-s','display_integration_v9_tb','-o',binary]+sources),('run',[IV.with_name('vvp.exe'),binary])]:
 p=subprocess.run(list(map(str,cmd)),cwd=R,capture_output=True,text=True,timeout=240)
 log=p.stdout+p.stderr;(V/(phase+'.log')).write_text(log,encoding='utf-8')
 assert p.returncode==0,(phase,log[-3000:])
 if phase=='run':assert 'DISPLAY_INTEGRATION_V9_PASS' in log;print(log[-2000:],flush=True)
for f,digest in hashes.items():assert sha(R/f)==digest,('DUT changed during test',f)
result={'tests':{'actual_top_against_v8':{'pass':True,'actual_fusion_pipeline':True,'detection_state_equal_same_clock':True,
 'detector_input_equal_same_clock':True,'protected_sw1_sketch_edge_sw2_sw3_pixels_equal_v8':True,'overlay_exact':True,
 'filter_sample_edge_lag':lag,'top_registered_stages':stages,'top_sample_edge_lag':stages-1,'added_display_clocks_v8':extra,
 'log':(V/'run.log').relative_to(R).as_posix()}},'source_sha256':hashes,
 'oracle_sha256':{Path(__file__).relative_to(R).as_posix():sha(Path(__file__))},
 'seconds':round(time.time()-start,2),'scope':'Actual extracted HDMI block and actual recognition pipeline; protected RGB compared with aligned V8 output. Sensor, DDR, panel and physical sound are outside this simulation.'}
(V/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('DISPLAY_V9_INTEGRATION_PASS',flush=True)
