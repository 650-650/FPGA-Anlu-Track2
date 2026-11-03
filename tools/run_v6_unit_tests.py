from pathlib import Path
import json,hashlib,subprocess,time,sys
sys.stdout.reconfigure(encoding='utf-8')
R=Path(__file__).resolve().parents[1];H=R/'user_source/hdl_source';V=R/'validation';IV=Path(r'D:\anlu\iverilog\bin\iverilog.exe')
tests={}
for name,files in [('aid_tracking_v6_tb',[H/'first_aid_detector.v',V/'aid_parallel_v6_reference.v']),('display_contrast_tb',[H/'display_contrast.v'])]:
 start=time.time();binary=V/(name+'.vvp')
 p=subprocess.run(list(map(str,[IV,'-g2012','-s',name,'-o',binary,V/(name+'.v')]+files)),cwd=R,capture_output=True,text=True,timeout=60)
 (V/(name+'_compile.log')).write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0,p.stderr
 p=subprocess.run([str(IV.with_name('vvp.exe')),str(binary)],cwd=R,capture_output=True,text=True,timeout=300)
 log=p.stdout+p.stderr;(V/(name+'.log')).write_text(log,encoding='utf-8');print(log[-1600:],flush=True)
 assert p.returncode==0 and 'PASS' in log,(name,log)
 tests[name]={'pass':True,'seconds':round(time.time()-start,2),'log':'validation/'+name+'.log'}
(V/'v6_unit_result.json').write_text(json.dumps({'tests':tests,'source_sha256':{p.relative_to(R).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (R/'user_source').rglob('*') if p.is_file()}},indent=2),encoding='utf-8')
print('V6_UNIT_TESTS_PASS',flush=True)
