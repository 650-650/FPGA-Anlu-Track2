"""Old/new clocked status05 counterexample with real input events and VCD."""
from pathlib import Path
import importlib.util,re,subprocess,json,hashlib
R=Path(__file__).resolve().parents[1];H=R/'user_source/hdl_source';V=R/'validation/board_status05';V.mkdir(parents=True,exist_ok=True)
s=importlib.util.spec_from_file_location('f',R/'tools/latency_v12_unit_verify.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
t=m.BENCH
a=t.index('frame_latency_monitor #(');b=t.index('));',a)+3
instance=t[a:b].replace('frame_latency_monitor #','old_frame_latency_monitor #',1).replace(' dut(',' previous(',1)
for x,y in [('latency','old_latency'),('frame_id','old_frame_id'),('valid','old_valid'),('repeat_frame','old_repeat'),('skip_frame','old_skip')]:
 instance=instance.replace('('+x+')','('+y+')')
t=t[:b]+"\nwire [31:0] old_latency;wire [15:0] old_frame_id;wire old_valid,old_repeat,old_skip;\n"+instance+t[b:]
a=t.index('initial begin\n $display("ASYNC_CLOCKS');b=t.index('initial begin #20000000;',a)
body='''initial begin
 $dumpfile("status05.vcd");
 $dumpvars(0,sys_clk,cam_clk,ddr_clk,hdmi_clk,rst_n,raw_user,raw_valid,packed_user,write_start,write_en,read_start,read_en,final_hdmi_de,valid,old_valid,latency,old_latency);
 $dumpvars(0,dut.raw_count,dut.raw_complete,dut.write_complete,dut.metadata_ready,dut.slot_bad,dut.pending,dut.pending_sequence,dut.O_frame_id,dut.O_status,previous.O_status);
 reset_all;source_frame(0,RG,DW,0);show(0,1,1,0,0);
 check(old_valid && old_frame_id==frame_id && old_latency==latency,"normal samples unchanged");
 $display("NORMAL_OLD_NEW_EQUAL id=%0d us=%0d",frame_id,latency);
 reset_all;source_frame(0,RG-1,DW,0);show(0,1,1,0,0);
 check(!old_valid && previous.O_status==8'h05,"old RAW-completion gate produces exact board status05");
 check(valid && dut.O_status==0,"known full DDR frame origin produces independently checked delay");
 $display("BOARD05_GATE_REPRO_PASS old_status=%02h new_status=%02h id=%0d us=%0d expected_us=%0d",previous.O_status,dut.O_status,frame_id,latency,expected_age);
 reset_all;source_frame(0,0,DW,0);show(0,1,0,0,0);
 check(!old_valid && !valid,"no RAW timestamp must remain invalid");
 $display("NO_SOURCE_BOTH_REJECTED");
 reset_all;source_frame(0,RG,DW-1,0);show(0,1,0,0,0);
 check(!old_valid && !valid,"incomplete DDR must remain invalid");
 $display("PARTIAL_DDR_BOTH_REJECTED");
 $display("BOARD05_REPRO_ALL_PASS checks=%0d",checks);$finish;
end
'''
t=t[:a]+body+t[b:];(V/'tb.sv').write_text(t,encoding='utf-8')
ref=R/'validation/reference_v13/frame_latency_monitor.v'
(V/'old_monitor.v').write_text(ref.read_text(encoding='utf-8').replace('module frame_latency_monitor #(','module old_frame_latency_monitor #(',1),encoding='utf-8')
iv=Path(r'D:\anlu\iverilog\bin\iverilog.exe');files=[H/'frame_latency_monitor.v',H/'fusion_controls.v',V/'old_monitor.v']
p=subprocess.run([str(iv),'-g2012','-s','latency_v12_unit_tb','-o',str(V/'sim.vvp'),str(V/'tb.sv'),*map(str,files)],capture_output=True,text=True)
(V/'compile.log').write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0,p.stderr
p=subprocess.run([str(iv.with_name('vvp.exe')),str(V/'sim.vvp')],cwd=V,capture_output=True,text=True)
(V/'run.log').write_text(p.stdout+p.stderr,encoding='utf-8');print(p.stdout);assert p.returncode==0 and 'BOARD05_REPRO_ALL_PASS' in p.stdout
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
(V/'result.json').write_text(json.dumps({'pass':True,'source_sha256':{str(p.relative_to(R)):sha(p) for p in [H/'frame_latency_monitor.v',H/'fusion_controls.v',ref]},'testbench_sha256':sha(V/'tb.sv'),'tool_sha256':sha(Path(__file__)),'waveform':'validation/board_status05/status05.vcd','waveform_sha256':sha(V/'status05.vcd'),'log':p.stdout,'scope':'Reproduces exact observed status05 from RAW completeness gate with known full DDR generation. This identifies the blocking gate, not proof of the board RAW-count discrepancy cause.'},indent=2),encoding='utf-8')
