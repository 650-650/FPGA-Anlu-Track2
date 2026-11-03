"""Finish the already-running build's strict export; never edit RTL or program hardware."""
from pathlib import Path
import subprocess,time,sys,argparse
R=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--run',choices=['phy_1','phy_seed2'],default='phy_1')
run=parser.parse_args().run
log=R/'td_project/camera_to_dsi_display_Runs'/run/'build_console.log'
out=R/'validation'/('release_export.log' if run=='phy_1' else 'release_seed2_export.log')
print('WAITING_FOR_FINAL_PHY_STAGE',flush=True)
while True:
    s=log.read_text(encoding='utf-8',errors='replace') if log.is_file() else ''
    error_log=log.with_name('build_stderr.log')
    errors=error_log.read_text(encoding='utf-8',errors='replace') if error_log.is_file() else ''
    if 'FUSION_BUILD_STAGE_PASS' in s:break
    if 'FUSION_BUILD_ERROR:' in s+errors:raise RuntimeError('TD build failed; no export')
    time.sleep(5)
with out.open('w',encoding='utf-8') as f:
    for tool in ['finalize_v13_delivery.py','write_v13_docs.py']:
        command=[sys.executable,str(R/'tools'/tool)]
        if tool=='finalize_v13_delivery.py':command+=['--run',run]
        p=subprocess.run(command,cwd=R,stdout=f,stderr=subprocess.STDOUT)
        f.flush()
        if p.returncode:
            print(out.read_text(encoding='utf-8'),flush=True)
            raise SystemExit(p.returncode)
print(out.read_text(encoding='utf-8'),flush=True)
print('V13_STRICT_EXPORT_AND_DOCS_COMPLETE',flush=True)
