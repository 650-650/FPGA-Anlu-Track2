"""Compare V14/V15 published timing results cycle by cycle; check debug causes."""
from pathlib import Path
import re,json,hashlib,subprocess
R=Path(__file__).resolve().parents[1];H=R/'user_source/hdl_source';V=R/'validation/monitor_equivalence';V.mkdir(parents=True,exist_ok=True)
B=R.with_name('07_stylize_flame_fusion_v14_latency_provenance')/'user_source/hdl_source/frame_latency_monitor.v'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
t=(R/'validation/latency_provenance_unit/tb.sv').read_text(encoding='utf-8')
match=re.search(r'frame_latency_monitor #\(.*?\) dut\(.*?\);',t,re.S);assert match
inst=match[0].replace('frame_latency_monitor #','frame_latency_monitor_v14 #').replace(' dut(',' legacy(')
for a,b in [('latency','old_latency'),('frame_id','old_id'),('valid','old_valid'),('repeat_frame','old_repeat'),('skip_frame','old_skip')]:
 inst=re.sub(r'\('+a+r'\)',lambda _: '('+b+')',inst)
add='''
wire [31:0] old_latency;wire [15:0] old_id;wire old_valid,old_repeat,old_skip;
integer equivalence_clocks=0;
always @(negedge hdmi_clk) if(rst_n)begin
 equivalence_clocks=equivalence_clocks+1;
 if({latency,frame_id,valid,repeat_frame,skip_frame,dut.O_status} !==
    {old_latency,old_id,old_valid,old_repeat,old_skip,legacy.O_status})
   $fatal(1,"V15 observational additions changed a V14 timing result");
end
'''+inst+'\n'
t=t[:match.end()]+add+t[match.end():]
# Fault injection must target both instances, including delayed CDC and wraps.
t=re.sub(r'(force|release) dut\.([\w.]+)([^;]*);',
 lambda m:m[0]+' '+m[1]+' legacy.'+m[2]+m[3]+';',t)
t=t.replace('begin passed=passed+1;$display("CASE_PASS %0s",name);end','''begin passed=passed+1;
 if(valid && dut.O_debug_reason!==0)$fatal(1,"valid result has nonzero read reason");
 if(name=="wrong_read_address_invalid" && !dut.O_debug_reason[5])$fatal(1,"missing wrong-address reason");
 if(name=="incomplete_read_image_invalid" && !dut.O_debug_reason[1])$fatal(1,"missing partial-read reason");
 if(name=="read_slot_overwritten_invalid" && !dut.O_debug_reason[2])$fatal(1,"missing overwritten-slot reason");
 if(name=="unrequested_old_return_invalid" && !dut.O_debug_reason[4])$fatal(1,"missing unrequested-return reason");
 if(name=="read_return_during_FIFO_reset_invalid" && !dut.O_debug_reason[3])$fatal(1,"missing reset-return reason");
 if(name=="outstanding_old_return_at_new_generation_invalid" && !dut.O_debug_reason[9])$fatal(1,"missing outstanding-at-start reason");
 $display("CASE_PASS %0s reason=%04h equivalent_clocks=%0d",name,dut.O_debug_reason,equivalence_clocks);end''')
legacy=V/'legacy_monitor.v';legacy.write_text(B.read_text(encoding='utf-8').replace('module frame_latency_monitor #','module frame_latency_monitor_v14 #'),encoding='utf-8')
tb=V/'tb.sv';tb.write_text(t,encoding='utf-8')
files=[H/'frame_latency_monitor.v',H/'fusion_controls.v',legacy,tb]
src={str(p):sha(p) for p in files}
iv=Path(r'D:\anlu\iverilog\bin\iverilog.exe')
c=subprocess.run([str(iv),'-g2012','-s','latency_v12_unit_tb','-o',str(V/'sim.vvp'),*map(str,files)],capture_output=True,text=True)
(V/'compile.log').write_text(c.stdout+c.stderr,encoding='utf-8');assert c.returncode==0,c.stderr
cases=clocks=0
for arg in ['', '+collision_complete','+collision_short','+collision_empty']:
 c=subprocess.run([str(iv.with_name('vvp.exe')),str(V/'sim.vvp'),*([arg] if arg else [])],capture_output=True,text=True)
 (V/((arg.strip('+') or 'main')+'.log')).write_text(c.stdout+c.stderr,encoding='utf-8')
 print(c.stdout[-2000:],flush=True);assert c.returncode==0,c.stdout[-2000:]
 cases+=int(re.search(r'LATENCY_V12_UNIT_PASS cases=(\d+)',c.stdout)[1])
 x=re.findall(r'equivalent_clocks=(\d+)',c.stdout);clocks+=int(x[-1])
assert src=={str(p):sha(p) for p in files}
r={'pass':True,'cases':cases,'compared_hdmi_clocks':clocks,'source_sha256':src,'verifier_sha256':sha(Path(__file__)),
 'policy_unchanged':True,'debug_fault_masks_checked':True,'scope':__doc__}
(V/'result.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
print('V15_MONITOR_EQUIVALENCE_PASS',cases,clocks)
