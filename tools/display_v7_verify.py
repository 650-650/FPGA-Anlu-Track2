from pathlib import Path
import hashlib,json,subprocess,time,sys
sys.stdout.reconfigure(encoding='utf-8')
R=Path(__file__).resolve().parents[1];V=R/'validation/display_v7';V.mkdir(exist_ok=True);H=R/'user_source/hdl_source';IV=Path(r'D:\anlu\iverilog\bin\iverilog.exe')
start=time.time();name='display_v7_tb';binary=V/(name+'.vvp')
for stage,cmd in [('compile',[IV,'-g2012','-s',name,'-o',binary,R/'validation'/f'{name}.v',H/'display_contrast.v']),('run',[IV.with_name('vvp.exe'),binary])]:
 p=subprocess.run(list(map(str,cmd)),cwd=R,capture_output=True,text=True,timeout=180);log=p.stdout+p.stderr
 (V/(stage+'.log')).write_text(log,encoding='utf-8');assert p.returncode==0,log[-2000:]
 if stage=='run':assert 'DISPLAY_V7_PASS' in log;print(log,flush=True)
(V/'result.json').write_text(json.dumps({'tests':{name:{'pass':True}},'source_sha256':{p.relative_to(R).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in [H/'display_contrast.v',H/'display_tone.dat']},'seconds':round(time.time()-start,2)},indent=2),encoding='utf-8')
