"""Isolated synthesis only; compare the two edge kernels on one device."""
from pathlib import Path
import re,subprocess,json,sys
sys.stdout.reconfigure(encoding='utf-8')
R=Path(__file__).resolve().parents[1];V=R/'validation/edge_v7/probe';V.mkdir(parents=True,exist_ok=True)
TD=Path(r'D:\anlu\TD_6.2.1_Engineer_6.2.168.116\bin\td_commands_prompt.exe')
base=R.parent/'07_stylize_flame_fusion_v6_visual_aid'
project=(R/'td_project/camera_to_dsi_display.al').read_text(encoding='utf-8');results={}
for name,source in [('v6',base/'user_source/hdl_source/isp/edge_detect_96.v'),('v7',R/'user_source/hdl_source/isp/edge_detect_96.v')]:
 d=V/name;d.mkdir(exist_ok=True)
 wrapper='''module edge_probe(input clk,rst_n,v,u,l,input [95:0] rgb,output ov,ou,ol,output [3:0] edge_bits);
 wire [95:0] data;
 edge_detect_96 dut(.I_clk(clk),.I_rst_n(rst_n),.I_tvalid(v),.I_tuser(u),.I_tlast(l),.I_tdata(rgb),.I_tready(1'b1),
 .O_tvalid(ov),.O_tuser(ou),.O_tlast(ol),.O_tdata(data));
 assign edge_bits={data[95],data[71],data[47],data[23]};endmodule
 '''
 (d/'wrapper.v').write_text(wrapper,encoding='utf-8')
 prj=re.sub(r'<Source_Files>.*?</Source_Files>',f'''<Source_Files><Verilog><File Path="{source.as_posix()}"><FileInfo>
 <Attr Name="UsedInSyn" Val="true"/><Attr Name="UsedInP&amp;R" Val="true"/>
 <Attr Name="BelongTo" Val="design_1"/><Attr Name="CompileOrder" Val="1"/>
 </FileInfo></File><File Path="wrapper.v"><FileInfo><Attr Name="UsedInSyn" Val="true"/>
 <Attr Name="BelongTo" Val="design_1"/><Attr Name="CompileOrder" Val="2"/></FileInfo></File></Verilog></Source_Files>''',project,flags=re.S)
 prj=re.sub(r' Path="[^"]+"','',prj,count=1)
 (d/'camera_to_dsi_display.prj').write_text(prj,encoding='utf-8')
 (d/'probe.tcl').write_text('''if {[catch {
 import_device ph1_35p.db -package PH1P35MDG324 -speed 3
 open_project camera_to_dsi_display.prj
 elaborate -top edge_probe
 optimize_rtl
 optimize_gate -packarea probe.area
 } result]} {puts stderr "PROBE_ERROR: $result";exit 1}
 puts "PROBE_PASS"
 exit 0
 ''',encoding='utf-8')
 p=subprocess.run([str(TD),'probe.tcl'],cwd=d,capture_output=True,text=True,timeout=180)
 log=p.stdout+p.stderr;(d/'probe.log').write_text(log,encoding='utf-8');assert p.returncode==0 and 'PROBE_PASS' in log,log[-1800:]
 area=(d/'probe.area').read_text(encoding='utf-8');metrics={}
 for key in ['lut6','slice','slice reg','eram','dsp']:
  m=re.search(r'^\s*#'+re.escape(key)+r'\*?\s+(\d+)',area,re.M);assert m,(key,area[:1000]);metrics[key]=int(m[1])
 results[name]=metrics;print(name,metrics,flush=True)
(V/'result.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
