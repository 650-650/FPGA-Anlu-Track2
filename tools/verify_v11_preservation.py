"""Keep delivered V10 untouched and limit V11 edits to the visual branches."""
from pathlib import Path
import hashlib,json,re
R=Path(__file__).resolve().parents[1];V=R/'validation';H=R/'user_source/hdl_source'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return p.read_text(encoding='utf-8')
def compact(s):return re.sub(r'\s+','',re.sub(r'//[^\n]*|/\*.*?\*/','',s,flags=re.S))
b=json.loads(read(V/'v10_baseline_manifest.json'));B=Path(b['baseline'])
for f,h in b['sha256'].items():assert sha(B/f)==h,('V10 baseline changed',f)
old={f:h for f,h in b['sha256'].items() if f.startswith('user_source/')}
now={p.relative_to(R).as_posix():sha(p) for p in (R/'user_source').rglob('*') if p.is_file()}
assert not set(old)-set(now),'deleted production source'
changed=sorted(f for f in old if old[f]!=now[f])
allowed={'user_source/hdl_source/'+f for f in ['design_top_wrapper.v','isp/stylize_v5_96.v','image_curve_rom.v','display_contrast.v']}
assert set(changed)==allowed,('unexpected production changes',changed)
added=sorted(set(now)-set(old))
assert added==['user_source/hdl_source/display_denoise_v11.v'],('unexpected new source',added)
for name in ['display_contrast.v','image_curve_rom.v']:
 f='user_source/hdl_source/'+name
 assert read(R/f).replace(R.as_posix(),B.as_posix())==read(B/f),('more than ROM relocation',f)
before=compact(read(B/'user_source/hdl_source/design_top_wrapper.v'))
after=compact(read(H/'design_top_wrapper.v'))
old_a=before.index('wirecartoon_vs,cartoon_hs,cartoon_de,cartoon_overlay;')
new_a=after.index('display_denoise_v11#(')
anchor='wire[5:0]display_offset;'
old_z=before.index(anchor,old_a);new_z=after.index(anchor,new_a)
expected='''display_denoise_v11#(.H_TOTAL(1650))u_display_denoise(
 .clk(S_hdmi_pixel_clk),.rst_n(S_hdmi_rst_n),
 .vs(core_hdmi_vs),.hs(core_hdmi_hs),.de(core_hdmi_de),.rgb(core_hdmi_rgb),
 .overlay(display_overlay_d||core_hdmi_rgb!=display_plain_d),.control(controls_hdmi),
 .O_vs(denoise_vs),.O_hs(denoise_hs),.O_de(denoise_de),.O_rgb(denoise_rgb),
 .O_overlay(denoise_overlay),.O_control(denoise_control));'''
assert after[new_a:new_z]==compact(expected),'unexpected combined-stage wiring'
assert after[:new_a]+before[old_a:old_z]+after[new_z:]==before,'top changed outside combined display instance'
for f in ['td_project/camera_to_dsi_display.sdc','user_source/constraints_source/fusion_cdc.sdc','user_source/constraints_source/pin.adc']:
 assert sha(R/f)==sha(B/f),('clock or pin constraint changed',f)
out={'pass':True,'baseline':str(B),'original_sources_and_bit_verified':len(b['sha256']),
 'original_bit_sha256':next(h for f,h in b['sha256'].items() if f.endswith('.bit')),
 'changed_sources':changed,'added_sources':added,'unchanged_source_files':len(old)-len(changed),
 'sensor_ae_awb_quality_curve_detection_tracking_aid_alarm_controls_guide_logo_pins_unchanged':True,
 'top_change_only_combined_display_stage_after_detection':True,
 'protected_style_modes_dynamic_equivalence_required':True,'source_sha256':now}
(V/'v11_preservation_result.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print('V11_PRESERVATION_PASS',len(old),'V10 sources + bit intact;',len(changed),'changes,',len(added),'new module')
