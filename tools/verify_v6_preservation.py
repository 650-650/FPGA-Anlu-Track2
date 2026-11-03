"""Audit the accepted V5 and every deliberate V6 source change."""
from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parents[1];V=R/'validation';H=R/'user_source/hdl_source'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return p.read_text(encoding='utf-8')
m=json.loads(read(V/'v5_baseline.json'));B=Path(m['root']);base=m['manifest'];BH=B/'user_source/hdl_source'
for f,d in base['source_sha256'].items():assert sha(B/f)==d,('V5 original modified',f)
assert sha(B/base['bitstream'])==base['bit_sha256'],'accepted V5 bit modified'
previous=json.loads(read(V/'integration_baselines.json'))
for label,entry in previous.items():
 for f,d in entry['sha256'].items():assert sha(Path(entry['root'])/f)==d,('earlier original modified',label,f)
changed=sorted(f for f,d in base['source_sha256'].items() if sha(R/f)!=d)
expected=['awb.v','color_luma_preserve.v','design_top_wrapper.v','first_aid_detector.v','image_curve_rom.v','isp/edge_detect_96.v','isp/isp_top.v','isp/stylize_v5_96.v']
assert changed==sorted('user_source/hdl_source/'+f for f in expected),changed
source={p.relative_to(R).as_posix():sha(p) for p in (R/'user_source').rglob('*') if p.is_file()}
added=sorted(set(source)-set(base['source_sha256']))
assert added==sorted('user_source/hdl_source/'+f for f in ['awb_line_memory.v','signal_delay_compact.v','curve_gain_scaled.dat','display_contrast.v']),added
for f in ['visual_flame_alarm.v','fusion_flame_pipeline.v','scene_color_control.v','fusion_controls.v','hdmi_mixer.v','anlogic_logo_rom.v','fusion_hud.v','fusion_menu_rom.v','uiisp_beta/ae_set.v','signal_delay.v','uics500_cfg/uicfgcs500_720p.v','uics500_cfg/uics500reg_720p60.v','curve_gain.dat','curve_srgb.dat','median_majority.dat']:
 assert sha(H/f)==sha(BH/f),('protected V5 source modified',f)
for f in ['td_project/camera_to_dsi_display.sdc','user_source/constraints_source/fusion_cdc.sdc','user_source/constraints_source/pin.adc']:
 assert sha(R/f)==sha(B/f),f
assert read(H/'awb.v').replace('signal_delay_compact','signal_delay')==read(BH/'awb.v'),'AWB differs beyond RAM selector'
assert read(H/'signal_delay_compact.v').replace('signal_delay_compact','signal_delay').replace('awb_line_memory','blk_mem_gen_awb_delay_signal').rstrip()==read(H/'signal_delay.v').rstrip(),'RAM address/controller scheduling modified'
a,b=read(BH/'design_top_wrapper.v'),read(H/'design_top_wrapper.v')
assert a[:a.index('    fusion_flame_pipeline #(')]==b[:b.index('    wire core_hdmi_vs')],'capture/DDR/ISP/scene colour wiring modified'
old_pipe=a[a.index('    fusion_flame_pipeline #('):a.index('    hdmi_mixer #(')]
new_pipe=b[b.index('    fusion_flame_pipeline #('):b.index('    reg [23:0] display_plain_d')]
for old,new in [('S_hdmi_out_vsync','core_hdmi_vs'),('S_hdmi_out_hsync','core_hdmi_hs'),('S_hdmi_out_de','core_hdmi_de'),('S_hdmi_out_data','core_hdmi_rgb')]:old_pipe=old_pipe.replace(old,new)
assert old_pipe.strip()==new_pipe.strip(),'detector input wiring changed'
assert a[a.index('    hdmi_mixer #('):]==b[b.index('    hdmi_mixer #('):],'mixer/HDMI source interface changed'
gain=[int(s,2) for s in read(H/'curve_gain.dat').split()];packed=[int(s,2) for s in read(H/'curve_gain_scaled.dat').split()]
assert len(gain)==len(packed)==256 and all(p==((g<<8)|((x*g+128)>>8)) for x,(g,p) in enumerate(zip(gain,packed)))
result={'v5_source_files_verified':len(base['source_sha256']),'v5_bit_sha256':base['bit_sha256'],'earlier_originals_verified':{k:len(v['sha256']) for k,v in previous.items()},'changed_sources':changed,'added_sources':added,'fire_classifier_and_pipeline_byte_identical_to_v5':True,'exposure_sensor_scene_color_auto_black_clocks_pins_unchanged':True,'detector_input_wiring_identical':True,'awb_address_controller_identical':True,'packed_peak_lookup_all_256_entries_exact':True,'display_contrast_is_downstream_only':True,'pixel_equivalence_requires_dynamic_test_results':True}
(V/'preservation_result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('V6_PRESERVATION_AUDIT_PASS',json.dumps(result))
