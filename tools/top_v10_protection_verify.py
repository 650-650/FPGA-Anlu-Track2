"""Fresh V10 vs delivered V9 protection checks using actual production RTL.

The HDMI connection block is extracted verbatim from each design_top_wrapper.
Every baseline module is namespaced from its baseline file, so the reference
cannot silently instantiate a changed V10 display filter or recognition core.
The functional fire/aid benches additionally exercise active target and sound
states with their original, explicitly accelerated simulation parameters.
"""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
R = Path(__file__).resolve().parents[1]
H = R / "user_source/hdl_source"
B = R.with_name("07_stylize_flame_fusion_v9_detail_motion_compact")
BH = B / "user_source/hdl_source"
V = R / "validation/top_v10_protection"
IV = Path(r"D:\anlu\iverilog\bin\iverilog.exe")
FILES = [
    "display_contrast.v", "display_denoise_v9.v", "display_cartoon_finish_v9.v",
    "color_luma_preserve.v", "fusion_controls.v", "fusion_flame_pipeline.v",
    "visual_flame_alarm.v", "first_aid_detector.v", "camera_frame_watchdog.v",
    "alarm_board_io.v",
]
CONTEXT = ["design_top_wrapper.v", "display_tone.dat", "isp/stylize_v5_96.v",
           "isp/style_guide_v8.v"]
PROTECTED = [f for f in FILES if f != "display_denoise_v9.v"]
NS = 1666


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return path.read_text(encoding="utf-8")


def normalized_rom_path(text):
    return re.sub(r'"[^"\r\n]*/display_tone\.dat"', '"DISPLAY_TONE_PATH"', text)


def namespace(text, names):
    pattern = re.compile(r"\b(" + "|".join(sorted(map(re.escape, names), key=len, reverse=True)) + r")\b")
    return pattern.sub(lambda m: "reference_v9_" + m[0], text)


HEADER = """module NAME(
 input S_csi_rx_clk,S_hdmi_pixel_clk,S_hdmi_rst_n,S_hdmi_user,
 input [12:0] color_gain_r,color_gain_b,input [23:0] mix_clean,mix_rgb,
 input mix_vs,mix_hs,mix_de,mix_overlay,input [5:0] color_control_hdmi,input [7:0] controls_hdmi,
 input [1:0] fusion_mode,input S_csi_frame_start,S_cam_cfg_done,S_init_calib_complete,S_lane_error_any,wb_locked,
 output O_vs,O_hs,O_de,output [23:0] O_rgb,O_detect,O_clean,O_core,O_detector_port,
 output O_color_de,output [65:0] O_detection_state,
 output [7:0] O_display_control,output O_display_overlay,
 output [25:0] O_gains,output [3:0] O_core_flags);
 wire S_hdmi_out_vsync,S_hdmi_out_hsync,S_hdmi_out_de;
 wire [23:0] S_hdmi_out_data;wire [3:0] O_led;
 wire O_buzzer_n,alarm,target,source_ok,video_lost,armed;
 wire [31:0] candidate_pixels;wire [11:0] target_x,target_y;
"""
TAIL = """
 assign O_vs=S_hdmi_out_vsync;assign O_hs=S_hdmi_out_hsync;assign O_de=S_hdmi_out_de;
 assign O_rgb=S_hdmi_out_data;assign O_detect=auto_clean;assign O_clean=color_clean;
 assign O_core=core_hdmi_rgb;assign O_color_de=color_de;
 assign O_detector_port=u_flame_fusion.I_detector_rgb;
 assign O_detection_state={O_led,O_buzzer_n,alarm,target,source_ok,video_lost,armed,candidate_pixels,target_x,target_y};
 assign O_display_control=denoise_control;assign O_display_overlay=denoise_overlay;
 assign O_gains=color_gains_hdmi;assign O_core_flags={core_hdmi_vs,core_hdmi_hs,core_hdmi_de,display_overlay_d};
endmodule
"""


