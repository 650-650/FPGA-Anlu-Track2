"""Exercise the exact colour/overlay integration block extracted from top RTL."""
from pathlib import Path
import hashlib,json,subprocess,time
R=Path(__file__).resolve().parents[1];H=R/'user_source/hdl_source';V=R/'validation'
s=(H/'design_top_wrapper.v').read_text(encoding='utf-8')
block=s[s.index('    wire [25:0] color_gains_hdmi;'):s.index('    fusion_flame_pipeline #(.SEPARATE_INPUT(1))')]
wrapper='''module production_color_stage(
 input S_csi_rx_clk,S_hdmi_pixel_clk,S_hdmi_rst_n,S_hdmi_user,
 input [12:0] color_gain_r,color_gain_b,input [23:0] mix_clean,mix_rgb,
 input mix_vs,mix_hs,mix_de,mix_overlay,input [5:0] color_control_hdmi,input [7:0] controls_hdmi,
 output O_vs,O_hs,O_de,O_overlay,output [23:0] O_display,O_detect);
'''+block+'''
 assign O_vs=color_vs;assign O_hs=color_hs;assign O_de=color_de;assign O_overlay=overlay_c[2];
 assign O_display=overlay_c[2]?composite_c2:color_clean;assign O_detect=auto_clean;
endmodule
'''
(V/'production_color_stage.v').write_text(wrapper,encoding='utf-8')
IV=Path(r'D:\anlu\iverilog\bin\iverilog.exe');name='color_display_stage_tb';start=time.time();binary=V/(name+'.vvp')
for phase,args in [('compile',[IV,'-g2012','-s',name,'-o',binary,V/(name+'.v'),V/'production_color_stage.v',H/'color_luma_preserve.v',H/'fusion_controls.v']),('run',[IV.with_name('vvp.exe'),binary])]:
 p=subprocess.run(list(map(str,args)),cwd=R,capture_output=True,text=True,timeout=120)
 log=p.stdout+p.stderr;(V/(name+'_'+phase+'.log')).write_text(log,encoding='utf-8');assert p.returncode==0,log
 if phase=='run':assert 'COLOR_DISPLAY_STAGE_PASS' in log;print(log,flush=True)
(V/'display_stage_verification_result.json').write_text(json.dumps({'tests':{name:{'pass':True,'seconds':round(time.time()-start,2),'log':'validation/'+name+'_run.log'}},'source_sha256':{p.relative_to(R).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (R/'user_source').rglob('*') if p.is_file()}},indent=2),encoding='utf-8')
