"""Actual mixer/HUD and extracted HDMI production chain, uniform RGB source.

This checks post-DDR display logic only. It does not substitute a numerical
colour function for the DUT, and does not claim to test sensor defects.
"""
from pathlib import Path
import hashlib,json,re,subprocess,time,sys
sys.stdout.reconfigure(encoding="utf-8")
R=Path(__file__).resolve().parents[1];H=R/"user_source/hdl_source"
V=R/"validation/yellow_dot_v11";V.mkdir(parents=True,exist_ok=True)
IV=Path(r"D:\anlu\iverilog\bin\iverilog.exe")
FILES=["design_top_wrapper.v","hdmi_mixer.v","fusion_hud.v","fusion_menu_rom.v","anlogic_logo_rom.v",
 "osd_char_lib.v","display_contrast.v","display_tone.dat","display_denoise_v9.v","display_cartoon_finish_v9.v",
 "color_luma_preserve.v","fusion_controls.v","fusion_flame_pipeline.v","visual_flame_alarm.v",
 "first_aid_detector.v","camera_frame_watchdog.v","alarm_board_io.v"]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

HEADER="""module actual_display_uniform(
 input S_csi_rx_clk,S_hdmi_pixel_clk,S_hdmi_rst_n,S_hdmi_user,
 input mix_vs_in,mix_hs_in,mix_de_in,mix_last_in,input[23:0] uniform_rgb,input[7:0] controls_hdmi,
 output S_hdmi_out_vsync,S_hdmi_out_hsync,S_hdmi_out_de,output[23:0] S_hdmi_out_data);
 wire[12:0] color_gain_r=4096,color_gain_b=4096;wire[5:0] color_control_hdmi=0;
 wire[1:0] fusion_mode=controls_hdmi[7:5]==1?controls_hdmi[4:3]:2'd0;
 wire S_csi_frame_start=S_hdmi_user,S_cam_cfg_done=1'b1,S_init_calib_complete=1'b1,S_lane_error_any=1'b0,wb_locked=1'b1;
 wire[23:0] mix_clean,mix_rgb;wire mix_vs,mix_hs,mix_de,mix_overlay;
 wire[3:0] O_led;wire O_buzzer_n,alarm,target,source_ok,video_lost,armed;
 wire[31:0] candidate_pixels;wire[11:0] target_x,target_y;
 wire[11:0] hud_x,hud_y;wire hud_hit;wire[23:0]hud_color;
 fusion_hud actual_hud(.I_clk(S_hdmi_pixel_clk),.I_rst_n(S_hdmi_rst_n),.I_x(hud_x),.I_y(hud_y),.I_control(controls_hdmi),
 .I_x_bcd(16'd0),.I_y_bcd(16'd0),.I_pixels_bcd(24'd0),.I_seconds_bcd(20'h00001),.I_exposure_bcd(20'h00640),
 .I_camera_fps_bcd(8'h60),.I_output_fps_bcd(8'h60),.I_gain_bcd(12'h016),.I_target(target),.I_alarm(alarm),.I_audio(1'b0),
 .I_cam_cfg(1'b1),.I_ddr_ready(1'b1),.I_source_ok(source_ok),.I_wb_locked(1'b1),.I_armed(armed),.I_debug(4'b1111),
 .I_aid_h_zone(2'd0),.I_aid_v_zone(2'd0),.I_color_control(6'd0),.O_hit(hud_hit),.O_color(hud_color));
 hdmi_mixer #(.H_OFFSET(0),.V_OFFSET(0),.IMG_WIDTH(1280),.IMG_HEIGHT(720),.DEBUG_MODE(0),.SHOW_COUNTER(0),.AUX_PIPELINED(1)) actual_mixer(
 .I_clk(S_hdmi_pixel_clk),.I_rst_n(S_hdmi_rst_n),.I_video_vsync(mix_vs_in),.I_video_hsync(mix_hs_in),.I_video_de(mix_de_in),
 .I_video_user(S_hdmi_user),.I_video_last(mix_last_in),.I_debug_status(4'b1111),.I_osd_enable(1'b1),.O_overlay_x(hud_x),.O_overlay_y(hud_y),
 .I_aux_hit(hud_hit),.I_aux_color(hud_color),.O_video_rd_en(),.I_video_rd_data(uniform_rgb),
 .O_hdmi_vsync(mix_vs),.O_hdmi_hsync(mix_hs),.O_hdmi_de(mix_de),.O_clean_data(mix_clean),.O_overlay_hit(mix_overlay),.O_hdmi_data(mix_rgb));
"""

