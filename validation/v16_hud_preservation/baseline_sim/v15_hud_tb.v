`timescale 1ns/1ps
module chinese_hud_tb;
reg clk=0;always #5 clk=~clk;
reg rst=0;
reg [11:0] x=0,y=0;
// Exercise an actual transition from reset/invalid controls to the first page.
reg [7:0] control=8'hff;
reg [11:0] style_levels=12'h492;
reg [15:0] x_bcd=0,y_bcd=0;
reg [23:0] pixels_bcd=0;
reg [19:0] seconds_bcd=0,exposure_bcd=0,latency_bcd=0;
reg [7:0] camera_fps_bcd=0,output_fps_bcd=0,latency_status=0;
reg [11:0] gain_bcd=0;
reg [15:0] frame_id=0;
reg target=0,alarm=0,audio=0,cam_cfg=0,ddr_ready=0,source_ok=0,wb_locked=0,armed=0;
reg latency_valid=0,latency_repeat=0,latency_skip=0;
reg [3:0] debug=0;
reg [1:0] h_zone=0,v_zone=0;
reg [5:0] color=0;
wire hit;wire [23:0] rgb;
fusion_hud dut(.I_clk(clk),.I_rst_n(rst),.I_x(x),.I_y(y),.I_control(control),
 .I_x_bcd(x_bcd),.I_y_bcd(y_bcd),.I_pixels_bcd(pixels_bcd),
 .I_seconds_bcd(seconds_bcd),.I_exposure_bcd(exposure_bcd),
 .I_camera_fps_bcd(camera_fps_bcd),.I_output_fps_bcd(output_fps_bcd),.I_gain_bcd(gain_bcd),
 .I_latency_bcd(latency_bcd),.I_latency_frame_id(frame_id),.I_latency_status(latency_status),
 .I_latency_valid(latency_valid),.I_latency_repeat(latency_repeat),.I_latency_skip(latency_skip),
 .I_target(target),.I_alarm(alarm),.I_audio(audio),.I_cam_cfg(cam_cfg),.I_ddr_ready(ddr_ready),
 .I_source_ok(source_ok),.I_wb_locked(wb_locked),.I_armed(armed),.I_debug(debug),
 .I_aid_h_zone(h_zone),.I_aid_v_zone(v_zone),.I_color_control(color),.O_hit(hit),.O_color(rgb));
task render_page;
 input string filename;
 integer fd,xx,yy,previous_x,previous_y,have_previous;
 reg [1279:0] scanline;
 begin
  fd=$fopen(filename,"w");if(fd==0)$fatal(1,"cannot open page output");
  repeat(3)@(negedge clk);have_previous=0;scanline=0;
  for(yy=540;yy<720;yy=yy+1)begin
   for(xx=0;xx<1280;xx=xx+1)begin
    @(negedge clk);x=xx;y=yy;
    @(posedge clk);#1;
    if(have_previous)begin
     if(hit!==1'b0 && hit!==1'b1)$fatal(1,"unknown HUD hit previous=%d,%d input=%d,%d control=%h panel=%h address=%h mem0=%h code=%h glyph=%h font=%h row=%h col=%h",previous_x,previous_y,x,y,control,dut.panel,dut.u_menu.I_address,dut.u_menu.rom[0],dut.code,dut.glyph,dut.bits,dut.font_row1,dut.col2);
     if(rgb!==24'hfff200)$fatal(1,"unexpected HUD color");
     scanline[1279-previous_x]=hit;
     if(previous_x==1279)$fdisplay(fd,"%h",scanline);
    end
    previous_x=xx;previous_y=yy;have_previous=1;
   end
  end
  @(negedge clk);x=0;y=0;@(posedge clk);#1;
  if(hit!==1'b0 && hit!==1'b1)$fatal(1,"unknown flushed HUD hit");
  scanline[0]=hit;$fdisplay(fd,"%h",scanline);
  $fclose(fd);
 end
endtask
task probe_controls;
 input string filename;
 integer fd,i,px,py,pc,pl,have_previous;
 begin
  fd=$fopen(filename,"w");have_previous=0;
  repeat(3)@(negedge clk);
  for(i=0;i<4096;i=i+1)begin
   @(negedge clk);
   case(i%8)0:control=8'h00;1:control=8'h20;2:control=8'h28;3:control=8'h58;
     4:control=8'h68;5:control=8'h70;6:control=8'ha0;default:control=8'h78;endcase
   x=(i*37)%1280;y=540+(i*53)%180;
   // Half of the samples concentrate on the level glyph while both the
   // panel and packed remembered levels change on consecutive clocks.
   if(i%2==0)begin
    control=8'h20+((i/2)%4)*8;
    x=16+12*32+((i/8)%32);y=552+((i/256)%32);
   end
   style_levels=((i%5)<<9)|(((i+1)%5)<<6)|(((i+2)%5)<<3)|((i+3)%5);
   @(posedge clk);#1;
   if(have_previous)$fdisplay(fd,"%d %d %d %d %b",px,py,pc,pl,hit);
   px=x;py=y;pc=control;pl=style_levels;have_previous=1;
  end
  @(negedge clk);x=0;y=0;@(posedge clk);#1;
  $fdisplay(fd,"%d %d %d %d %b",px,py,pc,pl,hit);$fclose(fd);
 end
endtask
initial begin
 repeat(4)@(negedge clk);
 if(hit!==0)$fatal(1,"HUD not blank in reset");rst=1;
@(negedge clk);control=8'h0; style_levels=12'h492; color=6'h0; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h1; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'ha5;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/page_00.hex");
@(negedge clk);control=8'h20; style_levels=12'h492; color=6'h0; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h1; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'ha5;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/page_04.hex");
@(negedge clk);control=8'h28; style_levels=12'h492; color=6'h0; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h1; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'ha5;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/page_05.hex");
@(negedge clk);control=8'h30; style_levels=12'h492; color=6'h0; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h1; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'ha5;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/page_06.hex");
@(negedge clk);control=8'h38; style_levels=12'h492; color=6'h0; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h1; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'ha5;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/page_07.hex");
@(negedge clk);control=8'h40; style_levels=12'h492; color=6'h0; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h1; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'ha5;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/page_08.hex");
@(negedge clk);control=8'h48; style_levels=12'h492; color=6'h0; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h1; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'ha5;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/page_09.hex");
@(negedge clk);control=8'h50; style_levels=12'h492; color=6'h0; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h1; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'ha5;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/page_10.hex");
@(negedge clk);control=8'h58; style_levels=12'h492; color=6'h0; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h1; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'ha5;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/page_11.hex");
@(negedge clk);control=8'h60; style_levels=12'h492; color=6'h0; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h1; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'ha5;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/page_12.hex");
@(negedge clk);control=8'h68; style_levels=12'h492; color=6'h0; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h1; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'ha5;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/page_13.hex");
@(negedge clk);control=8'h70; style_levels=12'h492; color=6'h0; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h1; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'ha5;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/page_14.hex");
@(negedge clk);control=8'h78; style_levels=12'h492; color=6'h0; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h1; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'ha5;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/page_15.hex");
@(negedge clk);control=8'h80; style_levels=12'h492; color=6'h0; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h1; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'ha5;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/page_16.hex");
@(negedge clk);control=8'h88; style_levels=12'h492; color=6'h0; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h1; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'ha5;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/page_17.hex");
@(negedge clk);control=8'h90; style_levels=12'h492; color=6'h0; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h1; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'ha5;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/page_18.hex");
@(negedge clk);control=8'h98; style_levels=12'h492; color=6'h0; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h1; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'ha5;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/page_19.hex");
@(negedge clk);control=8'he0; style_levels=12'h492; color=6'h0; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h1; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'ha5;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/page_28.hex");
@(negedge clk);control=8'h0; style_levels=12'h492; color=6'h34; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h1; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'ha5;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/base_cool.hex");
@(negedge clk);control=8'h0; style_levels=12'h492; color=6'hc; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h1; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'ha5;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/base_warm.hex");
@(negedge clk);control=8'h0; style_levels=12'h492; color=6'h1; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h1; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'ha5;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/base_magenta.hex");
@(negedge clk);control=8'h0; style_levels=12'h492; color=6'h2; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h1; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'ha5;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/base_green.hex");
@(negedge clk);control=8'h0; style_levels=12'h492; color=6'h3; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h1; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'ha5;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/base_reserved_tint.hex");
@(negedge clk);control=8'h0; style_levels=12'h492; color=6'h20; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h1; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'ha5;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/base_temperature_min.hex");
@(negedge clk);control=8'h0; style_levels=12'h492; color=6'h1c; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h1; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'ha5;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/base_temperature_max.hex");
@(negedge clk);control=8'h58; style_levels=12'h492; color=6'h0; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h0; v_zone=2'h0; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h1; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'ha5;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/aid_v0_h0.hex");
@(negedge clk);control=8'h58; style_levels=12'h492; color=6'h0; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h1; v_zone=2'h0; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h1; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'ha5;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/aid_v0_h1.hex");
@(negedge clk);control=8'h58; style_levels=12'h492; color=6'h0; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h2; v_zone=2'h0; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h1; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'ha5;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/aid_v0_h2.hex");
@(negedge clk);control=8'h58; style_levels=12'h492; color=6'h0; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h0; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h1; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'ha5;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/aid_v1_h0.hex");
@(negedge clk);control=8'h58; style_levels=12'h492; color=6'h0; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h1; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'ha5;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/aid_v1_h1.hex");
@(negedge clk);control=8'h58; style_levels=12'h492; color=6'h0; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h2; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h1; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'ha5;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/aid_v1_h2.hex");
@(negedge clk);control=8'h58; style_levels=12'h492; color=6'h0; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h0; v_zone=2'h2; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h1; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'ha5;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/aid_v2_h0.hex");
@(negedge clk);control=8'h58; style_levels=12'h492; color=6'h0; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h1; v_zone=2'h2; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h1; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'ha5;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/aid_v2_h1.hex");
@(negedge clk);control=8'h58; style_levels=12'h492; color=6'h0; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h2; v_zone=2'h2; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h1; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'ha5;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/aid_v2_h2.hex");
@(negedge clk);control=8'h58; style_levels=12'h492; color=6'h0; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h3; v_zone=2'h3; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h1; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'ha5;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/aid_reserved_zones.hex");
@(negedge clk);control=8'h58; style_levels=12'h492; color=6'h0; target=1'h0; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h1; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'ha5;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/aid_no_target.hex");
@(negedge clk);control=8'h68; style_levels=12'h492; color=6'h0; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h0; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'h3;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/latency_invalid.hex");
@(negedge clk);control=8'h68; style_levels=12'h492; color=6'h0; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'hcafe; latency_valid=1'h1; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'hdf;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/latency_hex_cafe.hex");
@(negedge clk);control=8'h68; style_levels=12'h492; color=6'h0; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'hdead; latency_valid=1'h1; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'hbc;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/latency_hex_dead.hex");
@(negedge clk);control=8'h68; style_levels=12'h492; color=6'h0; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h0; frame_id=16'h0; latency_valid=1'h1; latency_repeat=1'h0; latency_skip=1'h0; latency_status=8'h0;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/latency_zero.hex");
@(negedge clk);control=8'h0; style_levels=12'h492; color=6'h0; target=1'h0; alarm=1'h0; audio=1'h0; cam_cfg=1'h0; ddr_ready=1'h0; source_ok=1'h0; wb_locked=1'h0; armed=1'h0; debug=4'h0; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h0; latency_repeat=1'h0; latency_skip=1'h0; latency_status=8'h80;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/flags_off_00.hex");
@(negedge clk);control=8'h40; style_levels=12'h492; color=6'h0; target=1'h0; alarm=1'h0; audio=1'h0; cam_cfg=1'h0; ddr_ready=1'h0; source_ok=1'h0; wb_locked=1'h0; armed=1'h0; debug=4'h0; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h0; latency_repeat=1'h0; latency_skip=1'h0; latency_status=8'h80;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/flags_off_40.hex");
@(negedge clk);control=8'h48; style_levels=12'h492; color=6'h0; target=1'h0; alarm=1'h0; audio=1'h0; cam_cfg=1'h0; ddr_ready=1'h0; source_ok=1'h0; wb_locked=1'h0; armed=1'h0; debug=4'h0; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h0; latency_repeat=1'h0; latency_skip=1'h0; latency_status=8'h80;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/flags_off_48.hex");
@(negedge clk);control=8'h50; style_levels=12'h492; color=6'h0; target=1'h0; alarm=1'h0; audio=1'h0; cam_cfg=1'h0; ddr_ready=1'h0; source_ok=1'h0; wb_locked=1'h0; armed=1'h0; debug=4'h0; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h0; latency_repeat=1'h0; latency_skip=1'h0; latency_status=8'h80;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/flags_off_50.hex");
@(negedge clk);control=8'h58; style_levels=12'h492; color=6'h0; target=1'h0; alarm=1'h0; audio=1'h0; cam_cfg=1'h0; ddr_ready=1'h0; source_ok=1'h0; wb_locked=1'h0; armed=1'h0; debug=4'h0; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h0; latency_repeat=1'h0; latency_skip=1'h0; latency_status=8'h80;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/flags_off_58.hex");
@(negedge clk);control=8'h60; style_levels=12'h492; color=6'h0; target=1'h0; alarm=1'h0; audio=1'h0; cam_cfg=1'h0; ddr_ready=1'h0; source_ok=1'h0; wb_locked=1'h0; armed=1'h0; debug=4'h0; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h0; latency_repeat=1'h0; latency_skip=1'h0; latency_status=8'h80;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/flags_off_60.hex");
@(negedge clk);control=8'h68; style_levels=12'h492; color=6'h0; target=1'h0; alarm=1'h0; audio=1'h0; cam_cfg=1'h0; ddr_ready=1'h0; source_ok=1'h0; wb_locked=1'h0; armed=1'h0; debug=4'h0; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h0; latency_repeat=1'h0; latency_skip=1'h0; latency_status=8'h80;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/flags_off_68.hex");
@(negedge clk);control=8'h70; style_levels=12'h492; color=6'h0; target=1'h0; alarm=1'h0; audio=1'h0; cam_cfg=1'h0; ddr_ready=1'h0; source_ok=1'h0; wb_locked=1'h0; armed=1'h0; debug=4'h0; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h0; latency_repeat=1'h0; latency_skip=1'h0; latency_status=8'h80;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/flags_off_70.hex");
@(negedge clk);control=8'h78; style_levels=12'h492; color=6'h0; target=1'h0; alarm=1'h0; audio=1'h0; cam_cfg=1'h0; ddr_ready=1'h0; source_ok=1'h0; wb_locked=1'h0; armed=1'h0; debug=4'h0; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h0; latency_repeat=1'h0; latency_skip=1'h0; latency_status=8'h80;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/flags_off_78.hex");
@(negedge clk);control=8'ha0; style_levels=12'h492; color=6'h0; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h1; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'ha5;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/invalid_group_5.hex");
@(negedge clk);control=8'hc0; style_levels=12'h492; color=6'h0; target=1'h1; alarm=1'h1; audio=1'h1; cam_cfg=1'h1; ddr_ready=1'h1; source_ok=1'h1; wb_locked=1'h1; armed=1'h1; debug=4'ha; h_zone=2'h1; v_zone=2'h1; x_bcd=16'h1234; y_bcd=16'h5678; pixels_bcd=24'h123456; seconds_bcd=20'h12345; exposure_bcd=20'h54321; camera_fps_bcd=8'h24; output_fps_bcd=8'h60; gain_bcd=12'h123; latency_bcd=20'h3579; frame_id=16'h6c02; latency_valid=1'h1; latency_repeat=1'h1; latency_skip=1'h1; latency_status=8'ha5;
render_page("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/v16_hud_preservation/baseline_sim/invalid_group_6.hex");
$display("BASELINE_V15_HUD_RTL_PASS");$finish;
end
endmodule