TB = r"""`timescale 1ns/1ps
module top_v10_protection_tb;
 reg clk=0,sclk=0;always #5 clk=~clk;always #7 sclk=~sclk;
 reg rst=0,frame=0,vs=0,hs=0,de=0,overlay=0;
 reg [23:0] clean=0,composite=0;reg [5:0] trim=0;reg [7:0] control=0;
 reg [1:0] mode=0;reg [12:0] gr=4096,gb=4096;
 wire nvs,nhs,nde,ovs,ohs,ode,ncde,ocde,nov,oov;
 wire [23:0] np,op,ndetect,odetect,ncolor,ocolor,ncore,ocore,nport,oport;
 wire [65:0] nstate,ostate;wire [7:0] nctl,octl;
 wire [25:0] ngains,ogains;wire [3:0] ncflags,ocflags;
 localparam NS=1666;
 reg [23:0] cq[0:NS-1],pq[0:NS-1];reg [3:0] fq[0:NS-1];reg [7:0] ctlq[0:NS-1];
 integer n=0,w,r,meta_r,j,phase,f,i,scount=0,checks=0,detector_checks=0;
 integer overlays=0,styles=0,legacy=0,calibration=0,metadata=0,clear_changes=0;
 integer seed=32'h317ac907;
 production_v10_display current(.S_csi_rx_clk(sclk),.S_hdmi_pixel_clk(clk),.S_hdmi_rst_n(rst),.S_hdmi_user(frame),
  .color_gain_r(gr),.color_gain_b(gb),.mix_clean(clean),.mix_rgb(composite),.mix_vs(vs),.mix_hs(hs),.mix_de(de),.mix_overlay(overlay),
  .color_control_hdmi(trim),.controls_hdmi(control),.fusion_mode(mode),.S_csi_frame_start(frame),
  .S_cam_cfg_done(1'b1),.S_init_calib_complete(1'b1),.S_lane_error_any(1'b0),.wb_locked(1'b1),
  .O_vs(nvs),.O_hs(nhs),.O_de(nde),.O_rgb(np),.O_detect(ndetect),.O_clean(ncolor),.O_color_de(ncde),
  .O_core(ncore),.O_detector_port(nport),.O_detection_state(nstate),.O_display_control(nctl),
  .O_display_overlay(nov),.O_gains(ngains),.O_core_flags(ncflags));
 production_v9_display prior(.S_csi_rx_clk(sclk),.S_hdmi_pixel_clk(clk),.S_hdmi_rst_n(rst),.S_hdmi_user(frame),
  .color_gain_r(gr),.color_gain_b(gb),.mix_clean(clean),.mix_rgb(composite),.mix_vs(vs),.mix_hs(hs),.mix_de(de),.mix_overlay(overlay),
  .color_control_hdmi(trim),.controls_hdmi(control),.fusion_mode(mode),.S_csi_frame_start(frame),
  .S_cam_cfg_done(1'b1),.S_init_calib_complete(1'b1),.S_lane_error_any(1'b0),.wb_locked(1'b1),
  .O_vs(ovs),.O_hs(ohs),.O_de(ode),.O_rgb(op),.O_detect(odetect),.O_clean(ocolor),.O_color_de(ocde),
  .O_core(ocore),.O_detector_port(oport),.O_detection_state(ostate),.O_display_control(octl),
  .O_display_overlay(oov),.O_gains(ogains),.O_core_flags(ocflags));
 always @(posedge sclk)begin
  #2;if(rst && n>20)begin
   if(ngains!==ogains)$fatal(1,"source-clock calibration CDC differs");
   if(current.u_flame_fusion.source_toggle!==prior.u_flame_fusion.source_toggle ||
      current.u_flame_fusion.source_frame_d!==prior.u_flame_fusion.source_frame_d)
    $fatal(1,"source-clock source-frame CDC state differs");
   scount=scount+1;
  end
 end
 task tick;begin
  @(posedge clk);#1;
  // Raw control enters at u_cartoon_finish, after the 3+1 colour/core
  // pixel stages. Its own packet path is 4+1656=1660 registers (lag1659).
  // RGB/video continue through colour3+core1+finish4+cross1656+tone2=1666.
  w=n%NS;r=(w+1)%NS;meta_r=(w+7)%NS;
  cq[w]=composite;pq[w]=clean;fq[w]={vs,hs,de,overlay};ctlq[w]=control;
  if(rst && n>NS+4)begin
   if({nvs,nhs,nde}!==fq[r][3:1] || {ovs,ohs,ode}!==fq[r][3:1])
    $fatal(1,"production RGB/video sideband latency is not 1666 register stages");
   if({nvs,nhs,nde,nctl,nov,ncde,ncflags}!=={ovs,ohs,ode,octl,oov,ocde,ocflags})
    $fatal(1,"same-clock metadata differs");
   if(nctl!==ctlq[meta_r])$fatal(1,"display control does not follow center packet");
   if(ngains!==ogains || ncolor!==ocolor)$fatal(1,"upstream color calibration differs");
   if(ndetect!==odetect || nport!==oport || nport!==ndetect)
    $fatal(1,"actual detector input differs at same clock");
   if(nstate!==ostate || ncore!==ocore)$fatal(1,"real core output/state differs at same clock");
   metadata=metadata+1;
   if(ncde)begin detector_checks=detector_checks+1;calibration=calibration+1;end
   if(nde)begin
    checks=checks+1;
    if(fq[r][0])begin
     overlays=overlays+1;
     if(np!==cq[r] || op!==cq[r])$fatal(1,"overlay RGB was modified");
    end else if(ctlq[r][7:5]==1 && ctlq[r][4])begin
     styles=styles+1;
     if(np!==op || np!==pq[r])$fatal(1,"protected sketch/edge HDMI path differs");
    end else if(ctlq[r][7:5]>=2)begin
     legacy=legacy+1;
     if(np!==op)$fatal(1,"protected SW2/SW3 HDMI path differs");
    end else if(np!==op)clear_changes=clear_changes+1;
   end
  end
  n=n+1;@(negedge clk);
 end endtask
 task idle;input integer count;begin
  de=0;overlay=0;frame=0;vs=0;hs=0;repeat(count)tick;
 end endtask
 task commit;begin frame=1;vs=1;repeat(5)tick;frame=0;vs=0;idle(1800);end endtask
 initial begin
  for(j=0;j<NS;j=j+1)begin cq[j]=0;pq[j]=0;fq[j]=0;ctlq[j]=0;end
  repeat(5)tick;rst=1;idle(1800);
  for(phase=0;phase<10;phase=phase+1)begin
   idle(1800);
   case(phase)
    0:begin control=0;mode=0;end
    1:begin control=8'h20;mode=0;end
    2:begin control=8'h28;mode=1;end
    3:begin control=8'h30;mode=2;end
    4:begin control=8'h38;mode=3;end
    5:begin control=8'h40;mode=0;end
    6:begin control=8'h48;mode=0;end
    7:begin control=8'h50;mode=0;end
    8:begin control=8'h58;mode=0;end
    9:begin control=8'h60;mode=0;end
   endcase
   gr=phase%2?13'd6144:13'd2048;gb=phase%3?13'd2600:13'd6000;commit;commit;
   for(f=0;f<3;f=f+1)begin
    commit;
    for(i=0;i<1650*8;i=i+1)begin
     clean={$random(seed)};composite={$random(seed)};trim=i%36;
     de=i%1650<1280;hs=i%1650>=1390 && i%1650<1430;
     overlay=i%13==0 || (i%1650<15 && i/1650<2);tick;
    end
    idle(1800);
   end
   idle(1800);
  end
  idle(NS+100);
  if(detector_checks<300000 || overlays<18000 || styles<50000 || legacy<130000 || metadata<400000 || scount<100000)
   $fatal(1,"insufficient active protection coverage");
  $display("TOP_V10_PROTECTION_PASS ticks=%0d active=%0d detector_same_clock=%0d overlay_exact=%0d sketch_edge_exact=%0d SW2_SW3_exact=%0d metadata=%0d source_clock=%0d calibration=%0d clear_changed=%0d",n,checks,detector_checks,overlays,styles,legacy,metadata,scount,calibration,clear_changes);
  $finish;
 end
 initial begin #20000000;$fatal(1,"top protection timeout");end
endmodule
"""


