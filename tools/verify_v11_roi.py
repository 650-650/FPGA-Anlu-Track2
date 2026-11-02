"""Exercise the moved production ROI without changing V11 filtering logic.

Uses actual 1650 clocks/line, width 1280 and production ROI coordinates.
The stream has 224 active rows, not a complete camera/DDR simulation. Icarus
uses the module's existing behavioral line RAM; native RAM is not retested.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import time

R = Path(__file__).resolve().parents[1]
V = R / 'validation'
D = V / 'v11_roi'
D.mkdir(exist_ok=True)
B = Path(json.loads((V / 'source_baseline.json').read_text(encoding='utf-8'))['base'])
H = R / 'user_source/hdl_source'
HT, WIDTH, ROWS = 1650, 1280, 224
N = HT * ROWS
IV = Path(r'D:\anlu\iverilog\bin\iverilog.exe')
start = time.time()

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

old_inst = 'display_denoise_v11 #(.H_TOTAL(1650)) u_display_denoise('
new_inst = 'display_denoise_v11 #(.H_TOTAL(1650),.ROI_Y0(176),.ROI_Y1(208)) u_display_denoise('
top = H / 'design_top_wrapper.v'
module = H / 'display_denoise_v11.v'
assert top.read_text(encoding='utf-8') == (B / top.relative_to(R)).read_text(encoding='utf-8').replace(old_inst, new_inst)
assert sha(module) == sha(B / module.relative_to(R)), 'V11 algorithm changed'
assert 'parameter ROI_X0=672,ROI_X1=720,ROI_Y0=144,ROI_Y1=176' in module.read_text(encoding='utf-8')

# Independently specified input/output: a constant field and isolated coloured
# impulses. Each has eight matching radius-two neighbours. Only impulses in
# the configured ROI should be replaced; overlay and sketch are protected.
old_dots = {(680, 144), (696, 159), (712, 175)}
new_dots = {(680, 176), (696, 191), (712, 207)}
outside = {(671, 191), (720, 191)}
overlay_dot, sketch_dot = (680, 200), (700, 200)
dots = old_dots | new_dots | outside | {overlay_dot, sketch_dot}
assert len(dots) == 10
with (D / 'input.hex').open('w', encoding='ascii') as fi, \
     (D / 'expected_old.hex').open('w', encoding='ascii') as fo, \
     (D / 'expected_new.hex').open('w', encoding='ascii') as fn:
    for y in range(ROWS):
        for x in range(HT):
            active = x < WIDTH
            hs = WIDTH + 8 <= x < WIDTH + 12
            over = (x, y) == overlay_dot
            ctrl = 0x30 if 695 <= x <= 705 and 195 <= y <= 205 else 0
            rgb = 0xffff00 if (x, y) in dots else 0x606060
            meta = (ctrl << 28) | (int(over) << 27) | (int(active) << 26) | (int(hs) << 25)
            fi.write(f'{meta | rgb:09x}\n')
            fo.write(f'{meta | (0x606060 if (x, y) in old_dots else rgb):09x}\n')
            fn.write(f'{meta | (0x606060 if (x, y) in new_dots else rgb):09x}\n')

tb = r'''`timescale 1ns/1ps
module v11_roi_tb;
 localparam HT=1650,N=369600,LAG=2*HT+6;
 reg clk=0;always #5 clk=~clk;
 reg rst=0,vs=0,hs=0,de=0,overlay=0;reg[23:0]rgb=0;reg[7:0]control=0;
 wire[35:0] old_packet,new_packet;
 reg[35:0] input_data[0:N-1],expected_old[0:N-1],expected_new[0:N-1];
 integer i,j,checks=0,old_changes=0,new_changes=0,different=0;
 display_denoise_v11 #(.H_TOTAL(1650)) original_roi(
  .clk(clk),.rst_n(rst),.vs(vs),.hs(hs),.de(de),.rgb(rgb),.overlay(overlay),.control(control),
  .O_control(old_packet[35:28]),.O_overlay(old_packet[27]),.O_de(old_packet[26]),
  .O_hs(old_packet[25]),.O_vs(old_packet[24]),.O_rgb(old_packet[23:0]));
 display_denoise_v11 #(.H_TOTAL(1650),.ROI_Y0(176),.ROI_Y1(208)) moved_roi(
  .clk(clk),.rst_n(rst),.vs(vs),.hs(hs),.de(de),.rgb(rgb),.overlay(overlay),.control(control),
  .O_control(new_packet[35:28]),.O_overlay(new_packet[27]),.O_de(new_packet[26]),
  .O_hs(new_packet[25]),.O_vs(new_packet[24]),.O_rgb(new_packet[23:0]));
 initial begin
  $readmemh("input.hex",input_data);
  $readmemh("expected_old.hex",expected_old);$readmemh("expected_new.hex",expected_new);
  repeat(24)@(negedge clk);rst=1;
  for(i=0;i<N+LAG;i=i+1)begin
   @(negedge clk);
   if(i<N){control,overlay,de,hs,vs,rgb}=input_data[i];
   else begin control=0;overlay=0;de=0;hs=0;vs=0;rgb=0;end
   @(posedge clk);#1;
   if(i<LAG)begin
    if(old_packet!==36'd0 || new_packet!==36'd0)$fatal(1,"startup mismatch tick=%0d",i);
   end else begin
    j=i-LAG;checks=checks+1;
    if(old_packet!==expected_old[j])$fatal(1,"old ROI mismatch pixel=%0d actual=%h expected=%h",j,old_packet,expected_old[j]);
    if(new_packet!==expected_new[j])$fatal(1,"new ROI mismatch pixel=%0d actual=%h expected=%h",j,new_packet,expected_new[j]);
    if(old_packet!==input_data[j])old_changes=old_changes+1;
    if(new_packet!==input_data[j])new_changes=new_changes+1;
    if(old_packet!==new_packet)different=different+1;
   end
  end
  if(checks!=N || old_changes!=3 || new_changes!=3 || different!=6)$fatal(1,"wrong checks/events");
  $display("V11_MOVED_ROI_PASS packets=%0d old_repairs=%0d moved_repairs=%0d differences=%0d overlay_sketch_protected=1",checks,old_changes,new_changes,different);
  $finish;
 end
endmodule
'''
(D / 'v11_roi_tb.v').write_text(tb, encoding='utf-8')
for phase, cmd in [
    ('compile', [IV, '-g2012', '-s', 'v11_roi_tb', '-o', D / 'roi.vvp', D / 'v11_roi_tb.v', module]),
    ('run', [IV.with_name('vvp.exe'), D / 'roi.vvp'])]:
    p = subprocess.run(list(map(str, cmd)), cwd=D, capture_output=True, text=True, timeout=240)
    log = p.stdout + p.stderr
    (D / f'{phase}.log').write_text(log, encoding='utf-8')
    assert p.returncode == 0, (phase, log[-4000:])
    if phase == 'run':
        assert 'V11_MOVED_ROI_PASS' in log
        print(log.strip(), flush=True)
result = {
    'pass': True, 'packets': N, 'width': WIDTH, 'h_total': HT, 'active_rows': ROWS,
    'old_roi': [672, 720, 144, 176], 'new_roi': [672, 720, 176, 208],
    'old_repairs': 3, 'new_repairs': 3, 'different_pixels': 6,
    'overlay_sketch_and_outside_roi_preserved': True, 'complete_36bit_packet_checked': True,
    'unchanged_display_algorithm': True, 'behavioral_line_ram': True,
    'scope': 'Partial-height production-width display stream; no physical camera, DDR or native ERAM simulation.',
    'dut_sha256': {p.relative_to(R).as_posix(): sha(p) for p in [module, top]},
    'test_sha256': {p.relative_to(R).as_posix(): sha(p) for p in [Path(__file__), D / 'v11_roi_tb.v']},
    'seconds': round(time.time() - start, 2)}
(V / 'v11_roi_result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
