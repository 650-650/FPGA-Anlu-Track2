"""Actual-clock-rate reduced-height video/latency regression.

Production and original fixture stay unchanged. The only stimulus changes are
three clock half-periods. A passive assertion checks valid tuples at exactly
the actual VTC O_vtc_user phase consumed by the production HUD snapshot.
The RTL fixture watchdog bounds simulation; no subprocess wall-clock timeout
is used, because host clock jumps can misclassify a running simulation.
"""
from pathlib import Path
import importlib.util,subprocess,time,json,hashlib,re
R=Path(__file__).resolve().parents[1]
D=R/'validation/latency_actual_clocks';D.mkdir(exist_ok=True)
s=importlib.util.spec_from_file_location('fixture',R/'tools/latency_v12_video_verify.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
src=R/'validation/latency_startup/native_vtc_lead55_align0/tb.sv'
t=src.read_text(encoding='utf-8')
changes={'always #5.208333 cam=~cam;':'always #8.334 cam=~cam;','always #2.5 ddr=~ddr;':'always #7.5 ddr=~ddr;','always #6.666667 hdmi=~hdmi;':'always #6.6665 hdmi=~hdmi;'}
for old,new in changes.items():
 assert t.count(old)==1,old;t=t.replace(old,new)
# Observe precisely the VTC O_vtc_user phase used by the production HUD
# snapshot. This monitor does not drive a source, transport or end-time input.
hud_probe=r'''
integer hud_snapshot_valid_frames=0;
always @(posedge hdmi)if(rst && actual_vtc.O_vtc_user && mvalid)begin
 hud_snapshot_valid_frames=hud_snapshot_valid_frames+1;
 if(dut.O_status!==8'd0)$fatal(1,"Valid HUD snapshot carries nonzero diagnostic status");
 $display("HUD_SNAPSHOT_VALID id=%0d us=%0d status=%02h",mid,measured,dut.O_status);
end
'''
assert t.count('endmodule')==1
t=t.replace('endmodule',hud_probe+'\nendmodule')
assert t.count('$display("ACTUAL_VTC_PASS");$finish;')==1
t=t.replace('$display("ACTUAL_VTC_PASS");$finish;',
    'if(hud_snapshot_valid_frames<3)$fatal(1,"Too few valid samples reached the actual HUD snapshot phase");\n $display("HUD_SNAPSHOT_VALID_FRAMES count=%0d",hud_snapshot_valid_frames);\n $display("ACTUAL_VTC_PASS");$finish;')
(D/'actual_clocks_tb.sv').write_text(t,encoding='utf-8')
files=[*m.FILES,R/'user_source/hdl_source/vtc/uivtc.v']
source_hash={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
c=subprocess.run([str(m.IV),'-g2012','-s','latency_video_tb','-Platency_video_tb.FULL=1','-Platency_video_tb.STYLE=0','-Platency_video_tb.LEAD=55','-Platency_video_tb.ALIGN=0','-Platency_video_tb.LINES=8','-o',str(D/'sim.vvp'),str(D/'actual_clocks_tb.sv'),*[str(p) for p in files]],capture_output=True,text=True)
(D/'compile.log').write_text(c.stdout+c.stderr,encoding='utf-8')
if c.returncode:print(c.stderr);raise SystemExit(c.returncode)
start=time.monotonic()
with (D/'run.log').open('w',encoding='utf-8') as f:p=subprocess.run([str(m.VVP),str(D/'sim.vvp')],stdout=f,stderr=subprocess.STDOUT,text=True)
log=(D/'run.log').read_text(encoding='utf-8');print(log[-5000:],flush=True)
metric=re.search(r'VTC_RESULT (.*)',log)
result={'passed':p.returncode==0 and 'ACTUAL_VTC_PASS' in log,'returncode':p.returncode,'seconds_host_clock_may_jump':time.monotonic()-start,'scope':'Actual-clock-rate simulation of production video/FIFO/ordered MC observer path, 1280x8 reduced-height actual VTC, controlled SOF lead55, final VS/DE delay3313 clocks, behavioral ordered DDR response. Not full physical DDR/MIPI/HDMI or board validation.',
'clock_period_ns':{'sys':20.0,'camera':16.668,'ddr':15.0,'hdmi':13.333},'clock_frequency_mhz':{'sys':50,'camera':1000/16.668,'ddr':1000/15,'hdmi':1000/13.333},
'width':1280,'height':8,'source_frames':9,'sof_lead_clocks':55,'input_alignment_clocks':0,'final_display_delay_clocks':3313,
'changes_from_existing_fixture':changes,'base_fixture':str(src.relative_to(R)),'base_fixture_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'testbench_sha256':hashlib.sha256((D/'actual_clocks_tb.sv').read_bytes()).hexdigest(),'tool':str(Path(__file__).relative_to(R)),'tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
'metrics':dict(re.findall(r'(\w+)=(\d+)',metric[1])) if metric else {},'source_sha256':source_hash,'sources_still_current':source_hash=={str(q.relative_to(R)):hashlib.sha256(q.read_bytes()).hexdigest() for q in files},'measurements':re.findall(r'MEASUREMENT (.*)',log)}
hud_entries=[{'source_id':int(a),'latency_us':int(b),'status_hex':c} for a,b,c in re.findall(r'HUD_SNAPSHOT_VALID id=(\d+) us=(\d+) status=([0-9a-fA-F]+)',log)]
result['hud_snapshot_valid_frames']=len(hud_entries)
result['hud_snapshot_samples']=hud_entries
result['passive_addition']='At actual VTC O_vtc_user, count valid output tuples and assert status0; at unchanged termination assert count>=3. No source stimulus or old assertion/end-time changes.'
result['repeat_updates']=sum('repeat=1' in x for x in result['measurements'])
result['skip_updates']=sum('skip=1' in x for x in result['measurements'])
result['terminal_phase_note']='Unchanged termination can fall while awaiting retirement (instantaneous valid0) after prior valid samples; the new passive VTC-user probe proves tuples were captured at the HUD snapshot phase.'
assert result['sources_still_current']
assert result['passed'] and len(hud_entries)>=3 and all(x['status_hex']=='00' for x in hud_entries)
(D/'result.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps(result,ensure_ascii=False),flush=True)
raise SystemExit(0 if result['passed'] else 1)
