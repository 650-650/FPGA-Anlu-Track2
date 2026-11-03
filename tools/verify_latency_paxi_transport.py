"""Native video/FIFO/observer plus actual DDR wrapper and PAXI handshake RAM.

Only ddr2/physical memory is modeled. Valid samples must match every actual
output pixel's source/coordinate and independently recorded input/output times.
"""
from pathlib import Path
import argparse,importlib.util,subprocess,json,hashlib,re,time
R=Path(__file__).resolve().parents[1];H=R/'user_source/hdl_source'
OLD=R.parent/'07_stylize_flame_fusion_v14_latency_provenance'
parser=argparse.ArgumentParser();parser.add_argument('--lines',type=int,default=8)
parser.add_argument('--fault-vs-return',action='store_true');parser.add_argument('--compile-only',action='store_true')
parser.add_argument('--strong-backpressure',action='store_true')
args=parser.parse_args()
verifier_hash_at_start=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
assert args.lines in (8,720)
name=f"paxi_{args.lines}p"+('_late_return' if args.fault_vs_return else '')+('_strong_stall' if args.strong_backpressure else '')
V=R/'validation'/name;V.mkdir(parents=True,exist_ok=True)
base=OLD/'validation/latency_720p_transport/tb.sv'
t=base.read_text(encoding='utf-8')
t=t.replace(".I_mode(2'd0),", ".I_mode(2'd0),.I_level(3'd2),")
t=t.replace('parameter integer LINES=720;',f'parameter integer LINES={args.lines};\nparameter integer FAULT_VS_RETURN={int(args.fault_vs_return)},STRONG_STALL={int(args.strong_backpressure)};')
t=t.replace('reg mc_rdy=1,mc_wrdy=1;','wire mc_rdy,mc_wrdy;')
a=t.index('reg [127:0] ram0[');b=t.index('integer packed_words=',a)
t=t[:a]+'''wire[127:0]rdata;wire rvalid,rlast;
ph1p35_324_ddr_wrapper actual_ddr_wrapper(
 .I_sys_clk(ddr),.I_sys_rst_n(rst),.O_ddr_clk(),.O_init_calib_complete(),
 .I_mc_app_addr(mc_addr),.I_mc_app_cmd(mc_cmd),.I_mc_app_en(mc_en),
 .I_mc_app_wdf_data(mc_wdata),.I_mc_app_wdf_end(mc_wend),.I_mc_app_wdf_mask(mc_mask[15:0]),.I_mc_app_wdf_wren(mc_wren),
 .O_mc_app_rd_data(rdata),.O_mc_app_rd_data_end(rlast),.O_mc_app_rd_data_valid(rvalid),.O_mc_app_rdy(mc_rdy),.O_mc_app_wdf_rdy(mc_wrdy));
function integer addr_slot;input[24:0] a;begin addr_slot=a<7000000?0:a<14000000?1:a<21000000?2:3;end endfunction
'''+t[b:]
t=t.replace('.I_mc_app_rd_data_end(rvalid)', '.I_mc_app_rd_data_end(rlast)')
t=t.replace('.read_fifo_reset(vo.S_fifo_rst)', '.read_fifo_reset(vo.O_observe_fifo_reset)')
t=t.replace('claim_words[c]!=172800','claim_words[c]!=N')
t=t.replace('origin_by_sequence[0:63]','origin_by_sequence[0:511]').replace('final_start_ns[0:63]','final_start_ns[0:511]')
if args.lines==8:
    t=t.replace('repeat(280000)@(negedge cam);','repeat(63360)@(negedge cam);')
    t=t.replace('repeat(3000000)@(negedge cam);','repeat(300000)@(negedge cam);')
    t=t.replace('#250000000;', '#30000000;')
t=t.replace('if(mvalid_frames<5 || under_hits!=0)', 'if(mvalid_frames<5 || (!FAULT_VS_RETURN && under_hits!=0))')
t=t.replace('seq=dut.pending_sequence;', '''seq=dut.pending_sequence;
   verified_valid[seq]=1;
   if(seq==actual_ddr_wrapper.u_ddr2.fault_old_sequence || seq==actual_ddr_wrapper.u_ddr2.fault_new_sequence)
    $fatal(1,"late/reset response generation was incorrectly declared VALID seq=%0d",seq);
   if(verified_pixel_count[seq]!=W*H || verified_pixel_errors[seq]!=0)
    $fatal(1,"VALID frame pixel mismatch seq=%0d count=%0d errors=%0d",seq,verified_pixel_count[seq],verified_pixel_errors[seq]);
   $display("PIXEL_SCOREBOARD_PASS seq=%0d pixels=%0d",seq,verified_pixel_count[seq]);''')
