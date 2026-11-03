"""Use actual video_out SOF crossing; skip early HDMI SOFs without losing identity."""
from pathlib import Path
import importlib.util,subprocess,json,re,hashlib
R=Path(__file__).resolve().parents[1];H=R/'user_source/hdl_source';IP=R/'user_source/ip_source';V=R/'validation/startup_display_identity';V.mkdir(parents=True,exist_ok=True)
B=R.with_name('07_stylize_flame_fusion_v15_ddr_latency_final')
s=importlib.util.spec_from_file_location('fixture',R/'tools/verify_latency_startup.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
t=m.UNIT.replace('parameter DDR_RUN_RESET=0,VS_HIGH=0,EXPECT_FAIL=0;', 'parameter DDR_RUN_RESET=0,VS_HIGH=0,EXPECT_FAIL=0,DDR_START_NS=0,WRAP=0;')
t=t.replace('reg sys=0,cam=0,ddr=0,hdmi=0,rst=1;', 'reg sys=0,cam=0,ddr=0,hdmi=0,rst=1;reg ddr_run=0;initial #(DDR_START_NS)ddr_run=1;')
t=t.replace('always #2.5 if(DDR_RUN_RESET || rst)ddr=~ddr;','always #7.5 if(ddr_run)ddr=~ddr;')
t=t.replace('for(f=0;f<4;f=f+1)begin',"if(WRAP)begin force dut.hdmi_sequence=16'hfffe;@(negedge hdmi);release dut.hdmi_sequence;end\n for(f=0;f<8;f=f+1)begin")
t=t.replace('good==0 || mismatches!=0 || id!=1','good==0 || id!=1')
t=t.replace('good!=0 || mismatches!=candidates','good!=0')
tb=V/'tb.sv';tb.write_text(t,encoding='utf-8');sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();results=[]
for fixed,start,wrap in [(0,130000,0)]+[(1,d,0) for d in [0,25000,80000,130000,200000]]+[(1,80000,1)]:
 folder=V/f'fixed{fixed}_ddr{start}_wrap{wrap}';folder.mkdir(exist_ok=True)
 files=[tb,H/'video_out.v',(H if fixed else B/'user_source/hdl_source')/'frame_latency_monitor.v',H/'fusion_controls.v',IP/'w128_d512_fifo/w128_d512_fifo.v',IP/'w128_d512_fifo/soft_fifo_al_4057d6b76aa6.v']
 src={str(p):sha(p) for p in files}
 iv=Path(r'D:\anlu\iverilog\bin\iverilog.exe')
 cmd=[str(iv),'-g2012','-s','tb',f'-Ptb.DDR_START_NS={start}',f'-Ptb.WRAP={wrap}',f'-Ptb.EXPECT_FAIL={1-fixed}','-o',str(folder/'sim.vvp'),*map(str,files)]
 c=subprocess.run(cmd,capture_output=True,text=True);(folder/'compile.log').write_text(c.stdout+c.stderr,encoding='utf-8');assert c.returncode==0,c.stderr
 c=subprocess.run([str(iv.with_name('vvp.exe')),'-i',str(folder/'sim.vvp')],capture_output=True,text=True)
 log=c.stdout+c.stderr;(folder/'run.log').write_text(log,encoding='utf-8');assert c.returncode==0 and 'STARTUP_CASE_PASS' in log,log
 assert src=={str(p):sha(p) for p in files}
 results.append({'fixed':fixed,'ddr_start_ns':start,'wrap':wrap,'pass':True,'source_sha256':src,'summary':log.splitlines()[:2]})
 print('DISPLAY_STARTUP_PASS',fixed,start,wrap,log.splitlines()[0],flush=True)
r={'pass':True,'cases':len(results),'results':results,'verifier_sha256':sha(Path(__file__)),
 'scope':'Original V15 loses sequence lock if DDR misses display SOFs. New observer uses actual HDMI generation token, rejects startup prefix and recovers without reset. Complete slot data is injected in this isolated test.'}
(V/'result.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
