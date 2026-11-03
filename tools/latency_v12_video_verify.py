"""Exercise production packer/video/DDR interfaces with generated FIFO RTL.

The vendor generated soft FIFO models are compiled verbatim, including their
Gray pointer synchronizers, asynchronous reset with synchronous release, and
SHOW_AHEAD=0 RAM read latency. No production RTL is edited by this tool.
"""
from pathlib import Path
import hashlib,json,re,subprocess,sys,time

R=Path(__file__).resolve().parents[1]
H=R/'user_source/hdl_source'
IP=R/'user_source/ip_source'
V=R/'validation/latency_v12_video'
IV=Path(r'D:\anlu\iverilog\bin\iverilog.exe')
VVP=IV.with_name('vvp.exe')
FILES=[H/'isp/stylize_v5_96.v',H/'isp/style_guide_v8.v',H/'data_96bit_to_128bit.v',H/'video_in.v',H/'video_out.v',H/'mc_to_user_interface.v',
       H/'fusion_controls.v',H/'frame_latency_monitor.v',
       IP/'w128_d512_fifo/w128_d512_fifo.v',IP/'w128_d512_fifo/soft_fifo_al_4057d6b76aa6.v',
       IP/'w155_d512_fifo/w155_d512_fifo.v',IP/'w155_d512_fifo/soft_fifo_al_f58e8b3e1f3d.v']

