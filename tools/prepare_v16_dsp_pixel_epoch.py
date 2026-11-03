"""Start a new pixel verification epoch after the intentional, exact gain rewrite."""
from pathlib import Path
import json,hashlib,shutil,datetime
R=Path(__file__).resolve().parents[1];V=R/'validation/scene_pixel_equivalence';S=R/'validation/pre_dsp_pixel_epoch'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
path=V/'source_binding.json';m=json.loads(path.read_text(encoding='utf-8'))
rel='user_source/hdl_source/isp/stylize_v5_96.v';old='72a26a350f1c7089bd49503378c0d04ec3b92d7fd808563b13d548915b4009aa';new='4ea577328c6af4a7696e2a3e2764b4fd961c85d2a149ba59acb6d7ab1a26d207'
assert m['production_sha256'][rel]==old and sha(R/rel)==new
for p,h in m['production_sha256'].items():
 if p!=rel:assert sha(R/p)==h,p
assert not S.exists();S.mkdir()
for p in V.iterdir():
 if p.is_file() and (p.name in ['source_binding.json','result.json'] or p.suffix in ('.log','.do','.py','.sv','.v')):shutil.copy2(p,S/p.name)
previous=sha(path);m['production_sha256'][rel]=new
m['epoch']={'created':datetime.datetime.now().astimezone().isoformat(),'reason':'Exact dynamic sketch multiplication using idle DSP; rerun all pixel tests on current production, no old result relabeling.','previous_binding_sha256':previous,'old_style_sha256':old,'new_style_sha256':new}
path.write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8')
print('NEW_DSP_PIXEL_TEST_INPUTS_FROZEN_RUN_REQUIRED')
