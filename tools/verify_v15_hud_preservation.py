"""Compare newly simulated HUD pixels with delivered V14, except SW3 K3."""
from pathlib import Path
import json,hashlib
R=Path(__file__).resolve().parents[1];B=R.with_name('07_stylize_flame_fusion_v14_latency_provenance')
N=R/'validation/chinese_hud';O=B/'validation/chinese_hud';V=R/'validation/hud_preservation';V.mkdir(parents=True,exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
nc=json.loads((N/'cases.json').read_text(encoding='utf-8'));oc=json.loads((O/'cases.json').read_text(encoding='utf-8'))
assert nc==oc
exact=[];changed=[]
for case in nc:
 name=case['name'];p=(case['control']>>3)&31;p=0 if p<4 else p
 old=O/(name+'.hex');new=N/(name+'.hex')
 assert old.is_file() and new.is_file()
 if p==14:
  assert old.read_bytes()!=new.read_bytes();changed.append(name)
 else:
  assert old.read_bytes()==new.read_bytes(),('HUD_PIXEL_REGRESSION',name)
  exact.append(name)
r={'pass':True,'byte_identical_simulated_cases':exact,'only_changed_cases':changed,
 'unchanged_pixels':len(exact)*1280*180,'scope':__doc__,
 'old_result_sha256':sha(O/'result.json'),'new_result_sha256':sha(N/'result.json'),
 'verifier_sha256':sha(Path(__file__))}
(V/'result.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
print('HUD_PRESERVATION_PASS',len(exact),'identical cases;',changed,'SW3 K3 changed')