TB=r'''`timescale 1ns/1ps
module latency_video_tb;
parameter integer LEAD=0;
parameter integer FULL=0;
parameter integer STYLE=0,ALIGN=24,SPARSE=0;
parameter integer LINES=720;
localparam W=1280,H=LINES,N=W*H*3/16;
reg sys=0,cam=0,ddr=0,hdmi=0;
always #10 sys=~sys;
always #5.208333 cam=~cam;
always #2.5 ddr=~ddr;
always #6.666667 hdmi=~hdmi;
reg rst=0;
reg raw_user=0,raw_valid=0;
reg [95:0] raw_data=0;
reg [95:0] pipe_data[0:63];
reg [63:0] pipe_valid=0,pipe_user=0;
reg [5:0] pipe_pointer=0;
wire[95:0] style_data;wire style_valid,style_user;
generate if(STYLE)begin
 stylize_v5_96 #(.IMG_WIDTH(W),.IMG_HEIGHT(H),.EXTERNAL_EDGE(0)) real_style(
 .I_clk(cam),.I_rst_n(rst),.I_mode(2'd0),.I_tlast(1'b0),.I_tuser(raw_user),.I_tdata(raw_data),
 .I_edge_data(96'd0),.I_tvalid(raw_valid),.I_tready(1'b1),.O_tlast(),.O_tuser(style_user),.O_tdata(style_data),.O_tvalid(style_valid),.O_tready());
end else begin
 assign style_data=pipe_data[pipe_pointer];assign style_valid=pipe_valid[63];assign style_user=pipe_user[63-LEAD];
end endgenerate
wire p_user,p_valid;wire[127:0] p_data;
data_96bit_to_128bit packer(.I_clk(cam),.I_rst_n(rst),
 .I_96b_frame_start(style_user),.I_96b_valid(style_valid),.I_96b_data(style_data),
 .O_128b_frame_start(p_user),.O_128b_valid(p_valid),.O_128b_data(p_data));
integer k;
always @(posedge cam)begin
 if(!rst)begin pipe_valid<=0;pipe_user<=0;pipe_pointer<=0;for(k=0;k<64;k=k+1)pipe_data[k]<=0;end
 else if(!STYLE)begin
  pipe_valid<={pipe_valid[62:0],raw_valid};pipe_user<={pipe_user[62:0],raw_user};
  pipe_data[pipe_pointer]<=raw_data;pipe_pointer<=pipe_pointer+1'b1;
 end
end
wire wr_en,wr_busy,rd_en,rd_busy,user_ready,ret_valid;
wire [24:0] wr_addr,rd_addr;
wire [127:0] wr_data,ret_data;
wire[1:0] rp;
video_in #(.INPUT_ALIGN_CYCLES(ALIGN)) vi(.I_rst_n(rst),.I_camera_clk(cam),.I_camera_frame_start(p_user),.I_camera_valid(p_valid),
 .I_camera_data(p_data),.I_mipi_rx_error(1'b0),.I_ddr_clk(ddr),.I_display_pause(1'b0),
 .I_video_out_rd_busy(FULL?rd_busy:1'b0),.O_video_in_wr_busy(wr_busy),.O_video_out_rp(rp),
 .O_ddr_user_wr_en(wr_en),.O_ddr_user_addr(wr_addr),.O_ddr_user_wr_data(wr_data),.I_ddr_user_ready(user_ready));
reg out_vs=0,out_de=0;
wire [23:0] output_rgb;
video_out vo(.I_rst_n(rst),.I_ddr_clk(ddr),.O_video_out_rd_busy(rd_busy),
 .I_video_in_wr_busy(wr_busy),.I_video_out_rp(rp),.O_ddr_user_rd_en(rd_en),.O_ddr_user_addr(rd_addr),
 .I_ddr_user_ready(user_ready),.I_ddr_user_rd_valid(ret_valid),.I_ddr_user_rd_data(ret_data),
 .I_dsi_clk(hdmi),.I_video_vsync(~out_vs),.I_video_rd_en(FULL?out_de:1'b0),.O_vdieo_data(output_rgb));
wire mc_en,mc_wren,mc_wend;wire[24:0]mc_addr;wire[2:0]mc_cmd;wire[127:0]mc_wdata;
wire[31:0] mc_mask;
reg mc_rdy=1,mc_wrdy=1;
mc_to_user_interface mc(.I_clk(ddr),.I_rst_n(rst),.I_ddr_user_wr_en(wr_en),
 .I_ddr_user_rd_en(FULL?rd_en:1'b0),.I_ddr_user_addr(wr_en?wr_addr:rd_addr),.I_ddr_user_wr_data(wr_data),
 .O_ddr_user_ready(user_ready),.O_ddr_user_rd_valid(ret_valid),.O_ddr_user_rd_data(ret_data),
 .O_mc_app_en(mc_en),.O_mc_app_addr(mc_addr),.O_mc_app_cmd(mc_cmd),.I_mc_app_rdy(mc_rdy),
 .O_mc_app_wdf_wren(mc_wren),.O_mc_app_wdf_data(mc_wdata),.O_mc_app_wdf_end(mc_wend),.O_mc_app_wdf_mask(mc_mask),
 .I_mc_app_wdf_rdy(mc_wrdy),.I_mc_app_rd_data(rdata),.I_mc_app_rd_data_end(rvalid),.I_mc_app_rd_data_valid(rvalid));
reg [127:0] ram0[0:N+1023],ram1[0:N+1023],ram2[0:N+1023],ram3[0:N+1023];
reg [127:0] response_data[0:63];reg[63:0]response_valid=0;
reg[127:0]rdata=0;reg rvalid=0;
integer cycle=0,sa,ix,j,response_pointer=0;
function integer addr_slot;input[24:0] a;begin addr_slot=a<7000000?0:a<14000000?1:a<21000000?2:3;end endfunction
function integer addr_index;input[24:0] a;begin
 case(addr_slot(a))0:addr_index=a/8;1:addr_index=(a-7000000)/8;2:addr_index=(a-14000000)/8;3:addr_index=(a-21000000)/8;endcase
end endfunction
always @(posedge ddr)begin
 cycle<=cycle+1;
 // Deterministic backpressure is behind the original ordered command FIFO.
 if(FULL)begin mc_rdy<=cycle%29!=7 && cycle%29!=8;mc_wrdy<=cycle%37!=11;end
 rvalid<=response_valid[response_pointer];rdata<=response_data[response_pointer];
 response_valid[response_pointer]<=0;
 response_pointer<=response_pointer==63?0:response_pointer+1;
 if(rst && mc_en)begin
  sa=addr_slot(mc_addr);ix=addr_index(mc_addr);
  if(ix<0 || ix>N+1023)$fatal(1,"DDR address outside image + allowed prefetch %d",ix);
  if(mc_cmd==0 && mc_wren)begin
   case(sa)0:ram0[ix]<=mc_wdata;1:ram1[ix]<=mc_wdata;2:ram2[ix]<=mc_wdata;3:ram3[ix]<=mc_wdata;endcase
  end else if(mc_cmd==1)begin
   response_valid[response_pointer]<=1;
   case(sa)0:response_data[response_pointer]<=ram0[ix];1:response_data[response_pointer]<=ram1[ix];2:response_data[response_pointer]<=ram2[ix];3:response_data[response_pointer]<=ram3[ix];endcase
  end else $fatal(1,"bad memory command");
 end
end
integer packed_words=0,wr_count[0:3],total_wr=0,claims=0;
integer full_hits=0,under_hits=0,read_sessions=0,read_requests=0;
integer mismatch=0,identity_mismatch=0,checked_pixels=0,first_errors=0;
integer claim_words[0:15],claim_slot[0:15],claim_frame;
reg[127:0]first_word[0:15];
reg [31:0] delay_us;wire[31:0]measured;wire[15:0]mid;wire mvalid,mrepeat,mskip;
reg de1=0,de2=0,vs1=0,vs2=0;
always @(posedge hdmi)begin de1<=out_de;de2<=de1;vs1<=out_vs;vs2<=vs1;end
wire input_full=vi.U_w128_d512_fifo.full_flag;
wire output_under=vo.S_fifo_rd_en && vo.S_fifo_emtpy;
frame_latency_monitor #(.WIDTH(W),.HEIGHT(H)) dut(.sys_clk(sys),.cam_clk(cam),.ddr_clk(ddr),.hdmi_clk(hdmi),.rst_n(rst),
 .raw_user(raw_user),.raw_valid(raw_valid),.raw_error(1'b0),.packed_user(p_user),.input_overflow(vi.O_observe_overflow),
 .write_start(vi.S_frame_start),.write_slot(vi.S_video_in_wp),.write_en(wr_en),.write_address(wr_addr),
 .read_start(FULL?vo.S_video_frame_start:1'b0),.read_slot(rp),.read_en(FULL?rd_en:1'b0),.read_address(rd_addr),
 .read_return(ret_valid),.read_fifo_reset(vo.S_fifo_rst),.raw_hdmi_vs(out_vs),.final_hdmi_vs(vs2),.final_hdmi_de(FULL?de2:1'b0),
 .output_underflow(output_under),.O_latency_us(measured),.O_frame_id(mid),.O_valid(mvalid),.O_repeat(mrepeat),.O_skip(mskip));
integer active_claim=-1;
realtime capture_ns[0:15],first_display_ns=0.0;
integer captures=0,timestamp_checks=0,expected_us;
always @(posedge cam)if(rst)begin
 if(raw_user && raw_valid)begin captures=captures+1;capture_ns[captures]=$realtime;end
 if(p_valid)packed_words=packed_words+1;
 if(p_valid && input_full)full_hits=full_hits+1;
end
always @(posedge ddr)if(rst)begin
 if(vi.S_frame_start)begin
  if(active_claim>=0)$display("WRITE_FRAME index=%0d slot=%0d words=%0d first=%h",active_claim,claim_slot[active_claim],claim_words[active_claim],first_word[active_claim]);
  active_claim=claims;claim_slot[claims]=vi.S_video_in_wp;claim_words[claims]=0;first_word[claims]=0;claims=claims+1;
 end
 if(wr_en)begin
  total_wr=total_wr+1;wr_count[addr_slot(wr_addr)]=wr_count[addr_slot(wr_addr)]+1;
  if(active_claim>=0)begin if(claim_words[active_claim]==0)first_word[active_claim]=wr_data;claim_words[active_claim]=claim_words[active_claim]+1;end
 end
 if(FULL && vo.S_video_frame_start)begin read_sessions=read_sessions+1;read_requests=0;end
 if(FULL && rd_en)read_requests=read_requests+1;
end
integer oh=0,ov=0,out_frame=0,display_index=0,expected_frame=0;
integer mvalid_frames=0,observed_updates=0;
reg old_valid=0;reg[15:0] old_mid=0;
always @(negedge hdmi)if(FULL==1 && rst)begin
 out_vs=ov>=725 && ov<730;out_de=ov<720 && oh<1280;
 if(oh==1649)begin oh=0;if(ov==749)begin ov=0;out_frame=out_frame+1;end else ov=ov+1;end else oh=oh+1;
end
reg rd_d1=0,rd_d2=0;integer output_pixel=0,stable_frame=-1;
reg [23:0] wanted;reg[3:0] seen_id;
always @(posedge hdmi)begin
 if(FULL && de2 && first_display_ns==0.0)first_display_ns=$realtime;
 if(output_under)under_hits=under_hits+1;
 rd_d1<=out_de;rd_d2<=rd_d1;
 #1;
 if(FULL && rst && (FULL==2 || out_frame>=3) && rd_d2)begin
  // Pixel identity encoded in high nibble; coordinate in low twenty bits.
  seen_id=output_rgb[23:20];
  if(output_pixel==0)begin stable_frame=seen_id;expected_frame=seen_id;end
  wanted={expected_frame[3:0],output_pixel[19:0]};
  checked_pixels=checked_pixels+1;
  if(output_rgb!==wanted)begin mismatch=mismatch+1;if(first_errors<8)begin $display("PIXEL_MISMATCH f=%0d p=%0d got=%h expected=%h",out_frame,output_pixel,output_rgb,wanted);first_errors=first_errors+1;end end
  if(seen_id!==expected_frame[3:0])identity_mismatch=identity_mismatch+1;
  if(output_pixel==W*H-1)output_pixel=0;else output_pixel=output_pixel+1;
 end
 if(FULL && mvalid && (!old_valid || mid!=old_mid))begin
  mvalid_frames=mvalid_frames+1;observed_updates=observed_updates+1;
  if(FULL==2)begin
   if(mid!=1 || first_display_ns==0.0)$fatal(1,"same-frame identity did not match completed source1");
   expected_us=(first_display_ns-capture_ns[mid])/1000.0;
   if(measured+2<expected_us || measured>expected_us+2)$fatal(1,"physical fixture timestamp mismatch got=%0d expected=%0d",measured,expected_us);
   timestamp_checks=timestamp_checks+1;
  end
  $display("MEASUREMENT id=%0d us=%0d repeat=%0d skip=%0d",mid,measured,mrepeat,mskip);
 end
 old_valid=mvalid;old_mid=mid;
end
integer frame,line,g,pidx,c,oy,ox;
reg[23:0] px0,px1,px2,px3;
initial begin
 for(c=0;c<4;c=c+1)wr_count[c]=0;
 for(c=0;c<16;c=c+1)begin claim_words[c]=0;claim_slot[c]=0;first_word[c]=0;end
 #1000;rst=1;
 if(FULL==2)begin
  // video_out resets its own asynchronous FIFO on a display VS event, not
  // the global reset. A warm-up scan boundary represents the continuously
  // running VTC before a usable camera frame, without forcing FIFO internals.
  repeat(16)@(negedge hdmi);out_vs=1;
  repeat(8)@(negedge hdmi);out_vs=0;
  repeat(1000)@(negedge hdmi);
 end
 for(frame=1;frame<=(SPARSE?1:FULL==2?3:FULL?7:2);frame=frame+1)begin
  for(line=0;line<H;line=line+1)begin
   for(g=0;g<320;g=g+1)begin
    @(negedge cam);raw_valid=1;raw_user=line==0 && g==0;
    pidx=line*1280+g*4;
    px0={frame[3:0],pidx[19:0]};pidx=pidx+1;px1={frame[3:0],pidx[19:0]};
    pidx=pidx+1;px2={frame[3:0],pidx[19:0]};pidx=pidx+1;px3={frame[3:0],pidx[19:0]};
    raw_data={px0,px1,px2,px3};
   end
   @(negedge cam);raw_valid=0;raw_user=0;raw_data=0;
   // 96MHz source line period matches a 75MHz/1650 HDMI line in FULL.
   repeat(FULL==1?1791:91)@(negedge cam);
  end
  if(FULL==1)repeat(63360)@(negedge cam);
  else repeat(512)@(negedge cam);
 end
 if(SPARSE)begin
  // Two empty packed frame events exercise dropped frames while rotating the
  // existing four-slot pointer back to the complete source1 buffer.
  repeat(600)@(negedge cam);
  @(negedge cam);raw_user=1;@(negedge cam);raw_user=0;
  repeat(600)@(negedge cam);
  @(negedge cam);raw_user=1;@(negedge cam);raw_user=0;
 end
 if(FULL==2)begin
  repeat(3000)@(negedge cam);
  // Three complete source frames select slot0 (source ID1). Start exactly one
  // 720p scan, rather than spending several warm-up display frames on empties.
  @(negedge hdmi);out_vs=1;out_de=0;
  repeat(8)@(negedge hdmi);
  @(negedge hdmi);out_vs=0;
  repeat(33000)@(negedge hdmi);
  for(oy=0;oy<H;oy=oy+1)begin
   for(ox=0;ox<1280;ox=ox+1)begin @(negedge hdmi);out_de=1;end
   @(negedge hdmi);out_de=0;repeat(369)@(negedge hdmi);
  end
  repeat(20000)@(negedge hdmi);
  @(negedge hdmi);out_vs=1;repeat(8)@(negedge hdmi);
  @(negedge hdmi);out_vs=0;repeat(40000)@(negedge hdmi);
 end else repeat(FULL?120000:5000)@(negedge cam);
 if(active_claim>=0)$display("WRITE_FRAME index=%0d slot=%0d words=%0d first=%h",active_claim,claim_slot[active_claim],claim_words[active_claim],first_word[active_claim]);
 $display("RESULT lead=%0d full=%0d claims=%0d packed=%0d writes=%0d source_full=%0d output_under=%0d pixels=%0d mismatches=%0d identities=%0d valid_measurements=%0d timestamp_checks=%0d",LEAD,FULL,claims,packed_words,total_wr,full_hits,under_hits,checked_pixels,mismatch,identity_mismatch,mvalid_frames,timestamp_checks);
 if(claims!=(SPARSE?3:FULL==2?3:FULL?7:2))$fatal(1,"unexpected camera claims");
 if(packed_words!=(SPARSE?1:FULL==2?3:FULL?7:2)*N)$fatal(1,"packer count differs");
 if(!FULL && LEAD>=24)begin
  for(c=0;c<2;c=c+1)if(claim_words[c]!=N)$fatal(1,"guarded full write count incomplete");
 end
 if(!FULL && STYLE)begin
  for(c=0;c<2;c=c+1)begin
   if(ALIGN>0 && claim_words[c]!=N)$fatal(1,"production aligned full write incomplete");
   if(ALIGN==0 && claim_words[c]!=N-240)$fatal(1,"legacy drop diagnostic changed; inspect production timing");
  end
 end
 if(FULL && LEAD>=24)begin
  if(checked_pixels<(FULL==2?1:3)*W*H)$fatal(1,"not enough full frame pixels");
  if(identity_mismatch!=0 || mismatch!=0)$fatal(1,"production pixel mismatch");
  if(mvalid_frames<(FULL==2?1:2))$fatal(1,"monitor did not validate full production frames");
 end
 if(FULL && STYLE)begin
  if(claim_words[0]!=N || full_hits!=0 || under_hits!=0)$fatal(1,"production full-frame FIFO integrity failure");
  if(checked_pixels<W*H || mismatch!=0 || identity_mismatch!=0)$fatal(1,"production full-frame pixel identity failure");
  if(mvalid_frames<1 || timestamp_checks<1)$fatal(1,"production same-frame timestamp not verified");
 end
 $display("VIDEO_FLOW_COMPLETED");$finish;
end
initial begin #(FULL?180000000:20000000);$fatal(1,"testbench watchdog");end
endmodule
'''

