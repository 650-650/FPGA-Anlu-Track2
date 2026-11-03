"""Protect the user's SW1/SW2 effects against the tested V13 delivery."""
from pathlib import Path
import re,json,hashlib
R=Path(__file__).resolve().parents[1];B=R.with_name('07_stylize_flame_fusion_v13_latency_chinese_timing');V=R/'validation/v14_scope';V.mkdir(parents=True,exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((B/'output/build_manifest.json').read_text(encoding='utf-8'))
assert manifest['bit_sha256']=='b2aeca3857a29cb0f7dc997fa08a16ac71d823047699fc5c56ee2b390799dfe0'
assert sha(B/'output'/manifest['bitstream'])==manifest['bit_sha256']
for rel,h in manifest['source_sha256'].items():assert sha(B/rel)==h,('V13 baseline modified',rel)
current={p.relative_to(R).as_posix():sha(p) for p in (R/'user_source').rglob('*') if p.is_file()}
assert set(current)==set(manifest['source_sha256'])
rom={'user_source/hdl_source/image_curve_rom.v','user_source/hdl_source/display_contrast.v'}
norm=lambda s:re.sub(r'"[^"\r\n]*/(curve_srgb|curve_gain|curve_gain_scaled|median_majority|display_tone)\.dat"',lambda m:'"@ROM/'+m[1]+'.dat"',s)
exact=[];paths=[];changed=[]
for rel,h in current.items():
 if h==manifest['source_sha256'][rel]:exact.append(rel)
 elif rel in rom:
  assert norm((R/rel).read_text(encoding='utf-8'))==norm((B/rel).read_text(encoding='utf-8'));paths.append(rel)
 else:changed.append(rel)
assert changed==['user_source/hdl_source/frame_latency_monitor.v'],changed
assert sha(R/'td_project/camera_to_dsi_display.sdc')==sha(B/'td_project/camera_to_dsi_display.sdc')
assert 'user_source/hdl_source/design_top_wrapper.v' in exact
old=(B/'user_source/hdl_source/frame_latency_monitor.v').read_text(encoding='utf-8');new=(R/'user_source/hdl_source/frame_latency_monitor.v').read_text(encoding='utf-8')
assert old[old.index('module frame_latency_monitor #('):old.index('    localparam integer RAW_GROUPS')]==new[new.index('module frame_latency_monitor #('):new.index('    localparam integer RAW_GROUPS')]
top=(R/'user_source/hdl_source/design_top_wrapper.v').read_text(encoding='utf-8')
a=top.index('    wire [31:0] latency_us;');b=top.index('    wire [15:0] xb,yb;',a)
outside=top[:a]+top[b:]
for wire in ['latency_us','latency_frame_id','latency_valid','latency_repeat','latency_skip','latency_status']:
 assert not re.search(r'\b'+wire+r'\b',outside),wire
result={'pass':True,'baseline':str(B),'baseline_bit_sha256':manifest['bit_sha256'],'byte_exact_count':len(exact),'rom_path_only':paths,'changed_design_sources':changed,
 'top_byte_exact':True,'sw1_style_and_display_byte_exact':True,'sw2_detection_tracking_audio_byte_exact':True,
 'controls_camera_crop_and_constraints_byte_exact':True,'observer_outputs_only_to_hud_snapshot':True,
 'source_sha256':current,'baseline_source_sha256':manifest['source_sha256'],'primary_sdc_sha256':sha(R/'td_project/camera_to_dsi_display.sdc'),'verifier_sha256':sha(Path(__file__)),
 'scope':'Source protection; all SW1/SW2 processing and routing/control paths unchanged. Not a claim of new physical board observation.'}
(V/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print('V14_SW1_SW2_SCOPE_PASS',len(exact),paths,changed)
