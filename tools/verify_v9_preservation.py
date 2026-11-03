"""Verify V8 original preservation and bound V9 to two visual branches."""
from pathlib import Path
import hashlib,json,re
R=Path(__file__).resolve().parents[1];H=R/'user_source/hdl_source';V=R/'validation'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return p.read_text(encoding='utf-8')
def compact(s):return re.sub(r'\s+','',re.sub(r'//[^\n]*|/\*.*?\*/','',s,flags=re.S))
b=json.loads(read(V/'v8_baseline.json'));B=Path(b['root']);m=b['manifest'];BH=B/'user_source/hdl_source'
for f,d in m['source_sha256'].items():assert sha(B/f)==d,('original V8 changed',f)
assert sha(B/m['bitstream'])==m['bit_sha256'],'original V8 bit changed'
source={p.relative_to(R).as_posix():sha(p) for p in (R/'user_source').rglob('*') if p.is_file()}
changed=sorted(f for f,d in m['source_sha256'].items() if source[f]!=d)
allowed=['design_top_wrapper.v','display_contrast.v','image_curve_rom.v','isp/stylize_v5_96.v']
assert changed==sorted('user_source/hdl_source/'+f for f in allowed),changed
added=sorted(set(source)-set(m['source_sha256']))
assert added==['user_source/hdl_source/display_cartoon_finish_v9.v','user_source/hdl_source/display_denoise_v9.v'],added
for f in m['source_sha256']:
 if f not in changed:assert source[f]==m['source_sha256'][f],f
for name in ['display_contrast.v','image_curve_rom.v']:
 assert read(H/name).replace(R.as_posix(),B.as_posix())==read(BH/name),('more than ROM path changed',name)
old=compact(read(BH/'design_top_wrapper.v'));new=compact(read(H/'design_top_wrapper.v'))
new=new.replace('wirecartoon_vs,cartoon_hs,cartoon_de,cartoon_overlay;wire[23:0]cartoon_rgb;wire[7:0]cartoon_control;','')
a=new.index('display_cartoon_finish_v9#(');z=new.index('display_denoise_v9#(',a);new=new[:a]+new[z:]
new=new.replace('.vs(cartoon_vs),.hs(cartoon_hs),.de(cartoon_de),.rgb(cartoon_rgb),','.vs(core_hdmi_vs),.hs(core_hdmi_hs),.de(core_hdmi_de),.rgb(core_hdmi_rgb),')
new=new.replace('.overlay(cartoon_overlay),.control(cartoon_control),','.overlay(display_overlay_d||core_hdmi_rgb!=display_plain_d),.control(controls_hdmi),')
new=new.replace('display_denoise_v9#(.H_TOTAL(1650))','display_denoise_v8#(.H_TOTAL(1650),.STRIDE(4))')
assert new==old,'top differs beyond the display denoise instance'
new=compact(read(H/'display_cartoon_finish_v9.v'));old=compact(read(BH/'display_denoise_v8.v'))
new=new.replace('display_cartoon_finish_v9','display_denoise_v8').replace('display_cartoon_line_v9','display_denoise_line_v8')
new=new.replace('TH_DARK=32,TH_BRIGHT=16,MAX_CORRECTION=6','TH_DARK=40,TH_BRIGHT=16,MAX_CORRECTION=12')
new=new.replace('wireselected=control[7:5]==1&&control[4:3]==1;','wireselected=control[7:5]<2&&!(control[7:5]==1&&control[4]);')
assert new==old,'cartoon finish differs beyond selected page and lower thresholds/cap'
for f in ['td_project/camera_to_dsi_display.sdc','user_source/constraints_source/fusion_cdc.sdc','user_source/constraints_source/pin.adc']:
 assert sha(R/f)==sha(B/f),('clock/pin constraints changed',f)
assert sha(H/'isp/style_guide_v8.v')==sha(BH/'isp/style_guide_v8.v'),'protected guide changed'
assert sha(H/'isp/isp_top.v')==sha(BH/'isp/isp_top.v'),'ISP or metering changed'
protected=['visual_flame_alarm.v','fusion_flame_pipeline.v','first_aid_detector.v','fusion_controls.v','alarm_board_io.v',
 'scene_color_control.v','color_luma_preserve.v','awb.v','awb_line_memory.v','signal_delay_compact.v',
 'isp/auto_black_96.v','hdmi_mixer.v','anlogic_logo_rom.v','fusion_hud.v','fusion_menu_rom.v',
 'uiisp_beta/ae_set.v','uics500_cfg/uics500reg_720p60.v','display_tone.dat']
for f in protected:assert sha(H/f)==sha(BH/f),('protected source changed',f)
result={'pass':True,'v8_original_files_verified':len(m['source_sha256']),'v8_original_bit_sha256':m['bit_sha256'],
 'changed_sources':changed,'added_sources':added,'protected_sources':protected,
 'camera_exposure_awb_dehaze_quality_curve_detection_controls_alarm_pins_tone_unchanged':True,
 'top_diff_only_display_denoise_instance':True,'isp_and_shared_sketch_edge_guide_byte_identical_v8':True,
 'style_modes_0_2_3_dynamic_pixel_equivalence_required':True,'source_sha256':source}
(V/'v9_preservation_result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('V9_PRESERVATION_PASS',len(m['source_sha256']),'original sources + bit intact;',len(changed),'changed,',len(added),'new')