def extract_top(root, label, names=None):
    source = read(root / "design_top_wrapper.v")
    begin = source.index("    wire [25:0] color_gains_hdmi;")
    end = source.index("    hdmi_mixer #(", begin)
    block = source[begin:end]
    assert "display_denoise_v9" in block and "display_cartoon_finish_v9" in block
    if names:
        block = namespace(block, names)
    wrapper = HEADER.replace("NAME", f"production_{label}_display") + block + TAIL
    (V / f"production_{label}_display.v").write_text(wrapper, encoding="utf-8")


def make_paired_functional_bench(name, names):
    """Preserve the established baseline stimuli, add independent reference RTL.

    All original assertions remain. These fixtures deliberately accelerate
    arming/timeouts and use reduced frame dimensions, as their parameters show.
    """
    source = read(B / "validation" / f"{name}.v")
    renamed = f"paired_v10_{name}"
    source = source.replace(f"module {name};", f"module {renamed};", 1)
    start = source.index("    fusion_flame_pipeline #(")
    end = source.index(");", source.index(" dut(", start)) + 2
    instance = source[start:end]
    output_ports = {
        "O_vsync": "ovs" if name == "fusion_pipeline_tb" else "ov",
        "O_hsync": "ohs" if name == "fusion_pipeline_tb" else "oh",
        "O_de": "ode" if name == "fusion_pipeline_tb" else "od",
        "O_rgb": "result", "O_led": "leds", "O_buzzer_n": "buzz",
        "O_alarm": "alarm", "O_target": "target", "O_source_ok": "source_ok" if name == "fusion_pipeline_tb" else "source",
        "O_video_lost": "lost", "O_armed": "armed", "O_candidate_pixels": "pixels",
        "O_center_x": "cx", "O_center_y": "cy",
    }
    # Explicitly wire outputs omitted by the original aid fixture as well.
    declarations = []
    ref = namespace(instance, names).replace(" dut(", " prior(", 1)
    ninstance = instance
    comparisons = []
    for port, signal in output_ports.items():
        width = "[23:0] " if port == "O_rgb" else "[31:0] " if port == "O_candidate_pixels" else "[11:0] " if port in ("O_center_x", "O_center_y") else "[3:0] " if port == "O_led" else ""
        declarations.append(f" wire {width}reference_{signal};")
        pattern = re.compile(r"\." + port + r"\(([^)]*)\)")
        current = pattern.search(ninstance)
        if current:
            assert current[1] == signal, (name, port, current[1], signal)
            ref = pattern.sub(f".{port}(reference_{signal})", ref)
        else:
            declarations.append(f" wire {width}{signal};")
            ninstance = ninstance[:-2] + f",.{port}({signal}));"
            ref = ref[:-2] + f",.{port}(reference_{signal}));"
        comparisons.append(f"{signal}!==reference_{signal}")
    logic = "\n".join(declarations) + "\n integer pair_checks=0,positive_target=0,positive_alarm=0,sound_low=0;\n"
    logic += " always @(posedge clk)begin #2;if(rst)begin\n"
    logic += "  if(" + " || ".join(comparisons) + f')$fatal(1,"{name}: paired real pipeline output differs");\n'
    logic += "  pair_checks=pair_checks+1;if(target)positive_target=positive_target+1;if(alarm)positive_alarm=positive_alarm+1;if(!buzz)sound_low=sound_low+1;\n end end\n"
    source = source[:start] + logic + ninstance + "\n" + ref + source[end:]
    final = "$finish;"
    coverage = 'if(positive_target==0 || pair_checks<1000)$fatal(1,"paired target coverage missing");'
    if name == "fusion_pipeline_tb":
        coverage += 'if(positive_alarm==0 || sound_low==0)$fatal(1,"paired alarm/sound coverage missing");'
    coverage += f'$display("PAIRED_V10_{name.upper()}_PASS pair_checks=%0d positive_target=%0d positive_alarm=%0d sound_low=%0d",pair_checks,positive_target,positive_alarm,sound_low);$finish;'
    assert source.count(final) == 1
    source = source.replace(final, coverage)
    path = V / f"{renamed}.v"
    path.write_text(source, encoding="utf-8")
    return path, renamed


