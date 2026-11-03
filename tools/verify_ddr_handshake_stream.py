"""Stronger common-ready proof: back-to-back beats fill and throttle the FIFO.

The original nine-case testbench is unchanged. This companion replaces only its
5000-transaction common-ready stimulus with continuous one-beat-per-clock input.
All cycle, type, address, data, response and readiness comparisons remain intact.
"""
from pathlib import Path
import subprocess,json,hashlib,re,time
R=Path(__file__).resolve().parents[1];V=R/'validation/ddr_handshake_stream';V.mkdir(parents=True,exist_ok=True)
t=(R/'tools/ddr_handshake_tb.sv').read_text(encoding='utf-8')
old='for(i=0;i<5000;i=i+1)send((i%7)!=0,1000+i);'
new='''for(i=0;i<5000;i=i+1)begin
   @(negedge clk);
   while(!nr || !ory)begin uw=0;ur=0;@(negedge clk);end
   ua=25'((1000+i)*8);ud=data_for(1000+i);uw=(i%7)!=0;ur=!uw;
   exp_write[exp_count]=uw;exp_addr[exp_count]=ua;exp_count=exp_count+1;
   if(uw)begin exp_wdata[exp_writes]=ud;exp_writes=exp_writes+1;end
   else begin exp_rdata[exp_reads]={4{7'd0,ua}};exp_reads=exp_reads+1;end
  end
  @(negedge clk);uw=0;ur=0;'''
assert t.count(old)==1;t=t.replace(old,new)
tb=V/'tb.sv';tb.write_text(t,encoding='utf-8')
files=[tb,R/'tools/ddr2_handshake_stub.sv',R/'user_source/hdl_source/mc_to_user_interface.v',R/'user_source/hdl_source/ph1p35_ddr/ph1p35_324_ddr_wrapper.v',
       R/'user_source/ip_source/w155_d512_fifo/w155_d512_fifo.v',R/'user_source/ip_source/w155_d512_fifo/soft_fifo_al_f58e8b3e1f3d.v',
       R/'validation/ddr_handshake/legacy_mc_to_user_interface.v',R/'validation/ddr_handshake/legacy_ph1p35_324_ddr_wrapper.v']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
before={p.relative_to(R).as_posix():sha(p) for p in files};start=time.monotonic()
cmd=['iverilog','-g2012','-s','handshake_tb','-o',str(V/'sim.vvp'),*map(str,files)]
p=subprocess.run(cmd,capture_output=True,text=True);(V/'compile.log').write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0,p.stderr
p=subprocess.run(['vvp','-i',str(V/'sim.vvp')],capture_output=True,text=True);log=p.stdout+p.stderr
(V/'run.log').write_text(log,encoding='utf-8');print(log,flush=True)
passed=p.returncode==0 and 'DDR_HANDSHAKE_PASS cases=9' in log
unchanged=before=={q.relative_to(R).as_posix():sha(q) for q in files}
result={'passed':passed,'sources_still_current':unchanged,'seconds':time.monotonic()-start,'scope':__doc__,
 'source_sha256':before,'verifier_sha256':sha(Path(__file__)),'summary':re.findall(r'CASE_PASS (.*)',log),'compile_command':cmd}
(V/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');assert passed and unchanged
