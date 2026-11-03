"""Audit saved packet vectors and split repair counts after successful sims.
Does not alter HDL, the testbench, original runner, or simulation logs.
"""
from pathlib import Path
import hashlib,json
import numpy as np
from display_v11_model import filter_rgb
R=Path(__file__).resolve().parents[1];V=R/'validation/display_v11'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
result=json.loads((V/'result.json').read_text(encoding='utf-8'))
for kind in ['source_sha256','oracle_sha256']:
 for p,h in result[kind].items():assert sha(R/p)==h,(kind,p)
fixtures={};summary={}
for name,dirname in [('small','small'),('full','full'),('uniform_full','uniform_full'),('native_production_ram','native')]:
 t=result['tests'][name];d=V/dirname
 def read(p):return np.fromiter((int(s,16) for s in p.read_text().split()),dtype=np.uint64)
 raw=read(d/'input.hex');expected=read(d/'expected.hex');assert len(raw)==t['packets']
 assert np.array_equal(raw>>24,expected>>24)
 rgb=np.stack([(raw>>16)&255,(raw>>8)&255,raw&255],axis=1).astype(np.uint8)
 ctrl=(raw>>28).astype(np.uint8);over=((raw>>27)&1).astype(bool);de=((raw>>26)&1).astype(bool);vs=((raw>>24)&1).astype(bool)
 roi=(40,64,24,44) if name=='small' else (672,720,144,176)
 out,event,details=filter_rgb(rgb,de,over,ctrl,t['h_total'],t['width'],t['height'],vs,roi,True)
 actual=(out[:,0].astype(np.uint64)<<16)|(out[:,1].astype(np.uint64)<<8)|out[:,2]
 assert np.array_equal(actual,expected&0xffffff),name
 t['vector_replacements']=int(event.sum())
 t['dpc_events']=int(details['dpc_event'].sum());t['cartoon_cleanup_events']=int(details['cartoon_event'].sum())
 t['overlapping_dpc_cleanup_events']=int((details['dpc_event']&details['cartoon_event']).sum())
 t['saved_vectors_rechecked']=True
 for p in [d/'input.hex',d/'expected.hex']:fixtures[p.relative_to(R).as_posix()]=sha(p)
 summary[name]={k:t[k] for k in ['vector_replacements','dpc_events','cartoon_cleanup_events','saved_vectors_rechecked']}
result['packet_fixture_sha256']=fixtures
result['postcheck_note']='Counts split from the same saved packets and unchanged model after all simulations. Existing source/TB/runner/logs remain unchanged; expected packet RGB and all input sidebands rechecked exactly.'
result['oracle_sha256'][Path(__file__).relative_to(R).as_posix()]=sha(Path(__file__))
temp=V/'result.postcheck.tmp';temp.write_text(json.dumps(result,indent=2),encoding='utf-8');temp.replace(V/'result.json')
for name in ['result.json','production_latency_result.json','median_proof.json','quality_result.json']:
 a=json.loads((V/name).read_text())
 for kind in ['source_sha256','oracle_sha256']:
  for p,h in a.get(kind,{}).items():assert sha(R/p)==h,(name,p)
print(json.dumps(summary,indent=2));print('DISPLAY_V11_FINAL_HASH_AND_VECTOR_AUDIT_PASS')
