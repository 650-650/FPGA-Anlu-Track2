from pathlib import Path
import hashlib,json,subprocess,time,sys
sys.stdout.reconfigure(encoding='utf-8')
R=Path(__file__).resolve().parents[1];H=R/'user_source/hdl_source';V=R/'validation'
IV=Path(r'D:\anlu\iverilog\bin\iverilog.exe');VVP=IV.with_name('vvp.exe')
results={}
def run(name,sources,top=None,timeout=180):
    binary=V/(name+'.vvp')
    compile_cmd=[str(IV),'-g2012','-Wall','-s',top or name,'-o',str(binary)]+[str(p) for p in sources]
    t=time.time();c=subprocess.run(compile_cmd,cwd=R,text=True,capture_output=True,timeout=60)
    (V/(name+'_compile.log')).write_text(c.stdout+c.stderr,encoding='utf-8')
    if c.returncode:raise RuntimeError(name+' compile failed: '+c.stderr)
    p=subprocess.run([str(VVP),str(binary)],cwd=R,text=True,capture_output=True,timeout=timeout)
    log=p.stdout+p.stderr;(V/(name+'.log')).write_text(log,encoding='utf-8')
    print(name,log[-700:].strip(),flush=True)
    assert p.returncode==0 and 'PASS' in log and 'FAIL ' not in log,(name,p.returncode,log[-1000:])
    results[name]={'pass':True,'seconds':round(time.time()-t,3),'log':str((V/(name+'.log')).relative_to(R))}
run('fusion_controls_tb',[V/'fusion_controls_tb.v',H/'fusion_controls.v'])
run('fusion_osd_cdc_tb',[V/'fusion_osd_cdc_tb.v',H/'fusion_controls.v'])
run('flame_sensitivity_tb',[V/'flame_sensitivity_tb.v',H/'visual_flame_alarm.v'])
run('flame_tuned_full_resolution_tb',[V/'flame_tuned_full_resolution_tb.v',H/'visual_flame_alarm.v'])
run('fusion_cdc_tb',[V/'fusion_cdc_tb.v',H/'fusion_controls.v'])
run('fusion_pipeline_tb',[V/'fusion_pipeline_tb.v']+[H/f for f in ['fusion_flame_pipeline.v','visual_flame_alarm.v','camera_frame_watchdog.v','alarm_board_io.v','first_aid_detector.v']])
for name in ['flame_tracking_tb','flame_full_resolution_tb']:
    wrapper=V/(name+'_runner.v')
    wrapper.write_text(f'''`timescale 1ns/1ps
module runner;
{name} t();
initial begin wait(t.done);#1;if(t.failures!=0)$fatal(1,"core failures");$display("CORE_REGRESSION_PASS {name}");$finish;end
initial begin #2000000000;$fatal(1,"core test timeout");end
endmodule
''',encoding='ascii')
    run(name,[wrapper,V/(name+'.v'),H/'visual_flame_alarm.v'],top='runner')
sources={str(p.relative_to(R)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in (R/'user_source').rglob('*') if p.is_file()}
(V/'verification_result.json').write_text(json.dumps({'tests':results,'source_sha256':sources},indent=2),encoding='utf-8')
print('FUSION_VERIFICATION_PASS',flush=True)
