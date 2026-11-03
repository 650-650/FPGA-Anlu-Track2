from pathlib import Path
import hashlib,json,subprocess,sys,time
sys.stdout.reconfigure(encoding='utf-8')
R=Path(__file__).resolve().parents[1];H=R/'user_source/hdl_source';V=R/'validation'
IV=Path(r'D:\anlu\iverilog\bin\iverilog.exe');VVP=IV.with_name('vvp.exe')
tests=[
 ('median_eram_equivalence_tb',[H/'isp/stylize_v5_96.v']),
 ('image_quality_equivalence_tb',[V/'image_quality_reference.v',H/'isp/isp_top.v',H/'image_curve_rom.v']),
 # V6 intentionally replaces paired-pixel edge and global aid candidates.
 # Their new oracles/tracking tests are separate; do not call old behavior equal.
 ('aid_pipeline_tb',[H/f for f in ['fusion_flame_pipeline.v','first_aid_detector.v','visual_flame_alarm.v','camera_frame_watchdog.v','alarm_board_io.v']])]
results={}
for name,files in tests:
    start=time.time();out=V/(name+'.vvp')
    p=subprocess.run([str(IV),'-g2012','-s',name,'-o',str(out),str(V/(name+'.v'))]+list(map(str,files)),cwd=R,capture_output=True,text=True,timeout=90)
    (V/(name+'_compile.log')).write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0,p.stderr
    p=subprocess.run([str(VVP),str(out)],cwd=R,capture_output=True,text=True,timeout=360)
    (V/(name+'.log')).write_text(p.stdout+p.stderr,encoding='utf-8');print(p.stdout[-1000:],flush=True)
    assert p.returncode==0 and 'PASS' in p.stdout,(name,p.stdout,p.stderr)
    results[name]={'pass':True,'seconds':round(time.time()-start,2),'log':str((V/(name+'.log')).relative_to(R))}
source={p.relative_to(R).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (R/'user_source').rglob('*') if p.is_file()}
(V/'feature_verification_result.json').write_text(json.dumps({'tests':results,'source_sha256':source},indent=2),encoding='utf-8')
print('FEATURE_VERIFICATION_PASS',flush=True)
