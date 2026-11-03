"""Comparable isolated style-core TD area probe; does not build whole system."""
from pathlib import Path
import json,re,subprocess,sys,hashlib
sys.stdout.reconfigure(encoding='utf-8')
R=Path(__file__).resolve().parents[1];V=R/'validation/cartoon_v10/area_probe';V.mkdir(parents=True,exist_ok=True)
td=Path(r'D:\anlu\TD_6.2.1_Engineer_6.2.168.116\bin\td_commands_prompt.exe')
template=(R/'td_project/camera_to_dsi_display.al').read_text(encoding='utf-8');results={}
for kind,base in [('v9',R.parent/'07_stylize_flame_fusion_v9_detail_motion_compact'),('v10',R)]:
 p=V/kind;p.mkdir(exist_ok=True)
 for f in ['stylize_v5_96.v','style_guide_v8.v']:(p/f).write_bytes((base/'user_source/hdl_source/isp'/f).read_bytes())
 (p/'probe_top.v').write_text("""module cartoon_area_wrapper(input clk,rst_n,v,u,l,ready,input [1:0] mode,input [23:0] pixel,output [95:0] q,output ov,ou,ol,orr);
 reg [95:0] data;always @(posedge clk)data<={data[71:0],pixel};
 stylize_v5_96 dut(.I_clk(clk),.I_rst_n(rst_n),.I_mode(mode),.I_tvalid(v),.I_tuser(u),.I_tlast(l),.I_tready(ready),.I_tdata(data),.I_edge_data(96'd0),.O_tdata(q),.O_tvalid(ov),.O_tuser(ou),.O_tlast(ol),.O_tready(orr));
 endmodule
""",encoding='ascii')
 entries=''.join(f'<File Path="{f}"><FileInfo><Attr Name="UsedInSyn" Val="true"/><Attr Name="UsedInP&amp;R" Val="true"/><Attr Name="BelongTo" Val="design_1"/><Attr Name="CompileOrder" Val="{i+1}"/></FileInfo></File>' for i,f in enumerate(['stylize_v5_96.v','style_guide_v8.v','probe_top.v']))
 project=re.sub(r'<Source_Files>.*?</Source_Files>','<Source_Files><Verilog>'+entries+'</Verilog></Source_Files>',template,flags=re.S)
 project=re.sub(r' Path="[^"]+"','',project,count=1);(p/'camera_to_dsi_display.prj').write_text(project,encoding='utf-8')
 (p/'probe.tcl').write_text('''if {[catch {
import_device ph1_35p.db -package PH1P35MDG324 -speed 3
open_project camera_to_dsi_display.prj
elaborate -top cartoon_area_wrapper
optimize_rtl
optimize_gate -packarea probe.area
} result]} {puts stderr "PROBE_ERROR: $result";exit 1}
puts "PROBE_PASS"
exit 0
''',encoding='ascii')
 proc=subprocess.run([str(td),'probe.tcl'],cwd=p,capture_output=True,text=True,timeout=360)
 log=proc.stdout+proc.stderr;(p/'probe.log').write_text(log,encoding='utf-8');assert proc.returncode==0 and 'PROBE_PASS' in log,(kind,proc.returncode,log[-1800:])
 area=(p/'probe.area').read_text(encoding='utf-8');fields={}
 for f in ['lut6','slice','slice reg','eram','dsp']:
  m=re.search(r'^\s*#'+re.escape(f)+r'\*?\s+(\d+)',area,re.M);fields[f]=int(m[1]) if m else None
 fields['source_sha256']=hashlib.sha256((p/'stylize_v5_96.v').read_bytes()).hexdigest();results[kind]=fields;print(kind,fields,flush=True)
(V/'result.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
