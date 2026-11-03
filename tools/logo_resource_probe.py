from pathlib import Path
import re,subprocess,json,sys
sys.stdout.reconfigure(encoding='utf-8')
R=Path(__file__).resolve().parents[1];V=R/'validation/logo_resource_probe';V.mkdir(exist_ok=True)
td=Path(r'D:\anlu\TD_6.2.1_Engineer_6.2.168.116\bin\td_commands_prompt.exe')
original=(R/'user_source/hdl_source/anlogic_logo_rom.v').read_text(encoding='utf-8')
project=(R/'td_project/camera_to_dsi_display.al').read_text(encoding='utf-8')
result={}
for kind in ['hierarchy_split']:
    directory=V/kind;directory.mkdir(exist_ok=True)
    source=original.replace('module anlogic_logo_rom(', 'module logo_probe(')
    if kind=='hierarchy_split':
        index='\n'.join(re.findall(r'^\s*index_rom\[\d+\].*$',original,re.M))
        palette='\n'.join(re.findall(r'^\s*palette_rom\[\d+\].*$',original,re.M))
        source='''module logo_probe(input wire I_clk,input wire [13:0] I_addr,output wire [24:0] O_pixel);
wire [9:0] index;
logo_index_mem u_index(.clk(I_clk),.addr(I_addr),.data(index));
logo_palette_mem u_palette(.clk(I_clk),.addr(index),.data(O_pixel));
endmodule
(* keep_hierarchy="true" *) module logo_index_mem(input wire clk,input wire [13:0] addr,output reg [9:0] data);
(* ram_style="bram" *)reg [9:0] index_rom[0:16383];
integer i;
initial begin
for(i=0;i<16384;i=i+1)index_rom[i]=0;
'''+index+'''
end
always @(posedge clk)data<=index_rom[addr];
endmodule
(* keep_hierarchy="true" *) module logo_palette_mem(input wire clk,input wire [9:0] addr,output reg [24:0] data);
(* ram_style="bram" *)reg [24:0] palette_rom[0:1023];
integer i;
initial begin
for(i=0;i<1024;i=i+1)palette_rom[i]=0;
'''+palette+'''
end
always @(posedge clk)data<=palette_rom[addr];
endmodule
'''
    if kind=='keep_registers':
        source=source.replace('reg [9:0] pixel_index;', '(* keep="true" *) reg [9:0] pixel_index;')
        source=source.replace('output reg [24:0] O_pixel);','output wire [24:0] O_pixel);\n(* keep="true" *) reg [24:0] palette_pixel;\nassign O_pixel=palette_pixel;')
        source=source.replace('O_pixel <= palette_rom[pixel_index];','palette_pixel <= palette_rom[pixel_index];')
    (directory/'logo_probe.v').write_text(source,encoding='utf-8')
    prj=re.sub(r'<Source_Files>.*?</Source_Files>', '''<Source_Files><Verilog><File Path="logo_probe.v"><FileInfo>
    <Attr Name="UsedInSyn" Val="true"/><Attr Name="UsedInP&R" Val="true"/>
    <Attr Name="BelongTo" Val="design_1"/><Attr Name="CompileOrder" Val="1"/>
    </FileInfo></File></Verilog></Source_Files>''',project,flags=re.S)
    prj=re.sub(r' Path="[^"]+"','',prj,count=1)
    (directory/'camera_to_dsi_display.prj').write_text(prj,encoding='utf-8')
    tcl='''if {[catch {
import_device ph1_35p.db -package PH1P35MDG324 -speed 3
open_project camera_to_dsi_display.prj
elaborate -top logo_probe
optimize_rtl
optimize_gate -packarea probe.area
} result]} {puts stderr "PROBE_ERROR: $result";exit 1}
puts "PROBE_PASS"
exit 0
'''
    (directory/'probe.tcl').write_text(tcl,encoding='ascii')
    p=subprocess.run([str(td),'probe.tcl'],cwd=directory,text=True,capture_output=True,timeout=120)
    log=p.stdout+p.stderr;(directory/'probe.log').write_text(log,encoding='utf-8')
    assert p.returncode==0 and 'PROBE_PASS' in log,log[-1800:]
    area=(directory/'probe.area').read_text()
    print(kind,'\n',area[:1400],flush=True)
    result[kind]=area[:1400]
(V/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
