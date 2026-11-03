"""Bind both inputs and restrict integration to documented levels/OSD/observer changes."""
from pathlib import Path
import json,hashlib,re
R=Path(__file__).resolve().parents[1];V=R/'validation/v16_scope';V.mkdir(parents=True,exist_ok=True)
inputs=json.loads((R/'validation/integration_inputs.json').read_text(encoding='utf-8'))
B=Path(inputs['baseline']);T=Path(inputs['teammate']);sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for k,v in inputs['baseline_source_sha256'].items():assert sha(B/k)==v,('V15_CHANGED',k)
for k,v in inputs['teammate_source_sha256'].items():assert sha(T/k)==v,('TEAMMATE_CHANGED',k)
assert sha(B/'output/stylize_flame_fusion_v15_ddr_latency_final.bit')==inputs['baseline_bit_sha256']
current={p.relative_to(R).as_posix():sha(p) for p in (R/'user_source').rglob('*') if p.is_file()}
assert set(current)==set(inputs['baseline_source_sha256'])
exact=[k for k,v in current.items() if v==inputs['baseline_source_sha256'][k]]
changed=set(current)-set(exact)
allow={'design_top_wrapper.v','fusion_controls.v','isp/isp_top.v','isp/stylize_v5_96.v','isp/style_guide_v8.v',
 'display_contrast.v','fusion_hud.v','fusion_menu_rom.v','fusion_chinese_font_rom.v','frame_latency_monitor.v','image_curve_rom.v'}
assert changed=={'user_source/hdl_source/'+n for n in allow},changed
def text(base,n):return (base/'user_source/hdl_source'/n).read_text(encoding='utf-8')
assert text(R,'fusion_controls.v')==text(T,'fusion_controls.v')
assert text(R,'image_curve_rom.v').replace(R.as_posix(),B.as_posix())==text(B,'image_curve_rom.v')
old=text(B,'design_top_wrapper.v');new=text(R,'design_top_wrapper.v')
edits={
 'wire [7:0] controls_50,controls_camera,controls_hdmi;':'wire [7:0] controls_50,controls_camera,controls_hdmi;\n    wire [11:0] style_levels_50,style_levels_camera,style_levels_hdmi;',
 '.O_osd_enable(osd_enable_50),.O_wb_toggle(wb_toggle),.O_color_control(color_control_50));':'.O_osd_enable(osd_enable_50),.O_wb_toggle(wb_toggle),.O_color_control(color_control_50),\n        .O_style_levels(style_levels_50));',
 'fusion_control_cdc u_control_camera(':'fusion_control_cdc #(.WIDTH(20)) u_control_camera(',
 '.I_rst_n(S_rst_n),.I_commit(S_raw_tuser),.I_data(controls_50),.O_data(controls_camera));':'.I_rst_n(S_rst_n),.I_commit(S_raw_tuser),\n        .I_data({style_levels_50,controls_50}),.O_data({style_levels_camera,controls_camera}));',
 'fusion_control_cdc #(.WIDTH(15)) u_control_hdmi(':'fusion_control_cdc #(.WIDTH(27)) u_control_hdmi(',
 '.I_data({color_control_50,osd_enable_50,controls_50}),.O_data({color_control_hdmi,osd_enable_hdmi,controls_hdmi}));':'.I_data({style_levels_50,color_control_50,osd_enable_50,controls_50}),\n        .O_data({style_levels_hdmi,color_control_hdmi,osd_enable_hdmi,controls_hdmi}));',
 '.I_mode_req(fusion_mode),.O_wb_locked(wb_locked),':'.I_mode_req(fusion_mode),.I_style_levels(style_levels_camera),.O_wb_locked(wb_locked),',
 '.I_control(controls_hdmi),.I_x_bcd(xb),.I_y_bcd(yb),.I_pixels_bcd(pb),':'.I_control(controls_hdmi),.I_style_levels(style_levels_hdmi),.I_x_bcd(xb),.I_y_bcd(yb),.I_pixels_bcd(pb),',
 '        .overlay(denoise_overlay),':'        .overlay(denoise_overlay),\n        .clear_level(denoise_control[7:5]==1 && denoise_control[4:3]==0 ? style_levels_hdmi[2:0] : 3\'d2),'
}
for a,b in edits.items():assert old.count(a)==1;old=old.replace(a,b)
assert old==new,'TOP_CHANGE_OUTSIDE_LEVELS'
for n in ['fusion_flame_pipeline.v','visual_flame_alarm.v','first_aid_detector.v','alarm_board_io.v','scene_color_control.v',
 'color_luma_preserve.v','display_denoise_v11.v','video_in.v','video_out.v','mc_to_user_interface.v',
 'ph1p35_ddr/ph1p35_324_ddr_wrapper.v','uics500_cfg/uicfgcs500_720p.v','uics500_cfg/uics500reg_720p60.v',
 'data_96bit_to_128bit.v','fusion_telemetry.v']:
 assert 'user_source/hdl_source/'+n in exact,n
assert sha(R/'td_project/camera_to_dsi_display.sdc')==sha(B/'td_project/camera_to_dsi_display.sdc')
assert sha(R/'user_source/constraints_source/fusion_cdc.sdc')==sha(B/'user_source/constraints_source/fusion_cdc.sdc')
monitor=text(R,'frame_latency_monitor.v')
assert 'source_tag_ready[s] && !metadata_ready[s] && slot_id[s]==cp_sequence' in monitor and 'slot_claim[s]==cp_sequence' not in monitor
assert 'active_claim<=slot_id[read_slot]' in monitor and 'slot_source_sequence' not in monitor
assert 'read_sequence<=display_sequence_now' in monitor and 'read_sequence<=read_sequence+16' not in monitor
assert 'source_tag_wait<=2' in monitor and 'read_tag_wait<=2' in monitor
# The observation is downstream only; no callback drives reset, pixels or DDR.
begin=new.index('    wire [31:0] latency_us;');end=new.index('    wire [15:0] xb,yb;',begin)
rest=new[:begin]+new[end:]
for n in ['latency_us','latency_frame_id','latency_debug_reason','latency_valid','latency_repeat','latency_skip','latency_status']:
 assert not re.search(r'\b'+n+r'\b',rest),n
r={'pass':True,'baseline':str(B),'teammate':str(T),'baseline_bit_sha256':inputs['baseline_bit_sha256'],
 'source_sha256':current,'baseline_source_sha256':inputs['baseline_source_sha256'],'teammate_source_sha256':inputs['teammate_source_sha256'],
 'byte_exact_count':len(exact),'byte_exact':exact,'changed_design_sources':sorted(changed),'top_only_levels':True,
 'SW2_detection_tracking_alarm_unchanged':True,'camera_crop_pins_clocks_unchanged':True,'V15_transport_fixes_unchanged':True,
 'observer_outputs_only_to_HUD':True,'normal_clear_keeps_middle_level_outside_SW1':True,
 'levels':'All five retained; no image/line buffer additions; exact default/mode/level pixels proven separately.',
 'verifier_sha256':sha(Path(__file__))}
(V/'result.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');print('V16_SCOPE_PASS',len(exact),'unchanged',len(changed),'documented changes')
