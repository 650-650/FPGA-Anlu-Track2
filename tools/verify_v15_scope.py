"""Pin V14 and prove all non-transport/non-SW3 image logic is unchanged."""
from pathlib import Path
import re,json,hashlib
R=Path(__file__).resolve().parents[1]
B=R.with_name('07_stylize_flame_fusion_v14_latency_provenance')
V=R/'validation/v15_scope';V.mkdir(parents=True,exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((B/'output/build_manifest.json').read_text(encoding='utf-8'))
assert m['bit_sha256']=='21c9cd9c2b265ea64a80234cd56e608e9b785500255e5d9bc9336ca14d2ff48d'
assert sha(B/'output'/m['bitstream'])==m['bit_sha256']
for rel,h in m['source_sha256'].items():assert sha(B/rel)==h,('BASELINE_CHANGED',rel)
current={p.relative_to(R).as_posix():sha(p) for p in (R/'user_source').rglob('*') if p.is_file()}
assert set(current)==set(m['source_sha256'])
rom={'user_source/hdl_source/image_curve_rom.v','user_source/hdl_source/display_contrast.v'}
norm=lambda s:re.sub(r'"[^"\r\n]*/(curve_srgb|curve_gain|curve_gain_scaled|median_majority|display_tone)\.dat"',lambda m:'"@ROM/'+m[1]+'.dat"',s)
exact=[];paths=[];changed=[]
for rel,h in current.items():
 if h==m['source_sha256'][rel]:exact.append(rel)
 elif rel in rom:
  assert norm((R/rel).read_text(encoding='utf-8'))==norm((B/rel).read_text(encoding='utf-8'));paths.append(rel)
 else:changed.append(rel)
allowed={'design_top_wrapper.v','frame_latency_monitor.v','fusion_hud.v','fusion_menu_rom.v',
 'fusion_chinese_font_rom.v','mc_to_user_interface.v','ph1p35_ddr/ph1p35_324_ddr_wrapper.v','video_out.v'}
assert set(changed)=={'user_source/hdl_source/'+s for s in allowed},changed
def txt(base,name):return (base/'user_source/hdl_source'/name).read_text(encoding='utf-8')
old=txt(B,'design_top_wrapper.v');new=txt(R,'design_top_wrapper.v')
edits={
 'wire [15:0] latency_frame_id;':'wire [15:0] latency_frame_id;\n    wire [15:0] latency_debug_reason;',
 'reg [15:0] latency_hud_id;':'reg [15:0] latency_hud_id,latency_hud_reason;',
 'latency_hud_id<=0;latency_hud_flags':'latency_hud_id<=0;latency_hud_reason<=0;latency_hud_flags',
 'latency_hud_us<=latency_us;latency_hud_id<=latency_frame_id;':'latency_hud_us<=latency_us;latency_hud_id<=latency_frame_id;\n            latency_hud_reason<=latency_debug_reason;',
 '.O_skip(latency_skip),.O_status(latency_status));':'.O_skip(latency_skip),.O_status(latency_status),.O_debug_reason(latency_debug_reason));',
 '.I_latency_bcd(latency_bcd),.I_latency_frame_id(latency_hud_id),':'.I_latency_bcd(latency_bcd),\n        .I_latency_frame_id((controls_hdmi[7:5]==3\'d3 && controls_hdmi[4:3]==2\'d2) ? latency_hud_reason : latency_hud_id),'
}
for a,b in edits.items():assert old.count(a)==1;old=old.replace(a,b)
assert old==new,'TOP_CHANGED_OUTSIDE_PASSIVE_SW3_DIAGNOSTICS'
def no_constants(s):return re.sub(r'    // BEGIN GENERATED CHINESE GLYPH IDS.*?    // END GENERATED CHINESE GLYPH IDS','@GLYPH_IDS',s,flags=re.S)
assert no_constants(txt(B,'fusion_hud.v')).replace('latency_panel1<=panel==13;','latency_panel1<=panel==13 || panel==14;')==no_constants(txt(R,'fusion_hud.v'))
oldmenu=json.loads((B/'tools/chinese_assets/menu_zh.json').read_text(encoding='utf-8'))
newmenu=json.loads((R/'tools/chinese_assets/menu_zh.json').read_text(encoding='utf-8'))
for k,v in oldmenu['panels'].items():
 if k!='14':assert v==newmenu['panels'][k],k
assert oldmenu['dynamic_chinese_values']==newmenu['dynamic_chinese_values']
video=txt(B,'video_out.v')
video=video.replace('    assign O_observe_fifo_reset=S_fifo_rst;',
 '''    // Legacy observer port name: any return discarded by this FIFO is unsafe,
    // both during reset and at FULL. This signal feeds ONLY the passive
    // latency observer; the FIFO reset, read triggers and pixels are unchanged.
    assign O_observe_fifo_reset=S_fifo_rst || S_fifo_full;''')
video=video.replace('\twire        S_fifo_emtpy;     ','\twire        S_fifo_emtpy;\n    wire        S_fifo_full;')
video=video.replace('        .full_flag  (),','        .full_flag  ( S_fifo_full        ),')
assert video==txt(R,'video_out.v'),'VIDEO_OUT_CHANGED_BEYOND_PASSIVE_FULL_OBSERVATION'
assert sha(R/'td_project/camera_to_dsi_display.sdc')==sha(B/'td_project/camera_to_dsi_display.sdc')
assert sha(R/'user_source/constraints_source/fusion_cdc.sdc')==sha(B/'user_source/constraints_source/fusion_cdc.sdc')
r={'pass':True,'baseline':str(B),'baseline_bit_sha256':m['bit_sha256'],
 'byte_exact_count':len(exact),'byte_exact':exact,'rom_path_only':paths,'changed_design_sources':changed,
 'source_sha256':current,'baseline_source_sha256':m['source_sha256'],
 'top_diff_only_passive_SW3_debug':True,'hud_change_only_SW3_K3':True,
 'video_out_only_observer_full_flag':True,
 'sw1_styles_denoise_clarity_byte_exact':True,'sw2_detector_tracking_alarm_byte_exact':True,
 'crop_camera_controls_constraints_byte_exact':True,
 'shared_transport_change':'Hold FIFO head command until corresponding AR or both AW/W channels accept; no new pixel stage.',
 'limits':'Common-ready cycle equality is separately proven. Source equality and legal protocol simulation do not establish visual board acceptance.',
 'verifier_sha256':sha(Path(__file__))}
(V/'result.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
print('V15_SCOPE_PASS',len(exact),'byte-exact files',len(paths),'ROM path-only',len(changed),'scoped RTL changes')
