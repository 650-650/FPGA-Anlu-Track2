"""Preserve the unsuccessful arithmetic epoch, then stage the reviewed ROM RTL.

This creates new test inputs only. It never relabels an old result as passing;
the pixel runner, scope checker, model certificate and TD must run afterwards.
"""
from pathlib import Path
import datetime
import hashlib
import json
import shutil

R = Path(__file__).resolve().parents[1]
C = R.parent / 'v16_integration_audit/sketch_ink_rom_candidate/stylize_v5_96.v'
S = R / 'validation/pre_rom_epoch'
STYLE = 'user_source/hdl_source/isp/stylize_v5_96.v'
OLD = '4ea577328c6af4a7696e2a3e2764b4fd961c85d2a149ba59acb6d7ab1a26d207'
NEW = '811810da14ab2e86fe921feb5a2801b4c082a95c9de7cf147d20c68a9d4d892a'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

assert sha(R / STYLE) == OLD and sha(C) == NEW
frozen = json.loads((R / 'validation/build_input_signature.json').read_text(encoding='utf-8'))
for name, digest in frozen['source_sha256'].items():
    assert sha(R / name) == digest, name
V = R / 'validation/scene_pixel_equivalence'
binding = json.loads((V / 'source_binding.json').read_text(encoding='utf-8'))
assert binding['production_sha256'][STYLE] == OLD
for name, digest in binding['production_sha256'].items():
    assert sha(R / name) == digest, name
assert not S.exists(), 'Refuse to overwrite a previous epoch'
S.mkdir()
shutil.copy2(R / STYLE, S / 'old_stylize_v5_96.v')
for name in ['build_input_signature.json', 'phy_seed2_input_signature.json',
             'phy_seed3_input_signature.json', 'stopped_congested_4ea_runs.json']:
    shutil.copy2(R / 'validation' / name, S / name)
for folder in ['scene_pixel_equivalence', 'v16_scope']:
    source = R / 'validation' / folder
    dest = S / folder
    dest.mkdir()
    for file in source.iterdir():
        if file.is_file():
            shutil.copy2(file, dest / file.name)
shutil.copytree(R / 'validation/transport_model_identity', S / 'transport_model_identity')
shutil.copytree(R / 'td_project/camera_to_dsi_display_Runs', S / 'td_runs')
previous = sha(V / 'source_binding.json')
shutil.copyfile(C, R / STYLE)
binding['production_sha256'][STYLE] = NEW
binding['epoch'] = {
    'created': datetime.datetime.now().astimezone().isoformat(),
    'reason': 'Exact C1 sketch-ink ROM substitution; all pixel tests must rerun on this source.',
    'previous_binding_sha256': previous,
    'old_style_sha256': OLD, 'new_style_sha256': NEW,
}
(V / 'source_binding.json').write_text(json.dumps(binding, ensure_ascii=False, indent=2), encoding='utf-8')
(S / 'snapshot_sha256.json').write_text(json.dumps({
    p.relative_to(S).as_posix(): sha(p) for p in S.rglob('*') if p.is_file()
}, indent=2), encoding='utf-8')
print('ROM_STAGED_NOT_YET_VERIFIED_BUILD_REQUIRED', NEW)