pixel_oracle=r'''
integer verified_pixel_count[0:511],verified_pixel_errors[0:511];
reg verified_valid[0:511];
integer verify_init,verify_index=0,verify_seq=0;
integer output_fifo_overflows=0,max_outstanding=0;
integer session_fifo_overflows=0,session_reset_returns=0;
always @(posedge ddr)if(rst)begin
 if(ret_valid && vo.U_w128_d512_fifo.full_flag)begin
  output_fifo_overflows=output_fifo_overflows+1;
  session_fifo_overflows=session_fifo_overflows+1;
  if(output_fifo_overflows<9)$display("OUTPUT_FIFO_OVERFLOW readseq=%0d fifo_words=%0d outstanding=%0d",dut.read_sequence,vo.S_fifo_wr_num,dut.outstanding);
 end
 if(dut.outstanding>max_outstanding)max_outstanding=dut.outstanding;
 if(ret_valid && vo.S_fifo_rst)session_reset_returns=session_reset_returns+1;
 if(vo.S_video_frame_start)begin
  $display("PAXI_READ_SNAPSHOT seq=%0d read_en=%0d return=%0d outstanding=%0d words=%0d bad=%0d fifo_overflows=%0d reset_returns=%0d",dut.read_sequence,rd_en,ret_valid,dut.outstanding,dut.read_words,dut.session_bad,session_fifo_overflows,session_reset_returns);
  session_fifo_overflows=0;session_reset_returns=0;
 end
end
reg verify_pending=0,verify_vs=0;
reg [3:0] verify_id;
reg [23:0] verify_wanted;
always @(posedge hdmi)if(rst && dut.pending && dut.hv_sequence==dut.pending_sequence && !dut.completing_frame && !dut.incomplete_boundary)begin
 #1;
 if(!mvalid)$display("PAXI_REJECTED seq=%0d id=%0d status=%02h reason=%04h",dut.pending_sequence,mid,dut.O_status,dut.O_debug_reason);
end
initial for(verify_init=0;verify_init<512;verify_init=verify_init+1)begin
 verified_pixel_count[verify_init]=0;verified_pixel_errors[verify_init]=0;
 verified_valid[verify_init]=0;
end
always @(posedge hdmi)begin
 if(rst && verify_vs && !out_vs)verify_pending=1;
 verify_vs=out_vs;
 #1;
 if(rst && rd_d2)begin
  if(verify_pending)begin verify_seq=dut.hdmi_sequence;verify_index=0;verify_id=output_rgb[23:20];verify_pending=0;end
  if(verify_seq!=0 && verify_index<W*H)begin
   verify_wanted={verify_id,verify_index[19:0]};
   verified_pixel_count[verify_seq]=verified_pixel_count[verify_seq]+1;
   if(output_rgb!==verify_wanted)begin
    verified_pixel_errors[verify_seq]=verified_pixel_errors[verify_seq]+1;
    if(verified_pixel_errors[verify_seq]<5)$display("PAXI_PIXEL_ERROR seq=%0d pixel=%0d got=%h wanted=%h fifo_overflows=%0d max_outstanding=%0d",verify_seq,verify_index,output_rgb,verify_wanted,output_fifo_overflows,max_outstanding);
   end
   verify_index=verify_index+1;
  end
 end
end
'''
summary=r'''
bad_pixel_frames=0;
for(verify_init=1;verify_init<512;verify_init=verify_init+1)begin
 if(verified_pixel_count[verify_init]!=0 && verified_pixel_errors[verify_init]!=0)begin
  bad_pixel_frames=bad_pixel_frames+1;
  if(verified_valid[verify_init])$fatal(1,"bad pixel frame was marked VALID seq=%0d",verify_init);
 end
end
if(!STRONG_STALL && !FAULT_VS_RETURN && output_fifo_overflows!=0)$fatal(1,"normal transport overflowed output FIFO");
if(STRONG_STALL && (output_fifo_overflows==0 || bad_pixel_frames==0))$fatal(1,"strong-stall overflow fixture was not exercised");
$display("PAXI_PIXEL_SUMMARY valid_frames=%0d bad_pixel_frames_rejected=%0d output_fifo_overflows=%0d",checked_valid,bad_pixel_frames,output_fifo_overflows);
if(actual_ddr_wrapper.u_ddr2.split_aw_first==0 || actual_ddr_wrapper.u_ddr2.split_w_first==0 || actual_ddr_wrapper.u_ddr2.ready_mismatch==0)
 $fatal(1,"PAXI independent channel conditions were not exercised");
if(FAULT_VS_RETURN && (!actual_ddr_wrapper.u_ddr2.fault_injected || actual_ddr_wrapper.u_ddr2.returns_during_fifo_reset==0))
 $fatal(1,"late-return/FIFO-reset negative fixture was not exercised");
$display("PAXI_PROTOCOL_COUNTS AW=%0d W=%0d commits=%0d AR=%0d R=%0d aw_first=%0d w_first=%0d blocked_AR_with_AWready=%0d returns_in_reset=%0d",actual_ddr_wrapper.u_ddr2.aw_count,actual_ddr_wrapper.u_ddr2.w_count,actual_ddr_wrapper.u_ddr2.write_count,actual_ddr_wrapper.u_ddr2.ar_count,actual_ddr_wrapper.u_ddr2.return_count,actual_ddr_wrapper.u_ddr2.split_aw_first,actual_ddr_wrapper.u_ddr2.split_w_first,actual_ddr_wrapper.u_ddr2.ready_mismatch,actual_ddr_wrapper.u_ddr2.returns_during_fifo_reset);
'''
t=t.replace('$display("FULL720P_TRANSPORT_PASS',summary+'\n $display("PAXI_TRANSPORT_PASS')
t=t.replace('endmodule',pixel_oracle+'\nendmodule')
t=t.replace('integer verified_pixel_count[0:511]', 'integer bad_pixel_frames=0;\ninteger verified_pixel_count[0:511]')
tb=V/'tb.sv';tb.write_text(t,encoding='utf-8')
spec=importlib.util.spec_from_file_location('fixture',R/'tools/latency_v12_video_verify.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
files=[*m.FILES,H/'vtc/uivtc.v',H/'ph1p35_ddr/ph1p35_324_ddr_wrapper.v',R/'tools/ddr2_video_protocol_stub.sv']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
sources={p.relative_to(R).as_posix():sha(p) for p in files}
cmd=[str(m.IV),'-g2012',f'-DPAXI_VIDEO_LINES={args.lines}','-s','latency_video_tb','-Platency_video_tb.FULL=1','-Platency_video_tb.STYLE=0','-Platency_video_tb.LEAD=55','-Platency_video_tb.ALIGN=0',f'-Platency_video_tb.LINES={args.lines}','-o',str(V/'sim.vvp'),str(tb),*map(str,files)]
c=subprocess.run(cmd,capture_output=True,text=True);(V/'compile.log').write_text(c.stdout+c.stderr,encoding='utf-8')
assert c.returncode==0,c.stderr
(V/'started.json').write_text(json.dumps({'case':name,'source_sha256':sources,'verifier_sha256':verifier_hash_at_start,'testbench_sha256':sha(tb),'base_fixture_sha256':sha(base),'compile_command':cmd},indent=2),encoding='utf-8')
if args.compile_only:print('PAXI_TRANSPORT_COMPILED',name,flush=True);raise SystemExit(0)
print(f'PAXI_TRANSPORT_RUNNING case={name} log={V / "run.log"}',flush=True)
start=time.monotonic()
with (V/'run.log').open('w',encoding='utf-8') as f:
    f.write(f'RUNNING case={name} production_mc_sha256={sources["user_source/hdl_source/mc_to_user_interface.v"]} wrapper_sha256={sources["user_source/hdl_source/ph1p35_ddr/ph1p35_324_ddr_wrapper.v"]}\n');f.flush()
    p=subprocess.run([str(m.VVP),'-i',str(V/'sim.vvp')],stdout=f,stderr=subprocess.STDOUT,text=True)
log=(V/'run.log').read_text(encoding='utf-8');print(log[-7000:],flush=True)
ok=p.returncode==0 and 'PAXI_TRANSPORT_PASS' in log
unchanged=sources=={q.relative_to(R).as_posix():sha(q) for q in files}
result={'passed':ok,'returncode':p.returncode,'sources_still_current':unchanged,'seconds_host_clock_may_jump':time.monotonic()-start,
 'scope':__doc__,'height':args.lines,'width':1280,'source_frames':9,'fault_vs_return':args.fault_vs_return,'strong_backpressure':args.strong_backpressure,
 'pixel_verified_valid_frames':len(re.findall('PIXEL_SCOREBOARD_PASS',log)),'event_time_verified_frames':len(re.findall('EXTERNAL_ORACLE_PASS',log)),
 'summary':[x for x in log.splitlines() if 'PASS' in x or 'PAXI_' in x or 'VTC_RESULT' in x],
 'source_sha256':sources,'verifier_sha256':verifier_hash_at_start,'verifier_still_current':verifier_hash_at_start==sha(Path(__file__)),'testbench_sha256':sha(tb),'base_fixture':str(base),'base_fixture_sha256':sha(base),
 'compile_command':cmd,'clocks_ns':{'sys':20,'cam':16.668,'ddr':15,'hdmi':13.333},
 'limitations':['Encrypted controller and physical DDR PHY/RAM are modeled.','ISP timing is a controlled pipeline with production-observed SOF lead.','This is not physical board acceptance.']}
(V/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');assert ok
if not unchanged:print('SOURCE_CHANGED_DURING_RUN inspect report hashes before acceptance',flush=True)
