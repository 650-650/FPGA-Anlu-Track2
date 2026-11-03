"""Bind V10 visual-only edits to the delivered and untouched compact V9."""
from pathlib import Path
import hashlib,json

R=Path(__file__).resolve().parents[1]
V=R/'validation'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
baseline=json.loads((V/'v9_baseline_manifest.json').read_text(encoding='utf-8'))
B=Path(baseline['baseline'])
for f,h in baseline['sha256'].items():
    assert sha(B/f)==h,('V9 reference changed',f)
old={f:h for f,h in baseline['sha256'].items() if f.startswith('user_source/')}
now={p.relative_to(R).as_posix():sha(p) for p in (R/'user_source').rglob('*') if p.is_file()}
assert not set(old)-set(now),'deleted production source'
changed=sorted(f for f in old if old[f]!=now[f])
allowed={'user_source/hdl_source/'+f for f in ['isp/stylize_v5_96.v','display_contrast.v','image_curve_rom.v']}
assert set(changed)==allowed,('unexpected final production change',changed)
added=sorted(set(now)-set(old))
assert not added,('new source needs explicit audit',added)
for name in ['display_contrast.v','image_curve_rom.v']:
    f='user_source/hdl_source/'+name
    current=(R/f).read_text(encoding='utf-8').replace(R.as_posix(),B.as_posix())
    assert current==(B/f).read_text(encoding='utf-8'),('more than ROM path change',name)
for f in ['td_project/camera_to_dsi_display.sdc','user_source/constraints_source/fusion_cdc.sdc','user_source/constraints_source/pin.adc']:
    assert sha(R/f)==sha(B/f),('clock or pin constraints changed',f)
out={'pass':True,'baseline':str(B),'original_files_and_bit_verified':len(baseline['sha256']),
     'original_bit_sha256':next(h for f,h in baseline['sha256'].items() if f.endswith('.bit')),
     'changed_sources':changed,'added_sources':added,'unchanged_source_files':len(old)-len(changed),
     'top_detection_tracking_aid_alarm_controls_sensor_ae_awb_guide_pins_clocks_logo_unchanged':True,
     'style_modes_0_2_3_dynamic_equivalence_required':True,'source_sha256':now}
(V/'v10_preservation_result.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print('V10_PRESERVATION_PASS',len(old),'V9 sources + bit untouched;',len(changed),'changes, zero additions')
