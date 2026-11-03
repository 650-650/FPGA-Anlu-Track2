"""Use the vendor's confirmed placement seed option with unchanged frozen RTL."""
from pathlib import Path
import json,hashlib,datetime,subprocess,re,argparse,shutil
ap=argparse.ArgumentParser();ap.add_argument('--seed',type=int,choices=[2,3],default=2);args=ap.parse_args();seed=args.seed
R=Path(__file__).resolve().parents[1];P=R/f'td_project/camera_to_dsi_display_Runs/phy_seed{seed}'
if seed==3 and not P.exists():
 P.mkdir()
 src=R/'td_project/camera_to_dsi_display_Runs/phy_seed2'
 for name in ['settings.cfg','camera_to_dsi_display.tcl','camera_to_dsi_display.prj']:shutil.copy2(src/name,P/name)
 t=(P/'camera_to_dsi_display.tcl').read_text(encoding='utf-8').replace('set_param place seed 2','set_param place seed 3').replace('get_param place seed] != 2','get_param place seed] != 3').replace('SEED2_PLACE_PARAMETER_CONFIRMED 2','SEED3_PLACE_PARAMETER_CONFIRMED 3')
 (P/'camera_to_dsi_display.tcl').write_text(t,encoding='utf-8',newline='\n')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
f=R/'validation/build_input_signature.json';frozen=json.loads(f.read_text(encoding='utf-8'))
for k,v in frozen['source_sha256'].items():assert sha(R/k)==v,('FROZEN_SOURCE_CHANGED',k)
gate=R/'td_project/camera_to_dsi_display_Runs/syn_1/camera_to_dsi_display_gate.db'
log=gate.parent/'build_console.log';assert gate.is_file() and 'FUSION_BUILD_STAGE_PASS' in log.read_text(encoding='utf-8',errors='replace')
tcl=(P/'camera_to_dsi_display.tcl').read_text(encoding='utf-8');assert f'set_param place seed {seed}' in tcl and f'SEED{seed}_PLACE_PARAMETER_CONFIRMED {seed}' in tcl
signature={'run':f'phy_seed{seed}','seed':seed,'started':datetime.datetime.now().astimezone().isoformat(),
 'source_sha256':frozen['source_sha256'],'original_build_signature_sha256':sha(f),'gate_db_sha256':sha(gate),
 'config_sha256':{n:sha(P/n) for n in ['settings.cfg','camera_to_dsi_display.tcl','camera_to_dsi_display.prj']}}
(R/f'validation/phy_seed{seed}_input_signature.json').write_text(json.dumps(signature,indent=2),encoding='utf-8')
print(f'SEED{seed}_RUNNING_NO_RTL_CHANGE',signature['started'],flush=True)
with (P/'build_console.log').open('w',encoding='utf-8') as out:
 c=subprocess.run([r'D:\anlu\TD_6.2.1_Engineer_6.2.168.116\bin\td_commands_prompt.exe',(R/'tools/build_stage.tcl').as_posix()],cwd=P,stdout=out,stderr=subprocess.STDOUT)
s=(P/'build_console.log').read_text(encoding='utf-8',errors='replace')
assert c.returncode==0 and 'FUSION_BUILD_STAGE_PASS' in s and not re.search(r'(?mi)\bERROR\s*:',s),s[-2000:]
print(f'SEED{seed}_STAGE_PASS_CHECK_FINAL_TIMING',flush=True)
