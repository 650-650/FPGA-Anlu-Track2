"""Full 720p native DDR transport; pixel-encoded source ID and event-time oracle."""
from pathlib import Path
import importlib.util,subprocess,json,hashlib,re
R=Path(__file__).resolve().parents[1];V=R/'validation/latency_720p_transport';V.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('fixture',R/'tools/latency_v12_video_verify.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
t=(R/'validation/latency_startup/native_vtc_lead55_align0/tb.sv').read_text(encoding='utf-8')
for a,b in {'always #5.208333 cam=~cam;':'always #8.334 cam=~cam;','always #2.5 ddr=~ddr;':'always #7.5 ddr=~ddr;','always #6.666667 hdmi=~hdmi;':'always #6.6665 hdmi=~hdmi;'}.items():assert a in t;t=t.replace(a,b)
# Preserve the native packer/FIFOs/video arbiters/ordered command path. Make
# producer rate 60fps: each 1000-camera-clock row, 1000 rows per source frame.
t=t.replace('integer frame,line,g,c;','integer frame,line,g,c,p;')
t=t.replace("raw_data={4{24'h123456}};", "for(p=0;p<4;p=p+1)raw_data[95-24*p-:24]={frame[3:0],20'(line*W+g*4+p)};")
t=t.replace('repeat(1791)@(negedge cam);','repeat(679)@(negedge cam);')
t=t.replace('repeat(63360)@(negedge cam);','repeat(280000)@(negedge cam);')
t=t.replace('repeat(300000)@(negedge cam);','repeat(3000000)@(negedge cam);')
t=t.replace('claim_words[c]!=1920','claim_words[c]!=172800')
t=t.replace(' || mid!=7','')
t=t.replace('#20000000;', '#250000000;')
# The original reduced-height fixture never enabled its old pixel checker.
# This oracle explicitly observes encoded real FIFO pixels and samples the
# same final DE event as the production monitor. No DUT state is forced.
oracle=r'''
integer ext_pixel=0,checked_valid=0,checked_hud=0;
integer origin_by_sequence[0:63];
realtime final_start_ns[0:63];
reg raw_vs_prev=0,final_vs_prev=0,raw_first_pending=0,final_first_pending=0;
integer seq,oracle_age;
always @(posedge hdmi)begin
 // Native VTC emits DE while its internal reset holds h/v counters at zero.
 // Start an independent frame at an observed VS edge; counting pixels from
 // global reset includes those startup cycles and drifts by a partial row.
 if(rst && raw_vs_prev && !out_vs)raw_first_pending=1;
 if(rst && final_vs_prev && !vs2)final_first_pending=1;
 raw_vs_prev=out_vs;final_vs_prev=vs2;
 if(rst && de2 && final_first_pending)begin
  final_start_ns[dut.hdmi_sequence]=$realtime;final_first_pending=0;
 end
 #1;
 if(rst && rd_d2)begin
  if(raw_first_pending)begin
   origin_by_sequence[dut.hdmi_sequence]=output_rgb[23:20];
   raw_first_pending=0;
   $display("PIXEL_ORIGIN seq=%0d id=%0h first_rgb=%h",dut.hdmi_sequence,output_rgb[23:20],output_rgb);
  end
 end
 if(rst && mvalid && !old_valid)begin
  seq=dut.pending_sequence;
  if(mid!==origin_by_sequence[seq])$fatal(1,"Valid frame ID differs from actual DDR pixel origin seq=%0d id=%0d rgb_id=%0d",seq,mid,origin_by_sequence[seq]);
  oracle_age=(final_start_ns[seq]-capture_ns[mid])/1000.0;
  if(measured+2<oracle_age || measured>oracle_age+2)$fatal(1,"Real event time mismatch got=%0d expected=%0d",measured,oracle_age);
  checked_valid=checked_valid+1;
  $display("EXTERNAL_ORACLE_PASS seq=%0d id=%0d us=%0d event_us=%0d",seq,mid,measured,oracle_age);
 end
 if(rst && actual_vtc.O_vtc_user && mvalid)begin
  if(dut.O_status!==0)$fatal(1,"Valid HUD snapshot status nonzero");
  checked_hud=checked_hud+1;
 end
end
'''
# Existing monitor block updates old_valid after #1; observe transition at
# pre-NBA sampling via a dedicated flag instead of depending on block order.
oracle=oracle.replace('integer ext_pixel=0,','reg oracle_old_valid=0;\ninteger ext_pixel=0,')
oracle=oracle.replace('&& !old_valid','&& !oracle_old_valid')
oracle=oracle.replace('\nend\n','\n oracle_old_valid=mvalid;\nend\n')
t=t.replace('endmodule',oracle+'\nendmodule')
t=t.replace('$display("ACTUAL_VTC_PASS");$finish;', 'if(checked_valid<4 || checked_hud<4)$fatal(1,"Too few externally verified full frames");\n $display("FULL720P_TRANSPORT_PASS source_frames=9 measured=%0d hud=%0d",checked_valid,checked_hud);$finish;')
tb=V/'tb.sv';tb.write_text(t,encoding='utf-8');files=[*m.FILES,R/'user_source/hdl_source/vtc/uivtc.v']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();sources={p.relative_to(R).as_posix():sha(p) for p in files}
cmd=[str(m.IV),'-g2012','-s','latency_video_tb','-Platency_video_tb.FULL=1','-Platency_video_tb.STYLE=0','-Platency_video_tb.LEAD=55','-Platency_video_tb.ALIGN=0','-Platency_video_tb.LINES=720','-o',str(V/'sim.vvp'),str(tb),*map(str,files)]
p=subprocess.run(cmd,capture_output=True,text=True);(V/'compile.log').write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0,p.stderr
print('RUNNING_FULL720P_NATIVE_ORACLE',flush=True)
with (V/'run.log').open('w',encoding='utf-8') as f:p=subprocess.run([str(m.VVP),'-i',str(V/'sim.vvp')],stdout=f,stderr=subprocess.STDOUT,text=True)
log=(V/'run.log').read_text(encoding='utf-8');print(log[-9000:],flush=True)
ok=p.returncode==0 and 'FULL720P_TRANSPORT_PASS' in log
assert sources=={q.relative_to(R).as_posix():sha(q) for q in files}
result={'pass':ok,'width':1280,'height':720,'source_frames':9,'measured_frames':len(re.findall('EXTERNAL_ORACLE_PASS',log)),
 'source_sha256':sources,'testbench_sha256':sha(tb),'verifier_sha256':sha(Path(__file__)),'source_unchanged':True,
 'clocks_ns':{'sys':20,'cam':16.668,'ddr':15,'hdmi':13.333},'scope':__doc__+' RAM and controller response are ordered behavioral models. ISP transport latency modeled as a controlled 64-clock pipe; physical PHY/DDR not simulated.'}
(V/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');assert ok
