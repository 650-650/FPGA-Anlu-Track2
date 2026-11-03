"""Directed asynchronous-clock checks of the passive same-frame observer.

This exercises real RTL and the production bundled-data CDC. It does not model
the vendor pixel FIFOs or the complete ISP: production frame association and
video-path preservation need the separate integration regression.
"""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
HDL = ROOT / "user_source/hdl_source"
OUT = ROOT / "validation/latency_v12_unit"
OUT.mkdir(parents=True, exist_ok=True)
IVERILOG = Path(r"D:\anlu\iverilog\bin\iverilog.exe")

BENCH = r'''`timescale 1ns/1ps
module latency_v12_unit_tb;
localparam W=16,H=2,RG=W*H/4,DW=W*H*24/128,PX=W*H;
reg sys_clk=0,cam_clk=0,ddr_clk=0,hdmi_clk=0;
always #125 sys_clk=~sys_clk;
always #55 cam_clk=~cam_clk;
always #35 ddr_clk=~ddr_clk;
always #45 hdmi_clk=~hdmi_clk;
reg rst_n=0,raw_user=0,raw_valid=0,raw_error=0,packed_user=0,input_overflow=0;
reg write_start=0,write_en=0,read_start=0,read_en=0,read_fifo_reset=0;
reg[1:0]write_slot=0,read_slot=0;
reg[24:0]write_address=0,read_address=0;
reg raw_hdmi_vs=0,final_hdmi_vs=0,final_hdmi_de=0,output_underflow=0;
reg[2:0]return_pipe=0;
reg return_gate=1,inject_return=0;
wire read_return=(return_pipe[2] && return_gate) || inject_return;
always @(posedge ddr_clk or negedge rst_n)
 if(!rst_n)return_pipe<=0;else return_pipe<={return_pipe[1:0],read_en};
wire[31:0]latency;
wire[15:0]frame_id;
wire valid,repeat_frame,skip_frame;
// V13 diagnostics must agree with the published validity bit. This watches
// every case, including late-verdict races, rather than synthesizing a reason.
always @(negedge hdmi_clk)if(rst_n)begin
 if(valid===1'b1 && dut.O_status!==8'd0)$fatal(1,"valid sample carries an error status");
 if(valid===1'b0 && dut.O_status===8'd0)$fatal(1,"invalid sample has no diagnostic reason");
end
frame_latency_monitor #(.SYS_HZ(4000000),.WIDTH(W),.HEIGHT(H),.MAX_AGE_US(1000)) dut(
 .sys_clk(sys_clk),.cam_clk(cam_clk),.ddr_clk(ddr_clk),.hdmi_clk(hdmi_clk),.rst_n(rst_n),
 .raw_user(raw_user),.raw_valid(raw_valid),.raw_error(raw_error),.packed_user(packed_user),.input_overflow(input_overflow),
 .write_start(write_start),.write_slot(write_slot),.write_en(write_en),.write_address(write_address),
 .read_start(read_start),.read_slot(read_slot),.read_en(read_en),.read_address(read_address),
 .read_return(read_return),.read_fifo_reset(read_fifo_reset),
 .raw_hdmi_vs(raw_hdmi_vs),.final_hdmi_vs(final_hdmi_vs),.final_hdmi_de(final_hdmi_de),.output_underflow(output_underflow),
 .O_latency_us(latency),.O_frame_id(frame_id),.O_valid(valid),.O_repeat(repeat_frame),.O_skip(skip_frame));

integer checks=0,passed=0,model_id=0,last_source_id=0;
integer expected_age=0,active_id=0,active_sequence=0;
time source_time[0:65535];
time first_pixel_time;
reg[1:0]last_read_slot=0;
integer retire_slot=-1;
reg read_prestarted=0;
reg[2:0]held_request_phase=0;
function[24:0]base;
 input integer slot;
 begin case(slot)0:base=0;1:base=7000000;2:base=14000000;default:base=21000000;endcase end
endfunction
task check;
 input condition; input[511:0]message;
 begin checks=checks+1;if(condition!==1'b1)begin
  $display("FAIL check=%0d case=%0d t=%0t %0s valid=%b id=%0d age=%0d hs=%0d hv=%0d pending=%b pending_seq=%0d",
   checks,passed,$time,message,valid,frame_id,latency,dut.hdmi_sequence,dut.hv_sequence,dut.pending,dut.pending_sequence);
  $fatal(1,"LATENCY_UNIT_CHECK_FAILED");end end
endtask
task case_pass;
 input[511:0]name;
 begin passed=passed+1;$display("CASE_PASS %0s",name);end
endtask
task reset_all;
 begin
  rst_n=0;raw_user=0;raw_valid=0;raw_error=0;packed_user=0;input_overflow=0;
  write_start=0;write_en=0;read_start=0;read_en=0;read_fifo_reset=0;
  raw_hdmi_vs=0;final_hdmi_vs=0;final_hdmi_de=0;output_underflow=0;
  return_gate=1;inject_return=0;model_id=0;last_source_id=0;retire_slot=-1;read_prestarted=0;
  #1700;rst_n=1;#3300;
  check(!valid && !repeat_frame && !skip_frame,"reset clears published state");
 end
endtask

// Source frame and packed SOF are genuine input events. The expected t0 is
// wall-clock time at the first RAW group, independent of DUT time registers.
// mode: 1 raw error; 2 input FIFO overflow; 3 nonsequential DDR address.
task source_frame;
 input integer slot,raw_groups,ddr_words,mode;
 integer i;
 begin
  model_id=(model_id+1)&65535;last_source_id=model_id;
  @(negedge cam_clk);raw_user=1;raw_valid=raw_groups>0;raw_error=mode==1;
  @(posedge cam_clk);source_time[model_id]=$time;
  @(negedge cam_clk);raw_user=0;raw_valid=0;raw_error=0;
  repeat(2)@(negedge cam_clk);
  packed_user=1;
  @(negedge cam_clk);packed_user=0;
  @(negedge ddr_clk);write_slot=slot;write_start=1;
  @(negedge ddr_clk);write_start=0;
  for(i=1;i<raw_groups;i=i+1)begin
   @(negedge cam_clk);raw_valid=1;
   input_overflow=(mode==2 && i==2);
  end
  @(negedge cam_clk);raw_valid=0;input_overflow=0;
  for(i=0;i<ddr_words;i=i+1)begin
   @(negedge ddr_clk);write_en=1;write_address=base(slot)+i*8;
   if(mode==3 && i==2)write_address=write_address+8;
  end
  @(negedge ddr_clk);write_en=0;
  #6200;
 end
endtask

task raw_display_begin;
 input integer slot;
 begin
  @(negedge hdmi_clk);raw_hdmi_vs=1;
  repeat(2)@(negedge hdmi_clk);
  raw_hdmi_vs=0;
  repeat(2)@(negedge ddr_clk);
  read_slot=slot;read_start=1;last_read_slot=slot;
  @(negedge ddr_clk);read_start=0;
 end
endtask
task final_display_begin;
 begin
  @(negedge hdmi_clk);final_hdmi_vs=1;
  repeat(2)@(negedge hdmi_clk);
  final_hdmi_vs=0;
  repeat(44)@(negedge hdmi_clk);
  active_sequence=dut.hdmi_sequence;
 end
endtask
task display_begin;
 input integer slot;
 begin
  if(read_prestarted)check(slot==last_read_slot,"test source matches prestarted next read generation");
  else raw_display_begin(slot);
  read_prestarted=0;final_display_begin;
 end
endtask
task read_image;
 input integer slot,words,wrong;
 integer i;
 begin
  for(i=0;i<words;i=i+1)begin
   @(negedge ddr_clk);read_en=1;read_address=base(slot)+i*8;
   if(wrong && i==1)read_address=read_address+8;
  end
  @(negedge ddr_clk);read_en=0;
  repeat(8)@(negedge ddr_clk);
 end
endtask
task pixels;
 input integer count,id,underflow_index;
 integer i;
 begin
  for(i=0;i<count;i=i+1)begin
   @(negedge hdmi_clk);final_hdmi_de=1;output_underflow=i==underflow_index;
   if(i==0)begin
    @(posedge hdmi_clk);first_pixel_time=$time;
    expected_age=($time-source_time[id])/1000;
   end
  end
  @(negedge hdmi_clk);final_hdmi_de=0;output_underflow=0;
  repeat(4)@(negedge hdmi_clk);
 end
endtask
task retire;
 input integer expected_valid,id,expect_repeat,expect_skip;
 integer spins;
 begin
  raw_display_begin(retire_slot<0?last_read_slot:retire_slot);read_prestarted=1;
  retire_slot=-1;
  spins=0;
  while(dut.pending && spins<160)begin @(negedge hdmi_clk);spins=spins+1;end
  repeat(8)@(negedge hdmi_clk);
  check(valid===expected_valid,"retired validity");
  if(expected_valid)begin
   check(frame_id==id,"result is tied to actual displayed source ID");
   check(latency+2>=expected_age && latency<=expected_age+2,"timestamp difference matches wall-clock t0 to final first DE within 2us");
   check(repeat_frame===expect_repeat,"repeat state");
   check(skip_frame===expect_skip,"skip state");
  end else begin
   check(latency==0,"invalid frame does not expose a successful latency value");
   check(!repeat_frame && !skip_frame,"invalid frame has no success flags");
  end
 end
endtask
task show;
 input integer slot,id,expected_valid,expect_repeat,expect_skip;
 begin display_begin(slot);read_image(slot,DW,0);pixels(PX,id,-1);retire(expected_valid,id,expect_repeat,expect_skip);end
endtask

// Preserve the real atomic descriptor/verdict payload. Only hold its request
// synchronizer to model a delayed transfer, then release it so the old verdict
// first becomes observable exactly one edge before the competing pixel/boundary.
// No pending/candidate/result register is forced.
task wait_old_verdict_negedge;
 integer spins;
 begin
  @(negedge hdmi_clk);release dut.display_metadata.request_sync;
  spins=0;
  while(dut.hv_sequence!=16'd1 && spins<80)begin
   @(negedge hdmi_clk);spins=spins+1;
  end
  check(dut.hv_sequence==16'd1 && dut.pending && dut.pending_sequence==16'd1,
   "old coherent verdict arrived while previous full frame remains pending");
 end
endtask
task hold_descriptor_transaction;
 begin
  @(negedge hdmi_clk);
  held_request_phase={3{dut.display_metadata.ack}};
  force dut.display_metadata.request_sync=held_request_phase;
 end
endtask
task collision_complete;
 begin
  reset_all;source_frame(0,RG,DW,0);display_begin(0);read_image(0,DW,0);pixels(PX,1,-1);
  check(dut.pending && dut.pending_sequence==1,"first completed frame awaits retirement");
  hold_descriptor_transaction;
  display_begin(0);read_image(0,DW,0);pixels(PX-1,1,-1);
  check(dut.running && dut.pixel_count==PX-1 && dut.candidate_sequence==2,
   "second output frame reaches penultimate pixel without old verdict");
  wait_old_verdict_negedge;
  final_hdmi_de=1;
  @(posedge hdmi_clk);#1;
  $display("COLLISION_COMPLETE_STATE pending=%b seq=%0d valid=%b id=%0d",dut.pending,dut.pending_sequence,valid,frame_id);
  check(dut.pending && dut.pending_sequence==2 && !valid,
   "new completion must retain its pending entry and suppress old success on the same edge");
  @(negedge hdmi_clk);final_hdmi_de=0;
  case_pass("late_old_verdict_cannot_replace_new_full_frame_completion");
 end
endtask
task collision_incomplete;
 input integer emitted;
 begin
  reset_all;source_frame(0,RG,DW,0);display_begin(0);read_image(0,DW,0);pixels(PX,1,-1);
  check(dut.pending && dut.pending_sequence==1,"first full frame pending before short output");
  hold_descriptor_transaction;
  display_begin(0);read_image(0,DW,0);
  if(emitted!=0)pixels(emitted,1,-1);
  check((emitted==0 && dut.armed)||(emitted!=0 && dut.running),
   "next output frame is armed without DE or remains short");
  raw_display_begin(0);
  @(negedge hdmi_clk);final_hdmi_vs=1;
  repeat(3)@(negedge hdmi_clk);
  wait_old_verdict_negedge;
  final_hdmi_vs=0;
  @(posedge hdmi_clk);#1;
  $display("COLLISION_BOUNDARY_STATE emitted=%0d pending=%b seq=%0d valid=%b id=%0d",emitted,dut.pending,dut.pending_sequence,valid,frame_id);
  check(!valid && !repeat_frame && !skip_frame,
   "short or empty frame boundary must defeat same-edge stale-success publication");
  @(posedge hdmi_clk);#1;
  check(!valid && !repeat_frame && !skip_frame,
   "old pending verdict must not resurrect success one edge after an invalid boundary");
  if(emitted==0)case_pass("late_old_verdict_loses_to_empty_frame_boundary");
  else case_pass("late_old_verdict_loses_to_short_frame_boundary");
 end
endtask

initial begin
 $display("ASYNC_CLOCKS sys=250ns camera=110ns ddr=70ns hdmi=90ns");
 if($test$plusargs("collision_complete"))begin
  collision_complete;$display("LATENCY_V12_UNIT_PASS cases=%0d checks=%0d",passed,checks);$finish;
 end
 if($test$plusargs("collision_short"))begin
  collision_incomplete(8);$display("LATENCY_V12_UNIT_PASS cases=%0d checks=%0d",passed,checks);$finish;
 end
 if($test$plusargs("collision_empty"))begin
  collision_incomplete(0);$display("LATENCY_V12_UNIT_PASS cases=%0d checks=%0d",passed,checks);$finish;
 end
 reset_all;source_frame(0,RG,DW,0);source_frame(1,RG,DW,0);source_frame(2,RG,DW,0);source_frame(3,RG,DW,0);
 show(0,1,1,0,0);case_pass("first_valid_identity_and_age");
 retire_slot=2;show(0,1,1,1,0);case_pass("repeated_frame_keeps_ID_and_timestamp");
 source_frame(0,RG,DW,0);retire_slot=3;show(2,3,1,0,1);case_pass("skipped_source_ID_reported");
 retire_slot=0;show(3,4,1,0,0);show(0,5,1,0,0);case_pass("four_slot_ring_wrap");

 reset_all;source_frame(0,RG,DW,0);display_begin(0);read_image(0,DW+2,0);pixels(PX,1,-1);retire(1,1,0,0);case_pass("harmless_extra_prefetch_not_false_incomplete");
 reset_all;source_frame(0,RG-1,DW,0);show(0,1,0,0,0);case_pass("partial_RAW_invalid");
 reset_all;source_frame(0,RG+1,DW,0);show(0,1,0,0,0);case_pass("extra_RAW_invalid");
 reset_all;source_frame(0,RG,DW-1,0);show(0,1,0,0,0);case_pass("partial_DDR_invalid");
 reset_all;source_frame(0,RG,DW+1,0);show(0,1,0,0,0);case_pass("extra_DDR_write_invalid");
 reset_all;source_frame(0,RG,DW,3);show(0,1,0,0,0);case_pass("nonsequential_DDR_write_invalid");
 reset_all;source_frame(0,RG,DW,1);show(0,1,0,0,0);case_pass("RAW_error_invalid");
 reset_all;source_frame(0,RG,DW,2);show(0,1,0,0,0);case_pass("input_FIFO_overflow_invalid");

 reset_all;source_frame(0,RG,DW,0);display_begin(0);read_image(0,DW,1);pixels(PX,1,-1);retire(0,1,0,0);case_pass("wrong_read_address_invalid");
 reset_all;source_frame(0,RG,DW,0);display_begin(0);read_image(0,DW-1,0);pixels(PX,1,-1);retire(0,1,0,0);case_pass("incomplete_read_image_invalid");
 reset_all;source_frame(0,RG,DW,0);display_begin(0);read_image(0,DW,0);source_frame(0,RG,DW,0);pixels(PX,1,-1);retire(0,1,0,0);case_pass("read_slot_overwritten_invalid");
 reset_all;source_frame(0,RG,DW,0);display_begin(0);read_image(0,DW,0);pixels(PX,1,10);retire(0,1,0,0);case_pass("output_FIFO_underflow_invalid");
 reset_all;source_frame(0,RG,DW,0);display_begin(0);read_image(0,DW,0);pixels(PX-1,1,-1);retire(0,1,0,0);case_pass("partial_output_frame_invalid");
 reset_all;source_frame(0,RG,DW,0);display_begin(0);read_image(0,DW,0);pixels(PX+1,1,-1);retire(0,1,0,0);case_pass("extra_output_pixel_invalid");

 reset_all;source_frame(0,RG,DW,0);display_begin(0);
 @(negedge ddr_clk);inject_return=1;@(negedge ddr_clk);inject_return=0;
 read_image(0,DW,0);pixels(PX,1,-1);retire(0,1,0,0);case_pass("unrequested_old_return_invalid");

 reset_all;source_frame(0,RG,DW,0);display_begin(0);return_gate=0;
 read_image(0,1,0);display_begin(0);read_image(0,DW,0);pixels(PX,1,-1);retire(0,1,0,0);case_pass("outstanding_old_return_at_new_generation_invalid");

 reset_all;source_frame(0,RG,DW,0);display_begin(0);
 @(negedge ddr_clk);read_en=1;read_address=base(0);
 @(negedge ddr_clk);read_en=0;read_fifo_reset=1;
 repeat(6)@(negedge ddr_clk);read_fifo_reset=0;
 read_image(0,DW,0);pixels(PX,1,-1);retire(0,1,0,0);case_pass("read_return_during_FIFO_reset_invalid");

 // Only this boundary fault injection stalls the real synchronizer. Normal
 // cases above use unforced source/CDC events and external time scoreboards.
 reset_all;source_frame(0,RG,DW,0);
 force dut.display_metadata.request_sync=3'd0;
 display_begin(0);read_image(0,DW,0);pixels(PX,1,-1);
 release dut.display_metadata.request_sync;
 retire(0,1,0,0);case_pass("late_descriptor_cannot_borrow_previous_frame");

 reset_all;source_frame(0,RG,DW,0);show(0,1,1,0,0);
 display_begin(0);read_image(0,DW,0);pixels(PX,1,-1);
 force dut.display_metadata.request_sync=3'd0;
 display_begin(0);repeat(180)@(negedge hdmi_clk);
 check(!valid,"missing current verdict must not retain stale successful O_valid");
 release dut.display_metadata.request_sync;
 case_pass("missing_verdict_clears_old_success");

 reset_all;source_frame(0,RG,DW,0);display_begin(0);read_image(0,DW,0);pixels(8,1,-1);
 reset_all;source_frame(1,RG,DW,0);show(1,1,1,0,0);case_pass("reset_mid_output_discards_previous_epoch");

 reset_all;
 @(negedge sys_clk);
 force dut.microseconds=32'hfffffff8;
 force dut.time_gray=32'h80000004;
 @(negedge sys_clk);release dut.microseconds;release dut.time_gray;
 #1100;
 source_frame(0,RG,DW,0);show(0,1,1,0,0);case_pass("microsecond_wrap_modular_difference");

 reset_all;model_id=65534;
 @(negedge cam_clk);force dut.raw_id=16'hfffe;
 @(negedge cam_clk);release dut.raw_id;
 source_frame(0,RG,DW,0);source_frame(1,RG,DW,0);retire_slot=1;show(0,65535,1,0,0);
 show(1,0,1,0,0);case_pass("source_ID_wrap_does_not_fake_skip");

 reset_all;source_frame(0,RG,DW,0);#1010000;show(0,1,0,0,0);case_pass("stale_source_age_limit_invalid");
 $display("LATENCY_V12_UNIT_PASS cases=%0d checks=%0d",passed,checks);$finish;
end
initial begin #20000000;$fatal(1,"GLOBAL_TESTBENCH_TIMEOUT");end
endmodule
'''


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    started = time.time()
    bench = OUT / "latency_v12_unit_tb.sv"
    bench.write_text(BENCH, encoding="utf-8", newline="\n")
    binary = OUT / "latency_v12_unit.vvp"
    sources = [HDL / "frame_latency_monitor.v", HDL / "fusion_controls.v"]
    result = {
        "pass": False,
        "scope": "Passive observer unit RTL plus real production bundled-data CDC; independent asynchronous clocks and external wall-clock timestamp/identity checks. Not a complete camera/DDR/HDMI simulation or hardware measurement.",
        "source_sha256": {p.relative_to(ROOT).as_posix(): digest(p) for p in sources},
        "test_sources_sha256": {bench.relative_to(ROOT).as_posix(): digest(bench), Path(__file__).relative_to(ROOT).as_posix(): digest(Path(__file__))},
        "timestamp_tolerance_us": 2,
        "test_resolution": "16x2 pixels, 8 RAW groups, 6 packed DDR words; four independent clocks",
        "injection_limits": "Only late/missing descriptor synchronizer (including coherent old-verdict/new-frame collisions), timestamp wrap and ID wrap use force/release. Collision tests release the real atomic CDC payload; no pending/candidate/result register is forced. All normal source IDs, slot claims, addresses, read returns, pixel events and t0/t1 checks are genuine input events.",
        "stages": {},
    }
    try:
        errors = []
        for stage, command, timeout in [
            ("compile", [IVERILOG, "-g2012", "-s", "latency_v12_unit_tb", "-o", binary, bench, *sources], 90),
            ("run", [IVERILOG.with_name("vvp.exe"), binary], 90),
            ("run_collision_complete", [IVERILOG.with_name("vvp.exe"), binary, "+collision_complete"], 90),
            ("run_collision_short", [IVERILOG.with_name("vvp.exe"), binary, "+collision_short"], 90),
            ("run_collision_empty", [IVERILOG.with_name("vvp.exe"), binary, "+collision_empty"], 90),
        ]:
            process = subprocess.run(list(map(str, command)), cwd=ROOT, capture_output=True, text=True, timeout=timeout)
            log = process.stdout + process.stderr
            (OUT / (stage + ".log")).write_text(log, encoding="utf-8")
            result["stages"][stage] = {"returncode": process.returncode, "log": (OUT / (stage + ".log")).relative_to(ROOT).as_posix()}
            print(log[-10000:], flush=True)
            if process.returncode != 0:
                errors.append(f"{stage} failed, exit={process.returncode}")
                if stage == "compile":
                    break
                continue
            if stage.startswith("run"):
                matched = re.search(r"LATENCY_V12_UNIT_PASS cases=(\d+) checks=(\d+)", log)
                if not matched:
                    errors.append(stage + ": no dynamic PASS marker")
                    continue
                result["cases"] = result.get("cases", 0) + int(matched[1])
                result["checks"] = result.get("checks", 0) + int(matched[2])
                result.setdefault("case_names", []).extend(re.findall(r"CASE_PASS (.+)", log))
        if errors:
            result["failures"] = errors
            raise RuntimeError("; ".join(errors))
        if any(digest(p) != result["source_sha256"][p.relative_to(ROOT).as_posix()] for p in sources):
            raise RuntimeError("RTL changed during test; rerun required")
        result["pass"] = True
    except Exception as error:
        result["error"] = repr(error)
        raise
    finally:
        result["seconds"] = round(time.time() - started, 3)
        (OUT / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    print("LATENCY_V12_UNIT_VERIFICATION_PASS", flush=True)


if __name__ == "__main__":
    main()
