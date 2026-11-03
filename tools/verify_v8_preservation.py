"""Protect V7 originals and isolate V8 to display/style processing."""
from pathlib import Path
import hashlib,json,re
R=Path(__file__).resolve().parents[1];H=R/'user_source/hdl_source';V=R/'validation'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return p.read_text(encoding='utf-8')
def compact(s):return re.sub(r'\s+','',re.sub(r'//[^\n]*|/\*.*?\*/','',s,flags=re.S))
b=json.loads(read(V/'v7_baseline.json'));B=Path(b['root']);m=b['manifest'];BH=B/'user_source/hdl_source'
for f,d in m['source_sha256'].items():assert sha(B/f)==d,('original V7 changed',f)
assert sha(B/m['bitstream'])==m['bit_sha256'],'original V7 bit changed'
source={p.relative_to(R).as_posix():sha(p) for p in (R/'user_source').rglob('*') if p.is_file()}
changed=sorted(f for f,d in m['source_sha256'].items() if source[f]!=d)
allowed=['design_top_wrapper.v','display_contrast.v','display_tone.dat','image_curve_rom.v','isp/isp_top.v','isp/stylize_v5_96.v']
assert changed==sorted('user_source/hdl_source/'+f for f in allowed),changed
added=sorted(set(source)-set(m['source_sha256']))
assert added==['user_source/hdl_source/display_denoise_v8.v','user_source/hdl_source/isp/style_guide_v8.v'],added
protected=['visual_flame_alarm.v','fusion_flame_pipeline.v','first_aid_detector.v','fusion_controls.v','alarm_board_io.v',
 'scene_color_control.v','color_luma_preserve.v','awb.v','awb_line_memory.v','signal_delay_compact.v',
 'isp/auto_black_96.v','hdmi_mixer.v','anlogic_logo_rom.v','fusion_hud.v','fusion_menu_rom.v',
 'uiisp_beta/ae_set.v','uics500_cfg/uics500reg_720p60.v']
for f in protected:assert sha(H/f)==sha(BH/f),('protected source changed',f)
for f in ['td_project/camera_to_dsi_display.sdc','user_source/constraints_source/fusion_cdc.sdc','user_source/constraints_source/pin.adc']:
 assert sha(R/f)==sha(B/f),('clock/pin constraints changed',f)
assert read(H/'image_curve_rom.v').replace(R.as_posix(),B.as_posix())==read(BH/'image_curve_rom.v'),'base quality ROM implementation changed'
for name in ['curve_srgb.dat','curve_gain.dat','curve_gain_scaled.dat','median_majority.dat']:assert sha(H/name)==sha(BH/name),name
old=compact(read(BH/'design_top_wrapper.v'));new=compact(read(H/'design_top_wrapper.v'))
# Undo exactly the authorized display insertion and cartoon calibration change.
new=new.replace('.bypass(controls_hdmi[7:5]==1&&controls_hdmi[4]),','.bypass(controls_hdmi[7:5]==1&&controls_hdmi[4:3]!=0),',1)
a=new.index('wiredenoise_vs,');z=new.index('wire[5:0]display_offset;',a);new=new[:a]+new[z:]
new=new.replace('.overlay(denoise_overlay),','.overlay(display_overlay_d||core_hdmi_rgb!=display_plain_d),')
for k in ['vs','hs','de','rgb']:new=new.replace('denoise_'+k,'core_hdmi_'+k)
new=new.replace('denoise_control','controls_hdmi').replace('.keep_legacy(controls_hdmi[7:5]>=2),','')
assert new==old,'top differs beyond display insertion and single cartoon calibration'
old=compact(read(BH/'isp/isp_top.v'));new=compact(read(H/'isp/isp_top.v'))
a=old.index('wire[95:0]edge_data;');z=old.index('stylize_v5_96#(',a)
restored=new.replace('stylize_v5_96#(',old[a:z]+'stylize_v5_96#(',1).replace('.EXTERNAL_EDGE(0)','.EXTERNAL_EDGE(1)').replace('.I_edge_data(96\'d0)','.I_edge_data(edge_data)')
assert restored==old,'ISP differs beyond reuse of style windows for edge mode'
old=compact(read(BH/'display_contrast.v'));new=compact(read(H/'display_contrast.v'))
new=new.replace('overlay,bypass,cartoon,keep_legacy,','overlay,bypass,cartoon,')
assert new[:new.index('wire[9:0]rgb_lsum')]==old[:old.index('wire[9:0]rgb_lsum')],'display metering/statistics changed'
table=[int(a,2) for a in read(H/'display_tone.dat').split()]
assert len(table)==4096 and table[2048:]==[int(a,2) for a in read(BH/'display_tone.dat').split()],'legacy display curves changed'
for k in range(16):
 t=table[k*256:(k+1)*256];assert t[0]==0 and t[-1]==255 and all(t[j]<=t[j+1] for j in range(255))
result={'pass':True,'v7_original_files_verified':len(m['source_sha256']),'v7_original_bit_sha256':m['bit_sha256'],
 'changed_sources':changed,'added_sources':added,'protected_sources':protected,
 'camera_exposure_awb_dehaze_quality_curve_detection_controls_alarm_pins_unchanged':True,
 'top_diff_confined_to_display_after_detection_and_cartoon_display_calibration':True,
 'isp_diff_confined_to_reusing_style_edge_windows':True,'display_statistics_identical':True,
 'legacy_2048_curve_values_exact_v7':True,'all_tone_levels_monotone_black_white_anchored':True,
 'source_sha256':source,'dynamic_clear_and_actual_detection_path_proofs_required':True}
(V/'v8_preservation_result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('V8_PRESERVATION_PASS',len(m['source_sha256']),'original sources + bit intact;',len(changed),'changed,',len(added),'new')
