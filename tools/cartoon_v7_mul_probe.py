"""Small arithmetic-only TD probe; does not build or alter the system project."""
from pathlib import Path
import json,re,subprocess,sys
sys.stdout.reconfigure(encoding='utf-8')
R=Path(__file__).resolve().parents[1];V=R/'validation/cartoon_v7/mul_probe';V.mkdir(exist_ok=True)
td=Path(r'D:\anlu\TD_6.2.1_Engineer_6.2.168.116\bin\td_commands_prompt.exe')
template=(R/'td_project/camera_to_dsi_display.al').read_text(encoding='utf-8');results={}
for kind in ['shift_add','multiply']:
 p=V/kind;p.mkdir(exist_ok=True)
 expression='mul8(a[31-8*k-:8],b[31-8*k-:8])' if kind=='shift_add' else 'a[31-8*k-:8]*b[31-8*k-:8]'
 source='''module mul_probe(input clk,en,input[31:0]a,b,output reg[63:0]q);
 function[15:0]mul8;input[7:0]a,b;integer n;begin mul8=0;for(n=0;n<8;n=n+1)if(b[n])mul8=mul8+({8'd0,a}<<n);end endfunction
 integer k;always@(posedge clk)if(en)for(k=0;k<4;k=k+1)q[63-16*k-:16]<='''+expression+''';endmodule\n'''
 (p/'mul_probe.v').write_text(source,encoding='utf-8')
 project=re.sub(r'<Source_Files>.*?</Source_Files>','''<Source_Files><Verilog><File Path="mul_probe.v"><FileInfo><Attr Name="UsedInSyn" Val="true"/><Attr Name="UsedInP&amp;R" Val="true"/><Attr Name="BelongTo" Val="design_1"/><Attr Name="CompileOrder" Val="1"/></FileInfo></File></Verilog></Source_Files>''',template,flags=re.S)
 project=re.sub(r' Path="[^"]+"','',project,count=1)
 (p/'camera_to_dsi_display.prj').write_text(project,encoding='utf-8')
 (p/'probe.tcl').write_text('''if {[catch {
import_device ph1_35p.db -package PH1P35MDG324 -speed 3
open_project camera_to_dsi_display.prj
elaborate -top mul_probe
optimize_rtl
optimize_gate -packarea probe.area
} result]} {puts stderr "PROBE_ERROR: $result";exit 1}
puts "PROBE_PASS"
exit 0
''',encoding='ascii')
 proc=subprocess.run([str(td),'probe.tcl'],cwd=p,capture_output=True,text=True,timeout=180)
 log=proc.stdout+proc.stderr;(p/'probe.log').write_text(log,encoding='utf-8')
 assert proc.returncode==0 and 'PROBE_PASS' in log,(kind,log[-1800:])
 area=(p/'probe.area').read_text(encoding='utf-8');fields={}
 for f in ['lut6','slice','slice reg','dsp']:
  m=re.search(r'^\s*#'+re.escape(f)+r'\*?\s+(\d+)',area,re.M);fields[f]=int(m[1]) if m else None
 results[kind]=fields;print(kind,fields,flush=True)
(V/'result.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
