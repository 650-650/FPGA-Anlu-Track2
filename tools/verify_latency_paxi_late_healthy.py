"""Late-return test after two healthy video frames already passed the oracle.

Derives from the final reduced-height late-return fixture. Only a validation
copy of the behavior stub changes: inject at read sequence 7 instead of 3.
The production RTL, formal full-resolution model and original reports stay put.
"""
from pathlib import Path
import subprocess,json,hashlib,re,time
R=Path(__file__).resolve().parents[1]
BASE=R/'validation/paxi_8p_late_return';V=R/'validation/paxi_8p_late_healthy_return';V.mkdir(parents=True,exist_ok=True)
tb=V/'tb.sv'
text=(BASE/'tb.sv').read_text(encoding='utf-8')
old='for(c=1;c<9;c=c+1)if(claim_words[c]!=N)$fatal(1,"Complete source write lost words");'
new='''for(c=0;c<9;c=c+1)begin
  $display("INPUT_WRITE_PLAN source=%0d accepted=%0d full_rejected=%0d reset_rejected=%0d DDR_words=%0d expected_burst_words=%0d",c+1,input_accepted[c+1],input_rejected_full[c+1],input_rejected_reset[c+1],claim_words[c],(input_accepted[c+1]/240)*240);
  if(claim_words[c]!=(input_accepted[c+1]/240)*240)$fatal(1,"Actual DDR write differs from independent FIFO acceptance/burst plan");
  if(c!=0 && c!=5 && (input_accepted[c+1]!=N || input_rejected_full[c+1]!=0 || input_rejected_reset[c+1]!=0))$fatal(1,"Unexpected source corruption outside the injected fault window");
 end
 if(input_rejected_full[6]==0 || input_accepted[6]>=N)$fatal(1,"Fault must exercise the independently observed source6 FIFO overflow");
 if(verified_source_valid[6])$fatal(1,"Input-overflow source6 generation was incorrectly declared VALID");'''
assert text.count(old)==1;text=text.replace(old,new)
text=text.replace('verified_valid[seq]=1;','verified_valid[seq]=1;verified_source_valid[mid]=1;')
probe=r'''
integer input_generation=0,input_probe_init;
integer input_accepted[0:15],input_rejected_full[0:15],input_rejected_reset[0:15];
reg verified_source_valid[0:15];
reg input_previous_user=0;
initial for(input_probe_init=0;input_probe_init<16;input_probe_init=input_probe_init+1)begin
 input_accepted[input_probe_init]=0;input_rejected_full[input_probe_init]=0;input_rejected_reset[input_probe_init]=0;verified_source_valid[input_probe_init]=0;
end
always @(posedge cam)if(rst)begin
 if(p_user && !input_previous_user)input_generation=input_generation+1;
 input_previous_user=p_user;
 if(vi.aligned_camera_valid)begin
  if(vi.U_w128_d512_fifo.soft_fifo_al_4057d6b76aa6_Inst.wr_rst)input_rejected_reset[input_generation]=input_rejected_reset[input_generation]+1;
  else if(vi.U_w128_d512_fifo.full_flag)input_rejected_full[input_generation]=input_rejected_full[input_generation]+1;
  else input_accepted[input_generation]=input_accepted[input_generation]+1;
 end
end
'''
assert text.count('endmodule')==1
tb.write_text(text.replace('endmodule',probe+'\nendmodule'),encoding='utf-8')
stub=V/'ddr2_video_protocol_stub.sv'
t=(R/'tools/ddr2_video_protocol_stub.sv').read_text(encoding='utf-8')
assert t.count('read_sequence>=3')==1
stub.write_text(t.replace('read_sequence>=3','read_sequence>=7'),encoding='utf-8')
base=json.loads((BASE/'started.json').read_text(encoding='utf-8'))
cmd=base['compile_command'][:]
cmd=[str(V/'sim.vvp') if q==str(BASE/'sim.vvp') else str(tb) if q==str(BASE/'tb.sv') else str(stub) if q==str(R/'tools/ddr2_video_protocol_stub.sv') else q for q in cmd]
files=[Path(q) for q in cmd if q.endswith(('.v','.sv'))]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
hashes={p.relative_to(R).as_posix():sha(p) for p in files}
(V/'started.json').write_text(json.dumps({'compile_command':cmd,'source_sha256':hashes,'verifier_sha256':sha(Path(__file__))},indent=2),encoding='utf-8')
c=subprocess.run(cmd,capture_output=True,text=True);(V/'compile.log').write_text(c.stdout+c.stderr,encoding='utf-8');assert c.returncode==0,c.stderr
print('PAXI_LATE_HEALTHY_RUNNING',V/'run.log',flush=True);start=time.monotonic()
with (V/'run.log').open('w',encoding='utf-8') as f:p=subprocess.run(['vvp','-i',str(V/'sim.vvp')],stdout=f,stderr=subprocess.STDOUT,text=True)
log=(V/'run.log').read_text(encoding='utf-8');print(log[-6000:],flush=True)
pre=log.split('PAXI_FAULT_HOLD')[0];post=log.split('PAXI_FAULT_NEW_VS')[-1]
before=len(re.findall('EXTERNAL_ORACLE_PASS',pre));after=len(re.findall('EXTERNAL_ORACLE_PASS',post))
passed=p.returncode==0 and 'PAXI_TRANSPORT_PASS' in log and before>=2 and after>=4 and 'PAXI_FAULT_HOLD seq=7 ' in log
unchanged=hashes=={q.relative_to(R).as_posix():sha(q) for q in files}
result={'passed':passed,'returncode':p.returncode,'sources_still_current':unchanged,'seconds':time.monotonic()-start,'scope':__doc__,
 'healthy_frames_before_fault':before,'healthy_frames_after_fault':after,'source_sha256':hashes,'verifier_sha256':sha(Path(__file__)),
 'summary':[x for x in log.splitlines() if 'PAXI_FAULT' in x or 'PAXI_REJECTED seq=7' in x or 'PAXI_REJECTED seq=8' in x or 'PAXI_PROTOCOL_COUNTS' in x or 'PAXI_TRANSPORT_PASS' in x]}
(V/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');assert passed and unchanged
