from pathlib import Path
import hashlib,json,datetime
R=Path(__file__).resolve().parents[1]
paths=[p for p in (R/'user_source').rglob('*') if p.is_file()]
paths += [R/'td_project/camera_to_dsi_display.al',R/'td_project/camera_to_dsi_display.sdc',R/'build.ps1',R/'tools/prepare_project.py',R/'tools/build_stage.tcl']
s={'started':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
   'source_sha256':{p.relative_to(R).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
(R/'validation/build_input_signature.json').write_text(json.dumps(s,indent=2),encoding='utf-8')
print('FROZEN',len(paths),s['started'])
