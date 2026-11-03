"""Bind final unchanged-clear decision and independently check baseline outputs."""
from pathlib import Path
import hashlib,importlib.util,json
import numpy as np
from display_v10_model import filter_rgb
R=Path(__file__).resolve().parents[1];V=R/'validation/display_v10';BASE=R.parent/'07_stylize_flame_fusion_v9_detail_motion_compact'
spec=importlib.util.spec_from_file_location('compact_clear_reference',BASE/'tools/display_v9_model.py')
ref=importlib.util.module_from_spec(spec);spec.loader.exec_module(ref)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
source=R/'user_source/hdl_source/display_denoise_v9.v';baseline=BASE/'user_source/hdl_source/display_denoise_v9.v'
assert source.read_bytes()==baseline.read_bytes()
candidates=json.loads((V/'candidates.json').read_text(encoding='utf-8'))
for name,h in candidates['source_sha256'].items():assert sha(R/name)==h
for name,h in candidates['oracle_sha256'].items():assert sha(R/name)==h
tests={};rng=np.random.default_rng(20261101)
for ht,n in [(128,50000),(1650,120000)]:
 tick=np.arange(n);x=tick%ht;y=tick//ht
 de=(x<ht*3//4)&((y%24)<20);over=de&(rng.random(n)<.015)
 mode=np.array([0,0x20,0x28,0x30,0x38,0x40,0x48,0x50,0x58,0x60,0xe0],np.uint8)
 control=mode[(y//7)%len(mode)]|rng.integers(0,8,n,dtype=np.uint8)
 rgb=np.clip(64+rng.normal(0,8,(n,1))+rng.normal(0,2,(n,3)),0,255).round().astype(np.uint8)
 actual=filter_rgb(rgb,de,over,control,ht);expected=ref.filter_rgb(rgb,de,over,control,ht)
 assert np.array_equal(actual,expected)
 tests[f'compact_v9_model_equality_ht{ht}']={'pass':True,'packets':n,'changed_active':int(np.any(actual!=rgb,axis=1)[de].sum())}
manifest=json.loads((BASE/'output/build_manifest.json').read_text(encoding='utf-8'))
noise=[]
for block in [1,2,4]:
 rows=[a for a in candidates['noise'] if a['block']==block and a['sigma']==8 and a['mean']==64]
 noise.append({'block':block,'sigma':8,'mean':64,'v8_std_ratio':float(np.mean([a['v8'] for a in rows])),
               'v9_std_ratio':float(np.mean([a['v9'] for a in rows])),'v10_std_ratio':float(np.mean([a['v9'] for a in rows]))})
result={'decision':'retain compact V9 clear-only centered cross32/16 cap6; candidate noise improvements rejected for real-detail/halo regressions',
 'production_changed_from_compact_v9':False,'tests':tests,'compact_v9_manifest_resources':manifest['resources'],
 'compact_v9_timing_ns':manifest['timing_ns'],'clear_module_structural_resource_delta':{'eram':0,'dsp':0,'registers':0,'arithmetic':0},
 'before_tone_noise_summary':noise,
 'scope':'Known-truth software fixtures, independent baseline-model equality and exact source identity; no claim of clear noise improvement over V9 or board validation. Full packet RTL/native RAM checks are in result.json.',
 'source_sha256':{source.relative_to(R).as_posix():sha(source)},
 'oracle_sha256':{p.relative_to(R).as_posix():sha(p) for p in [Path(__file__),R/'tools/display_v10_model.py',R/'tools/display_v10_candidates.py',R/'tools/display_v9_model.py',R/'tools/denoise_v8_model.py']},
 'candidate_result_sha256':sha(V/'candidates.json'),
 'compact_v9_baseline':{'project':BASE.as_posix(),'display_source_sha256':sha(baseline),'model_sha256':sha(BASE/'tools/display_v9_model.py'),'manifest_sha256':sha(BASE/'output/build_manifest.json')}}
(V/'quality_result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
report=['# V10 clear-filter decision and verification', '',result['decision'], '',
        'The user accepted V9 clear sharpness and reduced dark ghosts. Every stronger candidate tested here damaged either weak two-pixel RGB diagonals, genuine low-contrast texture, or microtextured edges. The production clear module is therefore byte-identical to the compact V9 baseline. The main cartoon changes are outside this report.', '',
        '| sigma8, mean64 fixture | V8 noise STD ratio | V9 | V10 |', '|---|---:|---:|---:|']
for a in noise:report.append(f"| {a['block']}x{a['block']} | {a['v8_std_ratio']:.4f} | {a['v9_std_ratio']:.4f} | {a['v10_std_ratio']:.4f} |")
report += ['', 'Rejected flat boost: 2x2 noise STD ratio improves 0.7924 to 0.7213, but 8-level two-pixel colored diagonal contrast retained falls 0.75 to 0.50, and isotropic period-6/amplitude-8 signal retention falls 0.8571 to 0.7389. A one-pixel-line or step-only quality suite would have missed this.', '',
           'Threshold36/40 with cap6 gains only about 1-2 percent in the selected noise fixtures and deepens the 32-level textured-edge dark residual from -1 to -3/-5. Full 3x3 candidates gain more noise suppression but lose thin vertical RGB contrast and require extra gates. None is adopted.', '',
           'Budget from the compact V9 manifest: Slice20977/21216 (239 remaining), LUT20121, ERAM100/108, DSP32/40; setup/hold WNS +0.090/+0.020ns. This unchanged clear module adds no logic, registers, DSP or ERAM. Other V10 changes still require the parent whole-project build.', '',
           'Fresh V10 tests use sample_edge_lag1655 and registered_stages1656. All pages and overlay remain synchronized, and protected modes bypass this clear filter exactly. Software/native-RAM checks do not prove camera-to-panel behavior or observed hardware improvement.']
(V/'quality_report.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
print(json.dumps({'source_identical_compact_v9':True,'model_equality_packets':sum(a['packets'] for a in tests.values()),'decision':result['decision'],'noise':noise},indent=2))
