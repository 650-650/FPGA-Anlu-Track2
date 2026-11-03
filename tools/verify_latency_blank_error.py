from pathlib import Path
import subprocess,json,hashlib
R=Path(__file__).resolve().parents[1];H=R/'user_source/hdl_source'
V=R/'validation/latency_frontend/blank_error';V.mkdir(parents=True,exist_ok=True)
IV=Path(r'D:\anlu\iverilog\bin\iverilog.exe');VVP=IV.with_name('vvp.exe')
tb=r'''`timescale 1ns/1ps
module blank_error_tb;
reg clk=0;always #10 clk=~clk;
reg rst=0,ru=0,rv=0,re=0,pu=0;
legacy_frame_latency_monitor_v12 #(.WIDTH(16),.HEIGHT(1)) direct(.sys_clk(clk),.cam_clk(clk),.ddr_clk(clk),.hdmi_clk(clk),.rst_n(rst),.raw_user(ru),.raw_valid(rv),.raw_error(re),.packed_user(pu),.input_overflow(1'b0),.write_start(1'b0),.write_slot(2'd0),.write_en(1'b0),.write_address(25'd0),.read_start(1'b0),.read_slot(2'd0),.read_en(1'b0),.read_address(25'd0),.read_return(1'b0),.read_fifo_reset(1'b0),.raw_hdmi_vs(1'b0),.final_hdmi_vs(1'b0),.final_hdmi_de(1'b0),.output_underflow(1'b0),.O_latency_us(),.O_frame_id(),.O_valid(),.O_repeat(),.O_skip());
frame_latency_monitor #(.WIDTH(16),.HEIGHT(1)) gated(.sys_clk(clk),.cam_clk(clk),.ddr_clk(clk),.hdmi_clk(clk),.rst_n(rst),.raw_user(ru),.raw_valid(rv),.raw_error(re),.packed_user(pu),.input_overflow(1'b0),.write_start(1'b0),.write_slot(2'd0),.write_en(1'b0),.write_address(25'd0),.read_start(1'b0),.read_slot(2'd0),.read_en(1'b0),.read_address(25'd0),.read_return(1'b0),.read_fifo_reset(1'b0),.raw_hdmi_vs(1'b0),.final_hdmi_vs(1'b0),.final_hdmi_de(1'b0),.output_underflow(1'b0),.O_latency_us(),.O_frame_id(),.O_valid(),.O_repeat(),.O_skip());
task reset_all;begin rst=0;rv=0;ru=0;re=0;pu=0;repeat(4)@(negedge clk);rst=1;repeat(4)@(negedge clk);end endtask
initial begin
 reset_all;ru=1;rv=1;@(negedge clk);ru=0;repeat(3)@(negedge clk);rv=0;pu=1;@(negedge clk);pu=0;repeat(4)@(negedge clk);
 if(direct.done_good!==1 || gated.done_good!==1 || direct.raw_fault_seen!==0 || gated.raw_fault_seen!==0)$fatal(1,"healthy RAW incomplete");
 re=1;@(negedge clk);re=0;repeat(4)@(negedge clk);
 if(direct.raw_fault_seen!==1 || direct.raw_fault_id!==1 || gated.raw_fault_seen!==0)$fatal(1,"blank error expected difference absent");
 $display("BLANK_ERROR_POISONS_COMPLETE_RAW direct_fault=%0d direct_id=%0d gated_fault=%0d",direct.raw_fault_seen,direct.raw_fault_id,gated.raw_fault_seen);
 reset_all;ru=1;rv=1;@(negedge clk);ru=0;@(negedge clk);re=1;@(negedge clk);re=0;@(negedge clk);rv=0;repeat(4)@(negedge clk);
 if(direct.raw_fault_seen!==1 || gated.raw_fault_seen!==1 || direct.done_good!==0 || gated.done_good!==0)$fatal(1,"valid-beat error no longer rejected");
 $display("VALID_BEAT_ERROR_STILL_REJECTED direct_done=%0d gated_done=%0d",direct.done_good,gated.done_good);
 $display("BLANK_ERROR_RISK_PASS");$finish;
end
endmodule
'''
(V/'blank_error_tb.v').write_text(tb,encoding='utf-8')
files=[H/'frame_latency_monitor.v',H/'fusion_controls.v',R/'tools/reference/legacy_frame_latency_monitor_v12.v']
hashes={str(f.relative_to(R)):hashlib.sha256(f.read_bytes()).hexdigest()for f in files}
p=subprocess.run([str(IV),'-g2012','-s','blank_error_tb','-o',str(V/'sim.vvp'),str(V/'blank_error_tb.v'),*map(str,files)],capture_output=True,text=True,timeout=60)
(V/'compile.log').write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0,p.stdout+p.stderr
p=subprocess.run([str(VVP),str(V/'sim.vvp')],capture_output=True,text=True,timeout=60)
(V/'run.log').write_text(p.stdout+p.stderr,encoding='utf-8');print(p.stdout+p.stderr)
(V/'result.json').write_text(json.dumps({'pass':p.returncode==0 and 'BLANK_ERROR_RISK_PASS' in p.stdout,'scope':'V12 legacy marks completed RAW faulty from blank error; current V13 fixed RTL ignores blank error but rejects valid beat errors; not proof of physical encrypted byte_aligner error semantics','source_sha256':hashes},indent=2),encoding='utf-8')
assert p.returncode==0