def main():
    V.mkdir(parents=True, exist_ok=True)
    start = time.time()
    # Protect every inherited detection/control/colour module. ROM paths are
    # permitted to relocate, but their actual initialized bytes must be equal.
    for name in PROTECTED:
        a, b = read(H / name), read(BH / name)
        assert normalized_rom_path(a) == normalized_rom_path(b), ("Protected source changed", name)
    assert sha(H / "display_tone.dat") == sha(BH / "display_tone.dat")
    current_hashes = {(H / f).relative_to(R).as_posix(): sha(H / f) for f in FILES + CONTEXT}
    baseline_hashes = {(BH / f).relative_to(B).as_posix(): sha(BH / f) for f in FILES + CONTEXT}
    baseline_inputs = [B / "validation" / f for f in ("fusion_pipeline_tb.v", "aid_pipeline_tb.v")]
    baseline_hashes.update({p.relative_to(B).as_posix(): sha(p) for p in baseline_inputs})
    texts = {f: read(BH / f) for f in FILES}
    names = set()
    for text in texts.values():
        names.update(re.findall(r"\bmodule\s+(\w+)", text))
    baseline_sources = []
    for name, text in texts.items():
        target = V / ("reference_v9_" + name)
        target.write_text(namespace(text, names), encoding="utf-8")
        baseline_sources.append(target)
    extract_top(H, "v10")
    extract_top(BH, "v9", names)
    top_tb = V / "top_v10_protection_tb.v"
    top_tb.write_text(TB, encoding="utf-8")
    common = [H / f for f in FILES] + baseline_sources
    tests = [
        ("actual_top", "top_v10_protection_tb", [top_tb, V / "production_v10_display.v", V / "production_v9_display.v"]),
    ]
    for fixture in ("fusion_pipeline_tb", "aid_pipeline_tb"):
        path, name = make_paired_functional_bench(fixture, names)
        tests.append((fixture, name, [path]))
    summary = {}
    for label, top, extra in tests:
        binary = V / (label + ".vvp")
        for phase, cmd in (
            ("compile", [IV, "-g2012", "-s", top, "-o", binary] + extra + common),
            ("run", [IV.with_name("vvp.exe"), binary]),
        ):
            result = subprocess.run(list(map(str, cmd)), cwd=R, capture_output=True, text=True, timeout=900)
            log = result.stdout + result.stderr
            (V / f"{label}_{phase}.log").write_text(log, encoding="utf-8")
            assert result.returncode == 0, (label, phase, log[-4000:])
            if phase == "run":
                marker = "TOP_V10_PROTECTION_PASS" if label == "actual_top" else f"PAIRED_V10_{label.upper()}_PASS"
                assert marker in log, (label, log[-4000:])
                print(log[-1500:], flush=True)
                summary[label] = {"pass": True, "marker": marker, "log": f"validation/top_v10_protection/{label}_run.log"}
    for path, digest in current_hashes.items():
        assert sha(R / path) == digest, ("DUT changed during test", path)
    for path, digest in baseline_hashes.items():
        assert sha(B / path) == digest, ("Baseline changed during test", path)
    generated = [p for p in V.iterdir() if p.suffix == ".v"]
    result = {
        "tests": summary,
        "source_sha256": current_hashes,
        "baseline": str(B), "baseline_source_sha256": baseline_hashes,
        "oracle_sha256": {Path(__file__).relative_to(R).as_posix(): sha(Path(__file__))},
        "generated_hdl_sha256": {p.relative_to(R).as_posix(): sha(p) for p in generated},
        "registered_display_stages": NS,
        "registered_raw_control_to_denoise_stages": 1660,
        "source_and_pixel_clocks_compared": True,
        "reference_modules_derived_from_baseline_not_current": True,
        "same_clock_detection_inputs_state_alarm_led_buzzer": True,
        "active_fire_target_alarm_sound_and_aid_target_coverage_required": True,
        "protected_pages_and_overlay_exact": True,
        "seconds": round(time.time() - start, 2),
        "scope": "Actual extracted production HDMI wiring/default core parameters, plus paired original real fire/aid functional fixtures with explicitly accelerated arming/timeouts and reduced frame heights. CSI sensor, DDR/PHY transport, real lighting accuracy and physical sound are outside simulation. Style mode1 rendering is upstream of these wrappers and is verified separately.",
    }
    (V / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("TOP_V10_ALL_PROTECTION_PASS", flush=True)


if __name__ == "__main__":
    main()
