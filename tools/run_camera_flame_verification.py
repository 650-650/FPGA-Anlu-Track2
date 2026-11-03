from pathlib import Path
import hashlib,json,subprocess,sys,time
sys.stdout.reconfigure(encoding='utf-8')
R=Path(__file__).resolve().parents[1];H=R/'user_source/hdl_source';V=R/'validation'
IV=Path(r'D:\anlu\iverilog\bin\iverilog.exe');tests={}
for name,files in [
 ('awb_transport_tb',[V/'awb_v4_reference.v',H/'awb.v',H/'wb_gain_control.v',H/'signal_delay.v',H/'signal_delay_compact.v',H/'awb_line_memory.v']),
 ('flame_daylight_tb',[H/'visual_flame_alarm.v'])]:
 start=time.time();binary=V/(name+'.vvp')
 p=subprocess.run([str(IV),'-g2012','-s',name,'-o',str(binary),str(V/(name+'.v'))]+list(map(str,files)),cwd=R,capture_output=True,text=True,timeout=60)
 (V/(name+'_compile.log')).write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0,p.stderr
 p=subprocess.run([str(IV.with_name('vvp.exe')),str(binary)],cwd=R,capture_output=True,text=True,timeout=240)
 log=p.stdout+p.stderr;(V/(name+'.log')).write_text(log,encoding='utf-8');print(log[-1400:],flush=True)
 assert p.returncode==0 and 'PASS' in log,(name,log)
 tests[name]={'pass':True,'seconds':round(time.time()-start,2),'log':str((V/(name+'.log')).relative_to(R))}
(V/'camera_flame_verification_result.json').write_text(json.dumps({'tests':tests,'source_sha256':{p.relative_to(R).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (R/'user_source').rglob('*') if p.is_file()}},indent=2),encoding='utf-8')
print('CAMERA_FLAME_VERIFICATION_PASS',flush=True)
