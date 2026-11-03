from pathlib import Path
import re,subprocess,sys
sys.stdout.reconfigure(encoding='utf-8')
R=Path(__file__).resolve().parents[1];V=R/'validation/mode_register_probe';V.mkdir(exist_ok=True)
source=R/'user_source/hdl_source/isp/isp_top.v'
s=source.read_text(encoding='utf-8').replace('wire [1:0] sty_mode=I_mode_req;', '''reg [1:0] sty_mode;
    always @(posedge axi4s_video_aclk or negedge I_rst_n) begin
        if(!I_rst_n) sty_mode<=0;
        else sty_mode<=I_mode_req;
    end''')
alternate=V/'isp_top_registered.v';alternate.write_text(s,encoding='utf-8')
project=(R/'td_project/camera_to_dsi_display.al').read_text(encoding='utf-8')
project=re.sub(r' Path="[^"]+"','',project,count=1)
project=re.sub(r'<File Path="([^"]+)"',lambda m:'<File Path="'+str((R/'td_project'/m[1]).resolve()).replace('\\','/')+'"',project)
project=project.replace(source.as_posix(),alternate.as_posix())
(V/'camera_to_dsi_display.prj').write_text(project,encoding='utf-8')
root=R.as_posix()
tcl=f'''if {{[catch {{
import_device ph1_35p.db -package PH1P35MDG324 -speed 3
open_project camera_to_dsi_display.prj
elaborate -top design_top_wrapper
read_adc {root}/user_source/constraints_source/pin.adc
read_ip_adc -ip ddr2 -file {root}/user_source/hdl_source/ph1p35_ddr/ddr2/src/adc/ddr2.adc
read_sdc {root}/td_project/camera_to_dsi_display.sdc
read_sdc -ip ddr2 {root}/user_source/hdl_source/ph1p35_ddr/ddr2/src/sdc/ddr2.sdc
read_sdc -ip w128_d512_fifo {root}/user_source/ip_source/w128_d512_fifo/w128_d512_fifo.tcl
optimize_rtl
optimize_gate -packarea mode_register.area
}} result options]}} {{puts stderr "PROBE_ERROR: $result"; puts stderr [dict get $options -errorinfo]; exit 1}}
puts "MODE_REGISTER_PROBE_PASS"
exit 0
'''
(V/'probe.tcl').write_text(tcl,encoding='ascii')
td=Path(r'D:\anlu\TD_6.2.1_Engineer_6.2.168.116\bin\td_commands_prompt.exe')
with (V/'probe.log').open('w',encoding='utf-8') as log:
    subprocess.run([str(td),'probe.tcl'],cwd=V,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
log=(V/'probe.log').read_text(encoding='utf-8');assert 'MODE_REGISTER_PROBE_PASS' in log,log[-2000:]
print((V/'mode_register.area').read_text()[:1700])
