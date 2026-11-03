"""Compare compact and original camera transport using actual vendor RAM models."""
from pathlib import Path
import hashlib,json,re,subprocess,sys,time
sys.stdout.reconfigure(encoding='utf-8')
R=Path(__file__).resolve().parents[1];H=R/'user_source/hdl_source';V=R/'validation/native_awb_model';V.mkdir(exist_ok=True)
B=Path(r'D:\anlu\altera\14.1S\modelsim_ase\win32aloem');L=Path(r'D:\anlu\TD_6.2.1_Engineer_6.2.168.116\sim_release\ph1p')
tb=(R/'validation/awb_transport_tb.v').read_text(encoding='utf-8')
tb=re.sub(r'module blk_mem_gen_awb_delay_signal\(.*?endmodule','',tb,flags=re.S)
tb=tb.replace('module awb_transport_tb;', '''module awb_transport_tb;
 // Original generated input ports are unconnected in RTL. TD ties these to
 // zero (SYN-5025); give the vendor model those same synthesized constants.
 initial begin
  force prior.signal_delay_d.blk_mem_gen_awb_delay_signal_d.web=1'b0;
  force prior.signal_delay_d.blk_mem_gen_awb_delay_signal_d.dib=96'd0;
 end
''')
(V/'native_awb_tb.v').write_text(tb,encoding='utf-8')
ip=R/'user_source/ip_source/blk_mem_gen_awb_delay_signal'
steps=[('vmap_init',[B/'vmap.exe','-c']),('vlib',[B/'vlib.exe','work']),('vmap_work',[B/'vmap.exe','work','work']),
 ('vlog',[B/'vlog.exe','-sv','-work','work',L/'ph1p_phy_gsr.v',L/'ph1p_logic_eram.v',V/'native_awb_tb.v',
 R/'validation/awb_v4_reference.v',H/'awb.v',H/'wb_gain_control.v',H/'signal_delay.v',H/'signal_delay_compact.v',H/'awb_line_memory.v',
 ip/'blk_mem_gen_awb_delay_signal.v',ip/'ram_f84573da5ab5.v']),
 ('vsim',[B/'vsim.exe','-c','-do','vsim work.PH1P_PHY_GSR work.awb_transport_tb; onfinish stop; run -all; quit -f'])]
start=time.time();results={}
for name,cmd in steps:
 p=subprocess.run(list(map(str,cmd)),cwd=V,capture_output=True,text=True,timeout=240)
 log=p.stdout+p.stderr;(V/(name+'.log')).write_text(log,encoding='utf-8');print(name,log[-1200:],flush=True)
 assert p.returncode==0 and '** Error' not in log and '** Fatal' not in log,(name,log[-2000:])
 if name=='vsim':assert 'AWB_TRANSPORT_PASS beats=691200' in log
results={'native_vendor_model':True,'tests':{'native_awb_transport':{'pass':True,'pixels':2764800}},'seconds':round(time.time()-start,2),
 'source_sha256':{p.relative_to(R).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (R/'user_source').rglob('*') if p.is_file()}}
(V/'result.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print('NATIVE_AWB_MODEL_PASS',flush=True)
