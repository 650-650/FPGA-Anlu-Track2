"""V12 observer/HUD and explicitly allowed source-alignment regression.

Only generated fixtures/results live under validation/latency_v12_preservation.
No production source or historical baseline is changed by this verifier.
"""
from pathlib import Path
import hashlib,json,re,subprocess,time

R=Path(__file__).resolve().parents[1]
B=R.with_name('07_stylize_flame_fusion_v11_cartoon_regions')
H=R/'user_source/hdl_source';BH=B/'user_source/hdl_source'
V=R/'validation/latency_v12_preservation'
IV=Path(r'D:\anlu\iverilog\bin\iverilog.exe')

def read(p):return p.read_text(encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def norm(s):
    s=re.sub(r'"[^"\r\n]*/(curve_srgb|curve_gain|curve_gain_scaled|median_majority|display_tone)\.dat"',lambda m:'"@ROM/'+m[1]+'.dat"',s)
    return re.sub(r'\s+','',re.sub(r'/\*.*?\*/|//[^\n]*','',s,flags=re.S))
def replace(s,old,new):
    assert old in s,old[:100]
    return s.replace(old,new,1)
def restored_video(name,s):
    if name=='video_in.v':
        s=replace(s,'module video_in #(parameter integer INPUT_ALIGN_CYCLES=24)(','module video_in (')
        s=replace(s,'    input wire         I_ddr_user_ready,\n    output wire O_observe_frame_start,\n    output wire [1:0] O_observe_write_slot,\n    output wire O_observe_overflow\n','    input wire         I_ddr_user_ready\n')
        # This is a deliberate functional exception, not observation-only:
        # allow only the specified equal 24-cycle data/valid transport.
        a=s.index('    // The existing SOF reset spans')
        b=s.index('    wire S_input_fifo_full;',a)
        alignment=s[a:b]
        expected='''wire [127:0] aligned_camera_data;
wire aligned_camera_valid;
generate if(INPUT_ALIGN_CYCLES>0)begin: input_alignment
reg [127:0] data_pipe[0:INPUT_ALIGN_CYCLES-1];
reg [INPUT_ALIGN_CYCLES-1:0] valid_pipe;
integer n;
always @(posedge I_camera_clk)begin
data_pipe[0]<=I_camera_data;
for(n=1;n<INPUT_ALIGN_CYCLES;n=n+1)data_pipe[n]<=data_pipe[n-1];
end
always @(posedge I_camera_clk or negedge I_rst_n)
if(!I_rst_n)valid_pipe<=0;
else valid_pipe<=(valid_pipe<<1) | {{(INPUT_ALIGN_CYCLES-1){1'b0}},I_camera_valid};
assign aligned_camera_data=data_pipe[INPUT_ALIGN_CYCLES-1];
assign aligned_camera_valid=valid_pipe[INPUT_ALIGN_CYCLES-1];
end else begin: original_input
assign aligned_camera_data=I_camera_data;
assign aligned_camera_valid=I_camera_valid;
end endgenerate'''
        assert norm(alignment)==norm(expected),'Source alignment is more than the approved bit-preserving transport'
        s=s[:a]+s[b:]
        s=replace(s,'    wire S_input_fifo_full;\n    assign O_observe_frame_start=S_frame_start;\n    assign O_observe_write_slot=S_video_in_wp;\n    assign O_observe_overflow=aligned_camera_valid && S_input_fifo_full;\n','')
        s=replace(s,'.we         ( aligned_camera_valid ),','.we         ( I_camera_valid     ),')
        s=replace(s,'.di         ( aligned_camera_data  ),','.di         ( I_camera_data      ),')
        s=replace(s,'.full_flag  (S_input_fifo_full),','.full_flag  (),')
    else:
        s=replace(s,'    output reg[23:0]  O_vdieo_data,\n    output wire O_observe_read_start,\n    output wire [1:0] O_observe_read_slot,\n    output wire O_observe_fifo_reset,\n    output wire O_observe_underflow\n','    output reg[23:0]  O_vdieo_data\n')
        s=replace(s,'    assign O_observe_read_start=S_video_frame_start;\n    assign O_observe_read_slot=I_video_out_rp;\n    assign O_observe_fifo_reset=S_fifo_rst;\n    assign O_observe_underflow=S_fifo_rd_en && S_fifo_emtpy;\n','')
    return s
def restored_top(s):
    s=replace(s,'    wire latency_write_start,latency_read_start,latency_input_overflow;\n    wire latency_read_fifo_reset,latency_output_underflow;\n    wire [1:0] latency_write_slot,latency_read_slot;\n','')
    s=replace(s,'        .I_ddr_user_ready     ( S_ddr_user_ready      ),\n        .O_observe_frame_start(latency_write_start),.O_observe_write_slot(latency_write_slot),\n        .O_observe_overflow(latency_input_overflow)\n','        .I_ddr_user_ready     ( S_ddr_user_ready      )\n')
    s=replace(s,'        .O_vdieo_data        ( S_video_rd_data      ),\n        .O_observe_read_start(latency_read_start),.O_observe_read_slot(latency_read_slot),\n        .O_observe_fifo_reset(latency_read_fifo_reset),.O_observe_underflow(latency_output_underflow)\n','        .O_vdieo_data        ( S_video_rd_data      )\n')
    a=s.index('    wire [31:0] latency_us;');b=s.index('    wire [15:0] xb,yb;',a)
    s=s[:a]+s[b:]
    s=replace(s,'        .I_latency_us(latency_hud_us),.O_latency_bcd(latency_bcd),\n','')
    s=replace(s,'        .I_output_fps_bcd(output_fps_bcd),.I_gain_bcd(gain_bcd),\n        .I_latency_bcd(latency_bcd),.I_latency_frame_id(latency_hud_id),\n        .I_latency_valid(latency_hud_flags[2]),.I_latency_repeat(latency_hud_flags[1]),.I_latency_skip(latency_hud_flags[0]),\n        .I_target(target),.I_alarm(alarm),','        .I_output_fps_bcd(output_fps_bcd),.I_gain_bcd(gain_bcd),.I_target(target),.I_alarm(alarm),')
    return s
def parse_rom(text,size,default=32):
    arr=[default]*size
    for address,base,value in re.findall(r"rom\[(\d+)\]=8'([dh])([0-9a-fA-F]+);",text):arr[int(address)]=int(value,16 if base=='h' else 10)
    return arr
def namespace(s):
    for old,new in [('fusion_telemetry','reference_telemetry'),('fusion_hud','reference_hud'),('fusion_menu_rom','reference_menu'),('fusion_font_rom','reference_font')]:s=re.sub(r'\b'+old+r'\b',new,s)
    return s

HUD_TB=r'''`timescale 1ns/1ps
module preservation_hud_tb;
reg clk=0;always #5 clk=~clk;reg rst=0;
reg[11:0]x=0,y=0;reg[7:0]ctl=0;reg target=1;reg[5:0]trim=57;
reg[19:0]latency=20'h12345;reg[15:0]fid=16'ha5f2;reg valid=1,rep=0,skip=1;
wire nhit,ohit;wire[23:0]ncolor,ocolor;
fusion_hud n(.I_clk(clk),.I_rst_n(rst),.I_x(x),.I_y(y),.I_control(ctl),
 .I_x_bcd(16'h1234),.I_y_bcd(16'h5678),.I_pixels_bcd(24'h987654),.I_seconds_bcd(20'h12345),
 .I_exposure_bcd(20'h23456),.I_camera_fps_bcd(8'h60),.I_output_fps_bcd(8'h61),.I_gain_bcd(12'h256),
 .I_target(target),.I_alarm(1'b1),.I_audio(1'b1),.I_cam_cfg(1'b1),.I_ddr_ready(1'b1),
 .I_source_ok(1'b1),.I_wb_locked(1'b1),.I_armed(1'b1),.I_debug(4'b1011),.I_aid_h_zone(2'd1),.I_aid_v_zone(2'd2),
 .I_color_control(trim),.I_latency_bcd(latency),.I_latency_frame_id(fid),.I_latency_valid(valid),
 .I_latency_repeat(rep),.I_latency_skip(skip),.O_hit(nhit),.O_color(ncolor));
reference_hud o(.I_clk(clk),.I_rst_n(rst),.I_x(x),.I_y(y),.I_control(ctl),
 .I_x_bcd(16'h1234),.I_y_bcd(16'h5678),.I_pixels_bcd(24'h987654),.I_seconds_bcd(20'h12345),
 .I_exposure_bcd(20'h23456),.I_camera_fps_bcd(8'h60),.I_output_fps_bcd(8'h61),.I_gain_bcd(12'h256),
 .I_target(target),.I_alarm(1'b1),.I_audio(1'b1),.I_cam_cfg(1'b1),.I_ddr_ready(1'b1),
 .I_source_ok(1'b1),.I_wb_locked(1'b1),.I_armed(1'b1),.I_debug(4'b1011),.I_aid_h_zone(2'd1),.I_aid_v_zone(2'd2),
 .I_color_control(trim),.O_hit(ohit),.O_color(ocolor));
reg[7:0]expected_code[0:255];reg[7:0]font[0:1023];
integer state,row,col,fr,fc,k,a,checks=0,glyph_checks=0,bitmap_checks=0;
reg[7:0]ec;reg[6:0]eg;reg[7:0]eb;reg expected_hit;
function[6:0]hexchar;input[3:0]v;begin hexchar=v<10?48+v:65+v-10;end endfunction
function[6:0]expected_glyph;input[7:0]c;reg[5:0]slot;reg[3:0]d;begin
 slot=c[5:0];expected_glyph=c[6:0];
 if(c[7])begin
  if(slot>=59)begin d=latency[(63-slot)*4+:4];expected_glyph=valid?48+d:45;end
  else if(slot==43)expected_glyph=48+valid;
  else if(slot>=44 && slot<=47)expected_glyph=hexchar(fid[(47-slot)*4+:4]);
  else if(slot==48)expected_glyph=48+rep;
  else if(slot==49)expected_glyph=48+skip;
  else expected_glyph=32;
 end
end endfunction
task tick;begin @(posedge clk);#1;end endtask
initial begin
 $readmemh("__EXPECTED__",expected_code);$readmemh("__FONT__",font);
 repeat(5)tick;@(negedge clk);rst=1;
 for(state=0;state<32;state=state+1)begin
  if(state!=13)begin
   @(negedge clk);ctl=state<<3;target=state[0];trim=state[5:0];x=0;y=0;
   repeat(4)tick;
   for(row=0;row<4;row=row+1)for(fr=0;fr<8;fr=fr+1)
    for(col=0;col<64;col=col+1)for(fc=0;fc<8;fc=fc+1)begin
     @(negedge clk);x=16+16*col+2*fc;y=600+24*row+2*fr;
     tick;if(nhit!==ohit || ncolor!==ocolor)$fatal(1,"non-latency panel pixel changed state=%d x=%d y=%d",state,x,y);
     checks=checks+1;
    end
  end
 end
 for(state=0;state<4;state=state+1)begin
  @(negedge clk);ctl=8'h68;valid=state[0];rep=state[1];skip=!state[1];target=0;
  latency=state<2?20'h12345:20'h99999;fid=state<2?16'ha5f2:16'h019c;
  for(row=0;row<4;row=row+1)for(col=0;col<64;col=col+1)begin
   a=row*64+col;ec=expected_code[a];eg=expected_glyph(ec);
   @(negedge clk);x=16+16*col;y=600+24*row;tick;
   if(n.code!==ec || n.glyph!==eg)$fatal(1,"latency glyph wrong case=%d a=%d code=%h/%h glyph=%h/%h",state,a,n.code,ec,n.glyph,eg);
   glyph_checks=glyph_checks+1;
   for(fr=0;fr<8;fr=fr+1)for(fc=0;fc<8;fc=fc+1)begin
    @(negedge clk);x=16+16*col+2*fc;y=600+24*row+2*fr;
    repeat(3)tick;eb=font[eg*8+fr];expected_hit=eb[7-fc];
    if(nhit!==expected_hit || ncolor!==24'hfff200)$fatal(1,"latency bitmap wrong a=%d fr=%d fc=%d",a,fr,fc);
    bitmap_checks=bitmap_checks+1;
   end
  end
 end
 $display("V12_HUD_PROTECTION_PASS pixels=%0d glyphs=%0d bitmap=%0d",checks,glyph_checks,bitmap_checks);$finish;
end
initial begin #15000000;$fatal(1,"HUD timeout");end
endmodule
'''

TELEM_TB=r'''`timescale 1ns/1ps
module preservation_telemetry_tb;
reg clk=0,sclk=0;always #5 clk=~clk;always #7 sclk=~sclk;
reg rst=0,frame=0,sframe=0;reg[11:0]x=1234,y=567;reg[31:0]pixels=123456;
reg[15:0]exposure=12345,gain=256;reg[31:0]latency=0;
wire[123:0]ncommon,ocommon;wire[19:0]latbcd;
fusion_telemetry #(.CLK_HZ(1000)) n(.I_clk(clk),.I_rst_n(rst),.I_frame(frame),.I_source_clk(sclk),.I_source_frame(sframe),
 .I_x(x),.I_y(y),.I_pixels(pixels),.I_exposure(exposure),.I_gain(gain),.I_latency_us(latency),.O_latency_bcd(latbcd),
 .O_x_bcd(ncommon[123:108]),.O_y_bcd(ncommon[107:92]),.O_pixels_bcd(ncommon[91:68]),.O_seconds_bcd(ncommon[67:48]),
 .O_exposure_bcd(ncommon[47:28]),.O_camera_fps_bcd(ncommon[27:20]),.O_output_fps_bcd(ncommon[19:12]),.O_gain_bcd(ncommon[11:0]));
reference_telemetry #(.CLK_HZ(1000)) o(.I_clk(clk),.I_rst_n(rst),.I_frame(frame),.I_source_clk(sclk),.I_source_frame(sframe),
 .I_x(x),.I_y(y),.I_pixels(pixels),.I_exposure(exposure),.I_gain(gain),
 .O_x_bcd(ocommon[123:108]),.O_y_bcd(ocommon[107:92]),.O_pixels_bcd(ocommon[91:68]),.O_seconds_bcd(ocommon[67:48]),
 .O_exposure_bcd(ocommon[47:28]),.O_camera_fps_bcd(ocommon[27:20]),.O_output_fps_bcd(ocommon[19:12]),.O_gain_bcd(ocommon[11:0]));
integer clocks=0,cases=0,i,j,value;reg[19:0]expected;
function[19:0]bcd5;input integer v;integer k;reg[19:0]b;begin
 b=0;for(k=0;k<5;k=k+1)begin b[k*4+:4]=v%10;v=v/10;end bcd5=b;
end endfunction
always @(posedge clk)begin #1;if(rst)begin
 if(ncommon!==ocommon)$fatal(1,"legacy telemetry changed n=%h o=%h",ncommon,ocommon);clocks=clocks+1;
end end
always @(posedge sclk)if(rst)sframe<=clocks%113<4;
initial begin
 repeat(5)@(negedge clk);rst=1;
 for(i=0;i<18;i=i+1)begin
  case(i)
   0:value=0;1:value=1;2:value=9;3:value=10;4:value=999;5:value=1000;
   6:value=12345;7:value=33333;8:value=999990;9:value=999999;
   default:value=((i*81773)^32'h5a31)%1000000;
  endcase
  @(negedge clk);latency=value;x=(i*173)%4096;y=(i*269)%4096;pixels=i*23456;exposure=i*567;gain=i*23;frame=1;
  @(negedge clk);frame=0;
  for(j=0;j<330;j=j+1)@(negedge clk);
  expected=bcd5(value/10);
  if(latbcd!==expected)$fatal(1,"latency BCD wrong us=%d got=%h expected=%h",value,latbcd,expected);
  cases=cases+1;
 end
 $display("V12_TELEMETRY_PROTECTION_PASS clocks=%0d latency_cases=%0d",clocks,cases);$finish;
end
initial begin #1000000;$fatal(1,"telemetry timeout");end
endmodule
'''

ALIGN_TB=r'''`timescale 1ns/1ps
module preservation_alignment_tb;
reg cclk=0,dclk=0;always #5 cclk=~cclk;always #7 dclk=~dclk;
reg rst=0,sof=0,valid=0,ready=1,busy=0,pause=0;reg[127:0]data=0;
wire[156:0]base_state,zero_state;
video_in n24(.I_rst_n(rst),.I_camera_clk(cclk),.I_camera_frame_start(sof),.I_camera_valid(valid),.I_camera_data(data),
 .I_mipi_rx_error(1'b0),.I_ddr_clk(dclk),.I_display_pause(pause),.I_video_out_rd_busy(busy),.I_ddr_user_ready(ready));
video_in #(.INPUT_ALIGN_CYCLES(0)) n0(.I_rst_n(rst),.I_camera_clk(cclk),.I_camera_frame_start(sof),.I_camera_valid(valid),.I_camera_data(data),
 .I_mipi_rx_error(1'b0),.I_ddr_clk(dclk),.I_display_pause(pause),.I_video_out_rd_busy(busy),.I_ddr_user_ready(ready),
 .O_video_in_wr_busy(zero_state[156]),.O_video_out_rp(zero_state[155:154]),.O_ddr_user_wr_en(zero_state[153]),
 .O_ddr_user_addr(zero_state[152:128]),.O_ddr_user_wr_data(zero_state[127:0]));
reference_video_in old(.I_rst_n(rst),.I_camera_clk(cclk),.I_camera_frame_start(sof),.I_camera_valid(valid),.I_camera_data(data),
 .I_mipi_rx_error(1'b0),.I_ddr_clk(dclk),.I_display_pause(pause),.I_video_out_rd_busy(busy),.I_ddr_user_ready(ready),
 .O_video_in_wr_busy(base_state[156]),.O_video_out_rp(base_state[155:154]),.O_ddr_user_wr_en(base_state[153]),
 .O_ddr_user_addr(base_state[152:128]),.O_ddr_user_wr_data(base_state[127:0]));
reg[127:0]expected_data[0:23];reg[23:0]expected_valid=0;
integer i,j,n=0,transport_checks=0,bypass_checks=0,policy_checks=0;
reg[31:0]rng=32'h3196a75c;
always @(posedge cclk)begin
 if(!rst)expected_valid=0;
 else begin
  for(j=23;j>0;j=j-1)expected_data[j]=expected_data[j-1];
  expected_data[0]=data;expected_valid={expected_valid[22:0],valid};
 end
 #1;
 if(n24.aligned_camera_valid!==expected_valid[23])$fatal(1,"valid not delayed exactly24");
 if(expected_valid[23])begin
  if(n24.U_w128_d512_fifo.di!==expected_data[23])$fatal(1,"128bit sample changed by alignment");
  transport_checks=transport_checks+1;
 end
 if(n24.U_w128_d512_fifo.we!==expected_valid[23])$fatal(1,"FIFO valid not aligned");
 if(n0.U_w128_d512_fifo.we!==valid || n0.U_w128_d512_fifo.di!==data ||
    old.U_w128_d512_fifo.we!==valid || old.U_w128_d512_fifo.di!==data)$fatal(1,"parameter0 not original input");
 bypass_checks=bypass_checks+1;
end
always @(posedge dclk)begin
 #1;if(base_state!==zero_state)$fatal(1,"parameter0 reset/pointer/write arbitration changed");
 policy_checks=policy_checks+1;
end
initial begin
 for(i=0;i<24;i=i+1)expected_data[i]=0;
 repeat(8)@(negedge cclk);rst=1;
 for(i=0;i<1600;i=i+1)begin
  @(negedge cclk);rng={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};
  data={rng,~rng,rng^32'h5a3c08e1,rng+32'd123};valid=rng[0]||rng[4];sof=i%201==0;
  ready=rng[7]||rng[8];busy=i%89<7;pause=i>800 && i<840;
  if(i==713)rst=0;if(i==719)rst=1;
 end
 @(negedge cclk);valid=0;sof=0;repeat(35)@(negedge cclk);
 if(transport_checks<1000)$fatal(1,"transport coverage too small %d",transport_checks);
 $display("V12_ALIGNMENT_PROTECTION_PASS words=%0d bypass=%0d policy=%0d",transport_checks,bypass_checks,policy_checks);$finish;
end
initial begin #100000;$fatal(1,"alignment timeout");end
endmodule

// Transport/policy harness only. Real generated FIFO/DDR behavior is covered
// separately by latency_v12_video_verify; this stub exposes unchanged pins.
module w128_d512_fifo(input rst,clkw,clkr,we,re,input[127:0]di,
 output reg[127:0]dout,output valid,full_flag,empty_flag,afull,aempty,output[8:0]wrusedw,rdusedw);
 assign valid=re;assign full_flag=0;assign empty_flag=0;assign afull=0;assign aempty=0;
 assign wrusedw=0;assign rdusedw=300;
 always @(posedge clkr or posedge rst)if(rst)dout<=0;else if(re)dout<=dout+1'b1;
endmodule
'''

SNAPSHOT_TB=r'''`timescale 1ns/1ps
module preservation_snapshot_tb;
reg clk=0;always #5 clk=~clk;reg rst=0,frame=0;
reg[31:0]latency_us=0;reg[15:0]fid=0;reg valid=0,rep=0,skip=0;
wire[31:0]frozen_us;wire[15:0]frozen_id;wire[2:0]frozen_flags;wire[19:0]bcd;
snapshot_actual actual(.S_hdmi_pixel_clk(clk),.S_hdmi_rst_n(rst),.S_hdmi_user(frame),
 .latency_us(latency_us),.latency_frame_id(fid),.latency_valid(valid),.latency_repeat(rep),.latency_skip(skip),
 .O_us(frozen_us),.O_id(frozen_id),.O_flags(frozen_flags));
fusion_telemetry n(.I_clk(clk),.I_rst_n(rst),.I_frame(frame),.I_source_clk(clk),.I_source_frame(1'b0),
 .I_x(12'd0),.I_y(12'd0),.I_pixels(32'd0),.I_exposure(16'd0),.I_gain(16'd0),.I_latency_us(frozen_us),.O_latency_bcd(bcd));
reg[50:0]expected;integer frames=0,cycles=0,i,j,value;reg[19:0]expected_bcd;
function[19:0]bcd5;input integer v;integer k;reg[19:0]b;begin
 b=0;for(k=0;k<5;k=k+1)begin b[k*4+:4]=v%10;v=v/10;end bcd5=b;
end endfunction
always @(posedge clk)begin
 if(!rst)expected=0;else if(frame)expected={latency_us,fid,valid,rep,skip};
 #1;if({frozen_us,frozen_id,frozen_flags}!==expected)$fatal(1,"HUD tuple torn or updated without frame commit");cycles=cycles+1;
end
initial begin
 repeat(5)@(negedge clk);rst=1;
 for(i=0;i<12;i=i+1)begin
  @(negedge clk);value=13721+i*37123;latency_us=value;fid=16'hf012+i;valid=i[0];rep=i[1];skip=i[2];frame=1;
  expected_bcd=bcd5(value/10);
  @(negedge clk);frame=0;
  for(j=0;j<360;j=j+1)begin
   @(negedge clk);latency_us=(value+j*977)%1000000;fid=i+j;valid=j[0];rep=j[2];skip=!j[0];
  end
  if(bcd!==expected_bcd)$fatal(1,"late verdict changed BCD/frame tuple got=%h expected=%h",bcd,expected_bcd);
  frames=frames+1;
 end
 $display("V12_SNAPSHOT_PROTECTION_PASS frames=%0d clocks=%0d",frames,cycles);$finish;
end
initial begin #1000000;$fatal(1,"snapshot timeout");end
endmodule
'''

def run_test(name,top,tb,files):
    path=V/(name+'_tb.v');path.write_text(tb,encoding='utf-8')
    binary=V/(name+'.vvp')
    results={}
    for phase,cmd in [('compile',[IV,'-g2012','-s',top,'-o',binary,path]+files),('run',[IV.with_name('vvp.exe'),binary])]:
        proc=subprocess.run(list(map(str,cmd)),cwd=R,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=100,text=True,encoding='utf-8',errors='replace')
        (V/f'{name}_{phase}.log').write_text(proc.stdout,encoding='utf-8')
        assert proc.returncode==0,(name,phase,proc.returncode,proc.stdout[-4000:])
        results[phase]={'returncode':proc.returncode,'log':f'validation/latency_v12_preservation/{name}_{phase}.log'}
        if phase=='run':assert '_PROTECTION_PASS' in proc.stdout;print(proc.stdout.strip(),flush=True)
    return results

def main():
    start=time.time();V.mkdir(parents=True,exist_ok=True)
    current={p.relative_to(R).as_posix():sha(p) for p in (R/'user_source').rglob('*') if p.is_file()}
    baseline={p.relative_to(B).as_posix():sha(p) for p in (B/'user_source').rglob('*') if p.is_file()}
    allowed={'hdl_source/'+x for x in ['design_top_wrapper.v','video_in.v','video_out.v','fusion_hud.v','fusion_menu_rom.v','fusion_telemetry.v']}
    exact=[];relocated=[]
    for p in (B/'user_source').rglob('*'):
        if not p.is_file():continue
        rel=p.relative_to(B/'user_source').as_posix();q=R/'user_source'/rel
        assert q.is_file(),('Production source missing',rel)
        if sha(p)==sha(q):exact.append(rel)
        elif rel not in allowed:
            assert p.suffix=='.v' and norm(read(p))==norm(read(q)),('Protected source changed',rel)
            relocated.append(rel)
    for name in ['video_in.v','video_out.v']:
        assert norm(restored_video(name,read(H/name)))==norm(read(BH/name)),('Datapath changed',name)
    top=read(H/'design_top_wrapper.v')
    assert norm(restored_top(top))==norm(read(BH/'design_top_wrapper.v')),'Old top wiring changed'
    frozen_display_start='    wire [25:0] color_gains_hdmi;'
    assert norm(top[top.index(frozen_display_start):])==norm(read(BH/'design_top_wrapper.v')[read(BH/'design_top_wrapper.v').index(frozen_display_start):]),'Display block changed'
    # Monitor outputs terminate in an atomic per-frame HUD snapshot. None may
    # leave this observer region directly; only the frozen tuple reaches UI.
    a=top.index('    wire [31:0] latency_us;');b=top.index('    wire [15:0] xb,yb;',a)
    region=top[a:b];outside=top[:a]+top[b:]
    for wire in ['latency_us','latency_frame_id','latency_valid','latency_repeat','latency_skip']:
        assert not re.search(r'\b'+wire+r'\b',outside),('Monitor output escaped HUD snapshot',wire)
    assert set(re.findall(r'\b(\w+)\s*<=',region))=={'latency_hud_us','latency_hud_id','latency_hud_flags'},'Snapshot drives a non-HUD register'
    assert not re.search(r'\bassign\b',re.sub(r'//[^\n]*','',region)),'Observer region has an unexpected continuous driver'
    assert dict(re.findall(r'\.(O_\w+)\(([^)]+)\)',region))=={
        'O_latency_us':'latency_us','O_frame_id':'latency_frame_id',
        'O_valid':'latency_valid','O_repeat':'latency_repeat','O_skip':'latency_skip'},'Monitor has an unexpected output target'
    old_menu,old_font=read(BH/'fusion_menu_rom.v').split('module fusion_font_rom',1)
    new_menu,new_font=read(H/'fusion_menu_rom.v').split('module fusion_font_rom',1)
    assert old_font==new_font,'Font changed'
    om=parse_rom(old_menu,8192);nm=parse_rom(new_menu,8192)
    changes=[i for i,(a,b) in enumerate(zip(om,nm)) if a!=b]
    assert changes and all(13*256<=i<14*256 for i in changes),'A non-latency menu changed'
    for name in ['fusion_hud.v','fusion_menu_rom.v','fusion_telemetry.v']:
        (V/('reference_'+name)).write_text(namespace(read(BH/name)),encoding='utf-8')
    rows=[list(b'SW3 SAME FRAME DELAY  CAPTURE TO HDMI'),
      list(b'DELAY ')+[187,188,189,46,190,191]+list(b' MS   VALID ')+[171],
      list(b'SOURCE FRAME ')+[172,173,174,175]+list(b'  REPEAT ')+[176]+list(b'  SKIP ')+[177],
      list(b'FPGA INPUT TO HDMI  NOT MONITOR RESPONSE')]
    expected=[32]*256
    for row,values in enumerate(rows):expected[row*64:row*64+len(values)]=values
    (V/'expected_page13.hex').write_text(''.join(f'{v:02x}\n' for v in expected),encoding='ascii')
    font=parse_rom(old_font,1024,default=0)
    (V/'reference_font.hex').write_text(''.join(f'{v:02x}\n' for v in font),encoding='ascii')
    hudtb=HUD_TB.replace('__EXPECTED__',(V/'expected_page13.hex').as_posix()).replace('__FONT__',(V/'reference_font.hex').as_posix())
    tests={}
    tests['hud']=run_test('hud','preservation_hud_tb',hudtb,[H/'fusion_hud.v',H/'fusion_menu_rom.v',V/'reference_fusion_hud.v',V/'reference_fusion_menu_rom.v'])
    tests['telemetry']=run_test('telemetry','preservation_telemetry_tb',TELEM_TB,[H/'fusion_telemetry.v',V/'reference_fusion_telemetry.v'])
    (V/'reference_video_in.v').write_text(re.sub(r'\bvideo_in\b','reference_video_in',read(BH/'video_in.v')),encoding='utf-8')
    tests['source_alignment']=run_test('source_alignment','preservation_alignment_tb',ALIGN_TB,[H/'video_in.v',V/'reference_video_in.v'])
    a=top.index('    reg [31:0] latency_hud_us;');b=top.index('    frame_latency_monitor u_frame_latency(',a)
    block=top[a:b]
    wrapper='''module snapshot_actual(input S_hdmi_pixel_clk,S_hdmi_rst_n,S_hdmi_user,
input [31:0] latency_us,input [15:0] latency_frame_id,input latency_valid,latency_repeat,latency_skip,
output [31:0] O_us,output [15:0] O_id,output [2:0] O_flags);
'''+block+'''assign O_us=latency_hud_us;assign O_id=latency_hud_id;assign O_flags=latency_hud_flags;
endmodule
'''
    (V/'snapshot_actual.v').write_text(wrapper,encoding='utf-8')
    tests['snapshot']=run_test('snapshot','preservation_snapshot_tb',SNAPSHOT_TB,[V/'snapshot_actual.v',H/'fusion_telemetry.v'])
    for rel,h in current.items():assert sha(R/rel)==h,('DUT changed during verification',rel)
    for rel,h in baseline.items():assert sha(B/rel)==h,('Baseline changed during verification',rel)
    result={'pass':True,'exact_protected_source_count':len(exact),'rom_path_only_changes':relocated,
        'video_out_observer_only_after_stripping_new_ports':True,
        'video_in_original_fifo_reset_pointer_arbitration_after_explicit_alignment_restore':True,
        'old_top_connections_restored_after_removing_monitor_snapshot_ui_ports':True,
        'original_display_rgb_algorithm_chain_exact':True,'monitor_outputs_only_atomic_hud_snapshot':True,
        'input_transport_exception':{'default_camera_cycles':24,'data_width':128,'data_valid_delayed_together':True,
            'zero_parameter_restores_original_input_pins':True,'rgb_arithmetic_added':False,
            'fifo_reset_pointer_and_ddr_policy_changed':False,
            'pixel_timing_and_previously_truncated_frame_content_can_change':True,
            'scope':'Intentional timing change needed to retain the source prefix across existing FIFO SOF reset; not a whole-datapath or detector-input pixel equivalence claim.'},
        'menu_changes_only_panel13':True,'font_source_exact':True,'changed_menu_addresses':len(changes),
        'tests':tests,'source_sha256':current,'baseline_source_sha256':baseline,
        'verifier_sha256':sha(Path(__file__)),'seconds':round(time.time()-start,2),
        'scope':'Protected RGB/ISP/detection/alarm algorithms and old connections, with explicit 24-camera-cycle source data/valid transport exception. Real paired HUD/telemetry, bit-preserving delay, parameter-zero transport/policy and atomic per-frame HUD snapshot RTL tests. Source-alignment harness uses a pin-level FIFO stub; actual generated FIFO/DDR prefix and complete-frame tests are separate. No board observation, unchanged full-pipeline pixel stream, or unchanged detector input claimed.'}
    (V/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('V12_PRESERVATION_ALL_PASS',flush=True)

if __name__=='__main__':main()