TB=r"""`timescale 1ns/1ps
module yellow_uniform_tb;
 reg clk=0,sclk=0;always#5 clk=~clk;always#7 sclk=~sclk;
 // Drive a real control transition before the first active frame. Icarus
 // does not evaluate an always@* block for a variable input that has already
 // taken its initial value before that module's sensitivity wait begins.
 reg rst=0,user=0,vs=0,hs=0,de=0,last=0;reg[23:0]rgb=24'h606060;reg[7:0]control=8'hff;
 wire ov,oh,od;wire[23:0]pixel;
 actual_display_uniform dut(.S_csi_rx_clk(sclk),.S_hdmi_pixel_clk(clk),.S_hdmi_rst_n(rst),.S_hdmi_user(user),
 .mix_vs_in(vs),.mix_hs_in(hs),.mix_de_in(de),.mix_last_in(last),.uniform_rgb(rgb),.controls_hdmi(control),
 .S_hdmi_out_vsync(ov),.S_hdmi_out_hsync(oh),.S_hdmi_out_de(od),.S_hdmi_out_data(pixel));
 localparam NS=1669;reg[2:0]flags[0:NS-1];integer qx[0:NS-1],qy[0:NS-1],qp[0:NS-1],qf[0:NS-1];
 integer n=0,w,r,j,x=0,y=0,page=0,frame=0,active=0,outside=0,overlays=0;
 integer cp=0,cf=0,cx=0,cy=0,file0,file1,filep;reg colored,allowed;
 task tick;begin
  @(posedge clk);#1;w=n%NS;r=(w+1)%NS;flags[w]={vs,hs,de};qx[w]=x;qy[w]=y;qp[w]=page;qf[w]=frame;
  if(rst && n>NS+5)begin
   if({ov,oh,od}!==flags[r])$fatal(1,"actual mixer+HDMI sideband latency is not1669stages");
   if(od && qf[r]==0)begin
    active=active+1;cx=qx[r];cy=qy[r];cp=qp[r];cf=qf[r];
    if((^pixel)===1'bx)$fatal(1,"unknown uniform output pixel");
    colored=pixel[23:16]!=pixel[15:8] || pixel[15:8]!=pixel[7:0];
    // A few alignment pixels are allowed at the legal overlay boundaries;
    // the observed speck is far outside both rectangles.
    allowed=(cx<164 && cy<164) || (cx>=12 && cx<1044 && cy>=596 && cy<700);
    if(!allowed)begin outside=outside+1;if(colored)$fatal(1,"spontaneous non-grey point outside all overlays x%0d y%0d page%0d rgb%h",cx,cy,cp,pixel);end
    if(colored)begin
     overlays=overlays+1;
     if(cp==0)$fdisplay(file0,"%0d %0d %0d %0d %0d",cx,cy,pixel[23:16],pixel[15:8],pixel[7:0]);
     else $fdisplay(file1,"%0d %0d %0d %0d %0d",cx,cy,pixel[23:16],pixel[15:8],pixel[7:0]);
    end
   end
  end
  n=n+1;@(negedge clk);
 end endtask
 initial begin
  file0=$fopen("validation/yellow_dot_v11/uniform_base_colored.txt","w");file1=$fopen("validation/yellow_dot_v11/uniform_cartoon_colored.txt","w");
  for(j=0;j<NS;j=j+1)begin flags[j]=0;qx[j]=0;qy[j]=0;qp[j]=0;qf[j]=-1;end
  repeat(5)tick;rst=1;repeat(2000)tick;
  for(page=0;page<2;page=page+1)begin
   // Thirty-five complete blank lines warm every existing row FIFO after a
   // mode change; a discarded full active frame is unnecessary here.
   control=page==0?8'h00:8'h28;frame=-1;de=0;user=0;vs=0;hs=0;repeat(1650*35)tick;
   for(frame=0;frame<1;frame=frame+1)begin
    de=0;user=1;vs=1;repeat(5)tick;user=0;vs=0;repeat(1645)tick;
    for(y=0;y<720;y=y+1)begin
     for(x=0;x<1650;x=x+1)begin de=x<1280;last=x==1279;hs=x>=1390 && x<1430;tick;end
    end
    de=0;hs=0;repeat(1650*29)tick;
   end
  end
  frame=-1;de=0;user=0;vs=0;hs=0;repeat(NS+10)tick;
  $fclose(file0);$fclose(file1);
  if(active!=2*1280*720 || outside<1500000 || overlays<15000)$fatal(1,"uniform-frame coverage missing active%0d outside%0d overlays%0d",active,outside,overlays);
  filep=$fopen("validation/yellow_dot_v11/uniform_hdl_pass.txt","w");
  $fdisplay(filep,"YELLOW_UNIFORM_ACTUAL_TOP_PASS active=%0d outside_legal_overlay_grey=%0d real_overlay_colored=%0d registered_stages=1669",active,outside,overlays);$fclose(filep);
  $display("YELLOW_UNIFORM_ACTUAL_TOP_PASS active=%0d outside_legal_overlay_grey=%0d real_overlay_colored=%0d registered_stages=1669",active,outside,overlays);$finish;
 end
 initial begin#100000000;$fatal(1,"uniform fulltop timeout");end
endmodule
"""

