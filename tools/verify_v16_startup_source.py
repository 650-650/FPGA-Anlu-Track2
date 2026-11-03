"""Actual video_in/FIFO tests: late DDR must neither lock metadata nor borrow t0."""
from pathlib import Path
import json,hashlib,re,subprocess,time
R=Path(__file__).resolve().parents[1];H=R/'user_source/hdl_source';IP=R/'user_source/ip_source'
V=R/'validation/startup_source_identity';V.mkdir(parents=True,exist_ok=True)
A=R.parent/'v16_integration_audit';t=(A/'startup_sequence_tb.sv').read_text(encoding='utf-8')
t=t.replace('parameter MODE=0;','parameter MODE=0, DDR_HALF_PS=7500, PHASE_PS=0;')
t=t.replace('always #7.5 if(ddr_enabled)ddr=~ddr;',
 'initial begin #(PHASE_PS/1000.0);forever #(DDR_HALF_PS/1000.0)if(ddr_enabled)ddr=~ddr;end')
a=t.index('  if(MODE==1 || MODE==3)begin');b=t.index('  if(MODE==2)begin',a)
t=t[:a]+'''  if(MODE==1 || MODE==3)begin
   if(mon.pack_sequence!=12 || mon.claim_sequence!=10 || mon.metadata_ready!==4'b1111 || mon.write_complete!==4'b1111 || mon.slot_bad!==0)
    $fatal(1,"late DDR metadata did not recover autonomously");
   $display("LATE_DDR_AUTONOMOUS_METADATA_RECOVERY_PASS");
  end
'''+t[b:]
t=t.replace('|| wrong_bindings!=4)', '|| wrong_bindings!=0)')
t=t.replace('one missing DDR SOF did not isolate wrong apparently-good metadata','one lost DDR SOF caused a wrong source identity')
t=t.replace('ONE_LOST_SOF_WRONG_SOURCE_METADATA_REPRODUCED','ONE_LOST_SOF_CORRECT_SOURCE_IDENTITY_PASS')
# Independently inspect all completed healthy slots, not just terminal flags.
probe=r'''
real origin_time[0:15],reset_epoch=0;
integer identity_checks=0,si,sid,age_error;
always @(posedge rst)reset_epoch=$realtime;
always @(posedge cam)if(rst && ru && rv)origin_time[source_frames%12==0?12:source_frames%12]=$realtime;
always @(negedge ddr)if(rst)begin
 for(si=0;si<4;si=si+1)if(mon.metadata_ready[si] && mon.write_complete[si] && !mon.slot_bad[si])begin
  identity_checks=identity_checks+1;sid=mon.slot_id[si];
  if(mon.slot_id[si]!==stored_frame[si])$fatal(1,"wrong apparently-valid frame identity slot=%0d metadata=%0d pixel=%0d",si,mon.slot_id[si],stored_frame[si]);
  if(sid>=1 && sid<=12)begin
   age_error=$rtoi(($itor(mon.slot_time[si])*1000.0-(origin_time[sid]-reset_epoch))/1000.0);
   if(age_error>2 || age_error< -2)$fatal(1,"wrong source timestamp id=%0d error=%0d",sid,age_error);
  end
 end
end
'''
t=t.replace('  $display("STARTUP_SEQUENCE_AUDIT_PASS mode=%0d",MODE);',
 '  $display("IDENTITY_CHECKS %0d",identity_checks);\n  $display("STARTUP_SEQUENCE_AUDIT_PASS mode=%0d",MODE);')
t=t.replace('endmodule',probe+'\nendmodule')
tb=V/'tb.sv';tb.write_text(t,encoding='utf-8')
files=[tb,H/'video_in.v',H/'frame_latency_monitor.v',H/'fusion_controls.v',IP/'w128_d512_fifo/w128_d512_fifo.v',IP/'w128_d512_fifo/soft_fifo_al_4057d6b76aa6.v']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();src={str(p):sha(p) for p in files}
iv=Path(r'D:\anlu\iverilog\bin\iverilog.exe');results=[]
cases=[(mode,7500,0) for mode in range(5)]+[(mode,half,phase) for mode in [0,1,4] for half in [6000,12000] for phase in [500,3500,7250,11250]]
for mode,half,phase in cases:
 d=V/f'm{mode}_half{half}_phase{phase}';d.mkdir(exist_ok=True)
 cmd=[str(iv),'-g2012','-s','startup_sequence_tb',f'-Pstartup_sequence_tb.MODE={mode}',f'-Pstartup_sequence_tb.DDR_HALF_PS={half}',f'-Pstartup_sequence_tb.PHASE_PS={phase}','-o',str(d/'sim.vvp'),*map(str,files)]
 c=subprocess.run(cmd,capture_output=True,text=True);(d/'compile.log').write_text(c.stdout+c.stderr,encoding='utf-8');assert c.returncode==0,c.stderr
 c=subprocess.run([str(iv.with_name('vvp.exe')),'-i',str(d/'sim.vvp')],capture_output=True,text=True)
 log=c.stdout+c.stderr;(d/'run.log').write_text(log,encoding='utf-8');assert c.returncode==0,log[-3500:]
 checks=int(re.search(r'IDENTITY_CHECKS (\d+)',log)[1])
 results.append({'mode':mode,'ddr_half_ps':half,'phase_ps':phase,'checks':checks,'pass':True,'log_sha256':sha(d/'run.log')})
 print('SOURCE_STARTUP_PASS',mode,half,phase,checks,flush=True)
assert src=={str(p):sha(p) for p in files}
r={'pass':True,'cases':len(cases),'identity_and_timestamp_checks':sum(x['checks'] for x in results),'source_sha256':src,'verifier_sha256':sha(Path(__file__)),
 'results':results,'limits':'MODE2 intentionally drops two packed SOFs; ambiguous RAW provenance remains fail-closed until shared reset. No borrowing of latest RAW t0.'}
(V/'result.json').write_text(json.dumps(r,indent=2),encoding='utf-8');print('V16_SOURCE_STARTUP_PASS',len(cases),r['identity_and_timestamp_checks'])
