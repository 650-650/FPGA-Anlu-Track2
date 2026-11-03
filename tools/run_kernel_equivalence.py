from pathlib import Path
import hashlib,json,subprocess,time,sys
sys.stdout.reconfigure(encoding='utf-8')
R=Path(__file__).resolve().parents[1];V=R/'validation';H=R/'user_source/hdl_source';IV=Path(r'D:\anlu\iverilog\bin\iverilog.exe')
tests={}
for name,files in [
 ('image_quality_equivalence_tb',[V/'image_quality_reference.v',H/'isp/isp_top.v',H/'image_curve_rom.v']),
 ('median_eram_equivalence_tb',[H/'isp/stylize_v5_96.v']),
 ('color_luma_v5_equivalence_tb',[V/'color_luma_v5_reference.v',H/'color_luma_preserve.v'])]:
 t=time.time();binary=V/(name+'.vvp')
 p=subprocess.run(list(map(str,[IV,'-g2012','-s',name,'-o',binary,V/(name+'.v')]+files)),cwd=R,capture_output=True,text=True,timeout=60)
 (V/(name+'_compile.log')).write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0,p.stderr
 p=subprocess.run([str(IV.with_name('vvp.exe')),str(binary)],cwd=R,capture_output=True,text=True,timeout=300)
 log=p.stdout+p.stderr;(V/(name+'.log')).write_text(log,encoding='utf-8');print(log[-1200:],flush=True)
 assert p.returncode==0 and 'PASS' in log,(name,log)
 tests[name]={'pass':True,'seconds':round(time.time()-t,2),'log':'validation/'+name+'.log'}
(V/'kernel_equivalence_result.json').write_text(json.dumps({'tests':tests,'source_sha256':{p.relative_to(R).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (R/'user_source').rglob('*') if p.is_file()}},indent=2),encoding='utf-8')
print('KERNEL_EQUIVALENCE_PASS',flush=True)