def run_case(lead,full,style=0,align=24,sparse=0,lines=720):
    name=f'lead{lead}_style{style}_align{align}_sparse{sparse}_h{lines}_'+('full' if full else 'write')
    dest=V/name;dest.mkdir(parents=True,exist_ok=True)
    tb=dest/'tb.sv';tb.write_text(TB,encoding='utf-8',newline='\n')
    before_hash={str(f.relative_to(R)):hashlib.sha256(f.read_bytes()).hexdigest() for f in FILES}
    out=dest/'sim.vvp'
    c=subprocess.run([str(IV),'-g2012','-s','latency_video_tb',f'-Platency_video_tb.LEAD={lead}',f'-Platency_video_tb.FULL={full}',f'-Platency_video_tb.STYLE={style}',f'-Platency_video_tb.ALIGN={align}',f'-Platency_video_tb.SPARSE={sparse}',f'-Platency_video_tb.LINES={lines}','-o',str(out),str(tb),*[str(f) for f in FILES]],capture_output=True,text=True,timeout=45)
    (dest/'compile.log').write_text(c.stdout+c.stderr,encoding='utf-8')
    if c.returncode:raise RuntimeError(f'Compile failed {name}: '+c.stderr[-2000:])
    start=time.monotonic()
    p=subprocess.run([str(VVP),str(out)],capture_output=True,text=True,timeout=480 if full else 240)
    (dest/'run.log').write_text(p.stdout+p.stderr,encoding='utf-8')
    m=re.search(r'RESULT (.*)',p.stdout)
    result={'name':name,'scope':'production style/packer/video/FIFO/MC path' if style else 'controlled SOF lead diagnosis, not production style acceptance','parameters':{'lead':lead,'full':full,'style':style,'alignment':align,'sparse':sparse,'width':1280,'height':lines},'returncode':p.returncode,'seconds':round(time.monotonic()-start,3),'completed':'VIDEO_FLOW_COMPLETED' in p.stdout,'metrics':dict(re.findall(r'(\w+)=(\d+)',m[1])) if m else {},'frame_writes':re.findall(r'WRITE_FRAME (.*)',p.stdout),'compiled_source_sha256':before_hash,'sources_still_current':before_hash=={str(f.relative_to(R)):hashlib.sha256(f.read_bytes()).hexdigest() for f in FILES}}
    (dest/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result),flush=True)
    return result

