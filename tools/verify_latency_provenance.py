"""Timestamp provenance validity, separately from RAW image-quality counters.

Three former RAW-quality rejection fixtures still have a full, ordered DDR
frame and the same first-pixel origin. They must report the independently
measured age. All transport/metadata/overwrite/underflow rejections remain.
"""
from pathlib import Path
import importlib.util,json,hashlib,subprocess,re
R=Path(__file__).resolve().parents[1];H=R/'user_source/hdl_source'
V=R/'validation/latency_provenance_unit';V.mkdir(parents=True,exist_ok=True)
s=importlib.util.spec_from_file_location('old_fixture',R/'tools/latency_v12_unit_verify.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
t=m.BENCH
changes={
 'source_frame(0,RG-1,DW,0);show(0,1,0,0,0);case_pass("partial_RAW_invalid")':'source_frame(0,RG-1,DW,0);show(0,1,1,0,0);case_pass("RAW_count_short_full_DDR_has_same_first_pixel_time")',
 'source_frame(0,RG+1,DW,0);show(0,1,0,0,0);case_pass("extra_RAW_invalid")':'source_frame(0,RG+1,DW,0);show(0,1,1,0,0);case_pass("RAW_count_extra_full_DDR_has_same_first_pixel_time")',
 'source_frame(0,RG,DW,1);show(0,1,0,0,0);case_pass("RAW_error_invalid")':'source_frame(0,RG,DW,1);show(0,1,1,0,0);case_pass("RAW_quality_error_does_not_change_timestamp_origin")'}
for a,b in changes.items():assert t.count(a)==1;t=t.replace(a,b)
extra='''
 reset_all;source_frame(0,0,DW,0);show(0,1,0,0,0);case_pass("full_DDR_without_RAW_origin_stays_invalid");
 reset_all;source_frame(0,RG-1,DW-1,0);show(0,1,0,0,0);case_pass("RAW_short_and_DDR_short_stays_invalid");
'''
mark=' reset_all;source_frame(0,RG,DW-1,0);'
assert t.count(mark)==1;t=t.replace(mark,extra+mark)
tb=V/'tb.sv';tb.write_text(t,encoding='utf-8')
iv=Path(r'D:\anlu\iverilog\bin\iverilog.exe');files=[H/'frame_latency_monitor.v',H/'fusion_controls.v']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
sources={p.relative_to(R).as_posix():sha(p) for p in files}
cmd=[str(iv),'-g2012','-s','latency_v12_unit_tb','-o',str(V/'sim.vvp'),str(tb),*map(str,files)]
p=subprocess.run(cmd,capture_output=True,text=True);(V/'compile.log').write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0,p.stderr
cases=checks=0
for arg in ['', '+collision_complete','+collision_short','+collision_empty']:
 p=subprocess.run([str(iv.with_name('vvp.exe')),str(V/'sim.vvp'),*([arg] if arg else [])],capture_output=True,text=True)
 (V/(arg.strip('+') or 'main')).with_suffix('.log').write_text(p.stdout+p.stderr,encoding='utf-8')
 print(p.stdout[-5000:],flush=True);assert p.returncode==0
 match=re.search(r'LATENCY_V12_UNIT_PASS cases=(\d+) checks=(\d+)',p.stdout);assert match
 cases+=int(match[1]);checks+=int(match[2])
assert sources=={p.relative_to(R).as_posix():sha(p) for p in files}
report={'pass':True,'cases':cases,'checks':checks,'source_sha256':sources,'testbench_sha256':sha(tb),'verifier_sha256':sha(Path(__file__)),
 'scope':__doc__,'intentional_changes':changes,'source_unchanged':True,
 'measurement_valid_means':'Known first RAW-group timestamp is tied to the actual full ordered DDR slot generation, complete read and final HDMI frame. Does not certify RAW payload quality.'}
(V/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('PROVENANCE_UNIT_PASS',cases,checks)
