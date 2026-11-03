"""Five-level controls/CDC regression and cycle comparison of all V15 outputs."""
from pathlib import Path
import json,hashlib,subprocess,re
R=Path(__file__).resolve().parents[1];H=R/'user_source/hdl_source';V=R/'validation/controls_levels';V.mkdir(parents=True,exist_ok=True)
B=R.with_name('07_stylize_flame_fusion_v15_ddr_latency_final');T=Path(json.loads((R/'validation/integration_inputs.json').read_text(encoding='utf-8'))['teammate'])
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
original=T/'validation/controls_params_tb.sv';tb=V/'teammate_controls_params_tb.sv';tb.write_bytes(original.read_bytes())
old=V/'legacy_controls.v';old.write_text((B/'user_source/hdl_source/fusion_controls.v').read_text(encoding='utf-8').split('// Bundled-data request/acknowledge CDC.')[0].replace('module fusion_controls #','module legacy_controls #'),encoding='utf-8')
compare=V/'compare_tb.sv';compare.write_text(r'''`timescale 1ns/1ps
module compare_tb;
reg clk=0;always #10 clk=~clk;
reg [3:0]keys=15,sw=15;wire nr,orr,no,oo,nw,ow;wire[7:0]nc,oc;wire[5:0]nt,ot;wire[11:0]levels;
fusion_controls #(.BOOT_CYCLES(6),.DEBOUNCE_CYCLES(3),.RESET_CYCLES(9),.K3_HOLD_CYCLES(100),.K4_HOLD_CYCLES(80)) n(
 .I_clk(clk),.I_keys_n(keys),.I_switches(sw),.O_system_rst_n(nr),.O_control(nc),.O_osd_enable(no),.O_wb_toggle(nw),.O_color_control(nt),.O_style_levels(levels));
legacy_controls #(.BOOT_CYCLES(6),.DEBOUNCE_CYCLES(3),.RESET_CYCLES(9),.K3_HOLD_CYCLES(100),.K4_HOLD_CYCLES(80)) o(
 .I_clk(clk),.I_keys_n(keys),.I_switches(sw),.O_system_rst_n(orr),.O_control(oc),.O_osd_enable(oo),.O_wb_toggle(ow),.O_color_control(ot));
integer checks=0,i,j;reg[31:0]lfsr=32'h9ac74b13;
always @(posedge clk)begin
 #1;checks=checks+1;
 if({nr,nc,no,nw,nt}!=={orr,oc,oo,ow,ot})$fatal(1,"V15 control behavior regressed at check=%0d",checks);
 for(j=0;j<4;j=j+1)if(levels[j*3+:3]>4)$fatal(1,"illegal five-level state");
end
initial begin
 repeat(30)@(negedge clk);
 for(i=0;i<1000;i=i+1)begin
  lfsr={lfsr[30:0],lfsr[31]^lfsr[21]^lfsr[1]^lfsr[0]};
  sw=lfsr[11:8];keys=lfsr[3:0];repeat(7+(lfsr[15:12]*8))@(negedge clk);
  keys=15;repeat(13)@(negedge clk);
 end
 $display("V15_CONTROL_CYCLE_EQUIVALENCE_PASS checks=%0d",checks);$finish;
end
endmodule
''',encoding='utf-8')
iv=Path(r'D:\anlu\iverilog\bin\iverilog.exe');files=[H/'fusion_controls.v',old,tb,compare];src={str(p):sha(p) for p in files};results=[]
for top,marker in [('controls_params_tb','CONTROLS_PARAMS_PASS'),('compare_tb','V15_CONTROL_CYCLE_EQUIVALENCE_PASS')]:
 c=subprocess.run([str(iv),'-g2012','-s',top,'-o',str(V/(top+'.vvp')),*map(str,files)],capture_output=True,text=True)
 (V/(top+'_compile.log')).write_text(c.stdout+c.stderr,encoding='utf-8');assert c.returncode==0,c.stderr
 c=subprocess.run([str(iv.with_name('vvp.exe')),str(V/(top+'.vvp'))],capture_output=True,text=True)
 log=c.stdout+c.stderr;(V/(top+'.log')).write_text(log,encoding='utf-8');assert c.returncode==0 and marker in log,log
 count=int(re.search(marker+r' checks=(\d+)',log)[1]);results.append({'top':top,'checks':count,'pass':True});print(log,flush=True)
assert src=={str(p):sha(p) for p in files}
r={'pass':True,'results':results,'source_sha256':src,'verifier_sha256':sha(Path(__file__)),'teammate_TB_sha256':sha(original),
 'scope':'Five levels, memory, SW4, debounce, K3/K4 holds, coherent frame commit; every original control/color/alarm/reset output matches V15 on same pins.'}
(V/'result.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