STYLE_GAP_TB=r'''`timescale 1ns/1ps
module style_gap_tb;
parameter integer ALIGN=24;
reg cam=0,ddr=0,rst=0;always #5.208333 cam=~cam;always #2.5 ddr=~ddr;
reg valid=0,user=0,last=0;reg[95:0] data=0;
wire sv,su,sl,pv,pu;wire[95:0] sd;wire[127:0]pd;
stylize_v5_96 #(.IMG_WIDTH(1280),.IMG_HEIGHT(720),.EXTERNAL_EDGE(0)) style(
 .I_clk(cam),.I_rst_n(rst),.I_mode(2'd0),.I_tlast(last),.I_tuser(user),.I_tdata(data),
 .I_edge_data(96'd0),.I_tvalid(valid),.I_tready(1'b1),.O_tlast(sl),.O_tuser(su),.O_tdata(sd),.O_tvalid(sv),.O_tready());
data_96bit_to_128bit pack(.I_clk(cam),.I_rst_n(rst),.I_96b_frame_start(su),.I_96b_valid(sv),.I_96b_data(sd),
 .O_128b_frame_start(pu),.O_128b_valid(pv),.O_128b_data(pd));
wire we,wb;wire[24:0]wa;wire[127:0]wd;wire[1:0]rp;
video_in #(.INPUT_ALIGN_CYCLES(ALIGN)) vi(.I_rst_n(rst),.I_camera_clk(cam),.I_camera_frame_start(pu),.I_camera_valid(pv),.I_camera_data(pd),
 .I_mipi_rx_error(1'b0),.I_ddr_clk(ddr),.I_display_pause(1'b0),.I_video_out_rd_busy(1'b0),
 .O_video_in_wr_busy(wb),.O_video_out_rp(rp),.O_ddr_user_wr_en(we),.O_ddr_user_addr(wa),.O_ddr_user_wr_data(wd),.I_ddr_user_ready(1'b1));
integer tick=0,style_user=-1,style_valid=-1,pack_user=-1,pack_valid=-1;
integer packed_count=0,fifo_accepted=0,reset_lost=0,writes=0,g;
always @(posedge cam)begin
 if(rst)begin
  if(pv)packed_count=packed_count+1;
  if(vi.aligned_camera_valid)begin
   if(vi.U_w128_d512_fifo.soft_fifo_al_4057d6b76aa6_Inst.wr_rst)reset_lost=reset_lost+1;
   else if(!vi.U_w128_d512_fifo.full_flag)fifo_accepted=fifo_accepted+1;
  end
 end
 #1;tick=tick+1;
 if(rst)begin
  if(su && style_user<0)style_user=tick;if(sv && style_valid<0)style_valid=tick;
  if(pu && pack_user<0)pack_user=tick;if(pv && pack_valid<0)pack_valid=tick;
 end
end
always @(posedge ddr)if(rst && we)writes=writes+1;
initial begin
 #1000;rst=1;repeat(8)@(negedge cam);
 for(g=0;g<320;g=g+1)begin @(negedge cam);valid=1;user=g==0;last=g==319;data={4{24'h123456}};end
 @(negedge cam);valid=0;user=0;last=0;
 repeat(2000)@(negedge cam);
 $display("STYLE_GAP style_user=%0d style_valid=%0d pack_user=%0d pack_valid=%0d packed=%0d accepted=%0d reset_lost=%0d writes=%0d",style_user,style_valid,pack_user,pack_valid,packed_count,fifo_accepted,reset_lost,writes);
 if(packed_count!=240)$fatal(1,"production style/packer one-line count differs");
 $display("STYLE_GAP_COMPLETED");$finish;
end
endmodule
'''