def main():
 hashes={(H/f).relative_to(R).as_posix():sha(H/f) for f in FILES}
 source=(H/"design_top_wrapper.v").read_text(encoding="utf-8")
 start=source.index("    wire [25:0] color_gains_hdmi;");end=source.index("    hdmi_mixer #(",start)
 wrapper=V/"actual_display_uniform.v";wrapper.write_text(HEADER+source[start:end]+"\nendmodule\n",encoding="utf-8")
 tb=V/"yellow_uniform_tb.v";tb.write_text(TB,encoding="utf-8")
 sources=[H/f for f in FILES if f not in ["design_top_wrapper.v","display_tone.dat"]]
 start_time=time.time();binary=V/"uniform.vvp"
 marker=V/"uniform_hdl_pass.txt"
 if marker.exists():marker.unlink()
 for phase,cmd in [("compile",[IV,"-g2012","-s","yellow_uniform_tb","-o",binary,tb,wrapper]+sources),("run",[IV.with_name("vvp.exe"),binary])]:
  # Redirect directly to a file. Windows communicate(timeout=...) can expire
  # spuriously across host suspend/resume after its reader threads reach EOF.
  # The HDL has its own finite simulation-time timeout; exec remains pollable.
  logfile=V/f"uniform_{phase}.log"
  with logfile.open("w",encoding="utf-8") as output:
   p=subprocess.run(list(map(str,cmd)),cwd=R,stdout=output,stderr=subprocess.STDOUT)
  log=logfile.read_text(encoding="utf-8")
  assert p.returncode==0,(phase,log[-4000:])
  if phase=="run":assert marker.exists() and "YELLOW_UNIFORM_ACTUAL_TOP_PASS" in log;print(log[-1800:],flush=True)
 for f,h in hashes.items():assert sha(R/f)==h,("production source changed",f)
 try:
  from PIL import Image
  for name in ["base","cartoon"]:
   image=Image.new("RGB",(1280,720),(96,96,96))
   for line in (V/f"uniform_{name}_colored.txt").read_text().splitlines():
    x,y,r,g,b=map(int,line.split());image.putpixel((x,y),(r,g,b))
   image.save(V/f"uniform_{name}_rtl_overlay.png")
 except ImportError:
  pass
 result={"tests":{"actual_mixer_hud_hdmi_uniform":{"pass":True,"active_pixels":1843200,"outside_overlay_pixels_grey":True,"no_spontaneous_colored_dot":True,"registered_stages":1669}},
 "source_sha256":hashes,"oracle_sha256":{Path(__file__).relative_to(R).as_posix():sha(Path(__file__))},
 "generated_hdl_sha256":{p.relative_to(R).as_posix():sha(p) for p in [wrapper,tb]},"seconds":round(time.time()-start_time,2),
 "scope":"Real production mixer, real HUD/menu/logo ROMs and unmodified extracted post-DDR HDMI block with production dimensions/clocks. Flat grey source is supplied in place of DDR video; sensor, RAW/ISP/style, DDR/PHY, panel and phone are not modelled. The test does not rule out a defect in those excluded stages or identify the user-programmed bit."}
 (V/"uniform_result.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
 print("YELLOW_UNIFORM_VERIFICATION_PASS",flush=True)

if __name__=="__main__":main()
