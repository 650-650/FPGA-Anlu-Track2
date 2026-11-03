"""Bound V7 changes to visual paths and prove every original V6 file intact."""
from pathlib import Path
import hashlib,json,re
R=Path(__file__).resolve().parents[1];V=R/'validation';H=R/'user_source/hdl_source'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return p.read_text(encoding='utf-8')
def compact(s):return re.sub(r'\s+','',re.sub(r'//[^\n]*|/\*.*?\*/','',s,flags=re.S))
b=json.loads(read(V/'v6_baseline.json'));B=Path(b['root']);m=b['manifest'];BH=B/'user_source/hdl_source'
for f,s in m['source_sha256'].items():assert sha(B/f)==s,('original V6 modified',f)
assert sha(B/m['bitstream'])==m['bit_sha256'],'original V6 bit modified'
source={p.relative_to(R).as_posix():sha(p) for p in (R/'user_source').rglob('*') if p.is_file()}
changed=sorted(f for f,s in m['source_sha256'].items() if source[f]!=s)
allowed=['design_top_wrapper.v','display_contrast.v','fusion_menu_rom.v','image_curve_rom.v','isp/edge_detect_96.v','isp/stylize_v5_96.v']
assert changed==sorted('user_source/hdl_source/'+s for s in allowed),changed
added=sorted(set(source)-set(m['source_sha256']));assert added==['user_source/hdl_source/display_tone.dat'],added
protected=['visual_flame_alarm.v','fusion_flame_pipeline.v','first_aid_detector.v','fusion_controls.v','alarm_board_io.v',
 'scene_color_control.v','color_luma_preserve.v','awb.v','awb_line_memory.v','signal_delay_compact.v','isp/isp_top.v',
 'isp/auto_black_96.v','hdmi_mixer.v','anlogic_logo_rom.v','uiisp_beta/ae_set.v','uics500_cfg/uics500reg_720p60.v']
for f in protected:assert sha(H/f)==sha(BH/f),('protected path changed',f)
for f in ['td_project/camera_to_dsi_display.sdc','user_source/constraints_source/fusion_cdc.sdc','user_source/constraints_source/pin.adc']:
 assert sha(R/f)==sha(B/f),('clock/pin constraint changed',f)
assert read(H/'image_curve_rom.v').replace(R.as_posix(),B.as_posix())==read(BH/'image_curve_rom.v'),'quality curve differs beyond ROM directory'
for name in ['curve_srgb.dat','curve_gain.dat','curve_gain_scaled.dat','median_majority.dat']:assert sha(H/name)==sha(BH/name),name
new=compact(read(H/'design_top_wrapper.v'));old=compact(read(BH/'design_top_wrapper.v'))
new_pred='controls_hdmi[7:5]==1&&controls_hdmi[4:3]!=0';old_pred='controls_hdmi[7:5]==1&&controls_hdmi[4]'
assert new.count(new_pred)==1 and new.replace(new_pred,old_pred,1)==old,'top differs beyond cartoon display colour bypass'
table=[int(a,2) for a in read(H/'display_tone.dat').split()];assert len(table)==2048
for i in range(8):
 t=table[i*256:i*256+256];assert t[0]==0 and t[-1]==255 and all(t[j]<=t[j+1] for j in range(255))
assert all(table[7*256+y]>=y for y in range(256)),'night tone darkens input'
result={'v6_original_files_verified':len(m['source_sha256']),'v6_original_bit_sha256':m['bit_sha256'],
 'changed_sources':changed,'added_sources':added,'protected_sources':protected,
 'classifier_aid_alarm_controls_and_detection_color_byte_identical_v6':True,
 'exposure_camera_dehaze_quality_and_detection_wiring_preserved':True,
 'top_only_cartoon_display_color_bypass_changed':True,'tone_table_all_levels_monotone_black_white_anchored':True,
 'night_level_7_non_darkening':True,'dynamic_style_clear_sketch_bypass_equivalence_required':True}
(V/'v7_preservation_result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('V7_PRESERVATION_PASS',json.dumps(result))