def run_style_gap(align):
    dest=V/f'production_style_gap_align{align}';dest.mkdir(parents=True,exist_ok=True)
    tb=dest/'tb.sv';tb.write_text(STYLE_GAP_TB,encoding='utf-8',newline='\n')
    files=[H/'isp/stylize_v5_96.v',H/'isp/style_guide_v8.v',H/'data_96bit_to_128bit.v',H/'video_in.v',
           IP/'w128_d512_fifo/w128_d512_fifo.v',IP/'w128_d512_fifo/soft_fifo_al_4057d6b76aa6.v']
    source_hash={str(f.relative_to(R)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    out=dest/'sim.vvp';c=subprocess.run([str(IV),'-g2012','-s','style_gap_tb',f'-Pstyle_gap_tb.ALIGN={align}','-o',str(out),str(tb),*[str(f) for f in files]],capture_output=True,text=True,timeout=45)
    (dest/'compile.log').write_text(c.stdout+c.stderr,encoding='utf-8')
    if c.returncode:raise RuntimeError(c.stderr[-2000:])
    p=subprocess.run([str(VVP),str(out)],capture_output=True,text=True,timeout=60)
    (dest/'run.log').write_text(p.stdout+p.stderr,encoding='utf-8')
    m=re.search(r'STYLE_GAP (.*)',p.stdout)
    result={'scope':'Exact production mode0 style -> packer -> video_in generated FIFO, one complete 1280-pixel line','input_alignment_cycles':align,'returncode':p.returncode,'metrics':dict(re.findall(r'(\w+)=(-?\d+)',m[1])) if m else {},'completed':'STYLE_GAP_COMPLETED' in p.stdout,'source_sha256':source_hash}
    (dest/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)
    return result

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    V.mkdir(parents=True,exist_ok=True)
    if '--style-gap' in sys.argv:
        run_style_gap(0);run_style_gap(24);raise SystemExit(0)
    cases=[(0,2,1,24,1,8)] if '--production-fast' in sys.argv else [(0,2,1,24,1)] if '--production-full' in sys.argv else [(0,0,1,0),(0,0,1,24)] if '--production-write' in sys.argv else [(24,2)] if '--single-full' in sys.argv else [(0,0),(24,0)] if '--write-only' in sys.argv else [(0,0),(24,0),(24,1)]
    results=[run_case(*c) for c in cases]
    report={'scope':'Production packer/video/FIFO/ordered-command RTL with behavioral DDR memory and latency; not physical DDR or board verification','source_sha256':{str(f.relative_to(R)):hashlib.sha256(f.read_bytes()).hexdigest() for f in FILES},'results':results}
    (V/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    if any(x['returncode'] or not x['completed'] or not x['sources_still_current'] for x in results):raise SystemExit(1)
