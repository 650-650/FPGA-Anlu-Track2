"""Actual old/new MC FIFO and DDR wrapper RTL; only encrypted ddr2 is modeled.

Checks real PAXI acceptance, independent AW/AR/W backpressure, exactly-once
address/data queues, old lost-read counterexample, common-ready cycle equality,
delayed calibration, and reset during a partially accepted write. Not a physical
DDR/PHY or board acceptance test.
"""
from pathlib import Path
import hashlib,json,subprocess,time,re
R=Path(__file__).resolve().parents[1]
OLD=R.parent/'07_stylize_flame_fusion_v14_latency_provenance'
V=R/'validation/ddr_handshake';V.mkdir(parents=True,exist_ok=True)
H=R/'user_source/hdl_source'
old_files=[OLD/'user_source/hdl_source/mc_to_user_interface.v',OLD/'user_source/hdl_source/ph1p35_ddr/ph1p35_324_ddr_wrapper.v']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
old_hash={str(p):sha(p) for p in old_files}
legacy=[]
for p in old_files:
    q=V/('legacy_'+p.name)
    text=p.read_text(encoding='utf-8').replace('module '+p.stem+' (','module legacy_'+p.stem+' (')
    assert 'module legacy_'+p.stem in text
    q.write_text(text,encoding='utf-8');legacy.append(q)
files=[R/'tools/ddr_handshake_tb.sv',R/'tools/ddr2_handshake_stub.sv',H/'mc_to_user_interface.v',H/'ph1p35_ddr/ph1p35_324_ddr_wrapper.v',
       R/'user_source/ip_source/w155_d512_fifo/w155_d512_fifo.v',R/'user_source/ip_source/w155_d512_fifo/soft_fifo_al_f58e8b3e1f3d.v',*legacy]
before={p.relative_to(R).as_posix():sha(p) for p in files}
start=time.monotonic()
cmd=['iverilog','-g2012','-s','handshake_tb','-o',str(V/'sim.vvp'),*map(str,files)]
p=subprocess.run(cmd,capture_output=True,text=True)
(V/'compile.log').write_text(p.stdout+p.stderr,encoding='utf-8')
assert p.returncode==0,p.stderr
p=subprocess.run(['vvp','-i',str(V/'sim.vvp')],capture_output=True,text=True,timeout=90)
(V/'run.log').write_text(p.stdout+p.stderr,encoding='utf-8')
print(p.stdout+p.stderr,flush=True)
after={q.relative_to(R).as_posix():sha(q) for q in files}
passed=p.returncode==0 and 'DDR_HANDSHAKE_PASS cases=9' in p.stdout and before==after
result={'passed':passed,'returncode':p.returncode,'seconds':round(time.monotonic()-start,3),
        'scope':__doc__,'cases':re.findall(r'CASE_PASS (.*)',p.stdout),'source_sha256':before,
        'sources_still_current':before==after,'original_v14_sha256':old_hash,
        'original_v14_unchanged':old_hash=={str(q):sha(q) for q in old_files},
        'verifier_sha256':sha(Path(__file__)),'compile_command':cmd,'simulation_clock_period_ns':15}
(V/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
assert passed and result['original_v14_unchanged']
