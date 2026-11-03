"""Area tradeoff for the exact registered majority helper only."""
from pathlib import Path
import json,re,subprocess,sys
sys.stdout.reconfigure(encoding='utf-8')
R=Path(__file__).resolve().parents[1];V=R/'validation/cartoon_v7/median_probe';V.mkdir(exist_ok=True)
td=Path(r'D:\anlu\TD_6.2.1_Engineer_6.2.168.116\bin\td_commands_prompt.exe')
template=(R/'td_project/camera_to_dsi_display.al').read_text(encoding='utf-8');results={}
current=(R/'user_source/hdl_source/isp/stylize_v5_96.v').read_text(encoding='utf-8')
original=(R.parent/'07_stylize_flame_fusion_v5_auto_color/user_source/hdl_source/isp/stylize_v5_96.v').read_text(encoding='utf-8')
for kind,s in [('logic',current),('eram',original)]:
 p=V/kind;p.mkdir(exist_ok=True)
 source=s[s.index('module median4_eram'):].replace((R.parent/'07_stylize_flame_fusion_v5_auto_color').as_posix(),R.as_posix())
 (p/'median_probe.v').write_text(source,encoding='utf-8')
 project=re.sub(r'<Source_Files>.*?</Source_Files>','''<Source_Files><Verilog><File Path="median_probe.v"><FileInfo><Attr Name="UsedInSyn" Val="true"/><Attr Name="UsedInP&amp;R" Val="true"/><Attr Name="BelongTo" Val="design_1"/><Attr Name="CompileOrder" Val="1"/></FileInfo></File></Verilog></Source_Files>''',template,flags=re.S)
 project=re.sub(r' Path="[^"]+"','',project,count=1)
 (p/'camera_to_dsi_display.prj').write_text(project,encoding='utf-8')
 (p/'probe.tcl').write_text('''if {[catch {
import_device ph1_35p.db -package PH1P35MDG324 -speed 3
open_project camera_to_dsi_display.prj
elaborate -top median4_eram
optimize_rtl
optimize_gate -packarea probe.area
} result]} {puts stderr "PROBE_ERROR: $result";exit 1}
puts "PROBE_PASS"
exit 0
''',encoding='ascii')
 proc=subprocess.run([str(td),'probe.tcl'],cwd=p,capture_output=True,text=True,timeout=180)
 log=proc.stdout+proc.stderr;(p/'probe.log').write_text(log,encoding='utf-8');assert proc.returncode==0 and 'PROBE_PASS' in log,(kind,log[-1800:])
 area=(p/'probe.area').read_text(encoding='utf-8');fields={}
 for f in ['lut6','slice','slice reg','eram','dsp']:
  m=re.search(r'^\s*#'+re.escape(f)+r'\*?\s+(\d+)',area,re.M);fields[f]=int(m[1]) if m else None
 results[kind]=fields;print(kind,fields,flush=True)
(V/'result.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
