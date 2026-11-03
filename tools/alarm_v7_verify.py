"""Directed tests of the unchanged controls/CDC/fire/buzzer; no state forcing."""
from pathlib import Path
import hashlib,json,subprocess,sys,time
sys.stdout.reconfigure(encoding='utf-8')
R=Path(__file__).resolve().parents[1];V=R/'validation/alarm_v7';H=R/'user_source/hdl_source';V.mkdir(exist_ok=True)
IV=Path(r'D:\anlu\iverilog\bin\iverilog.exe');files=['fusion_controls.v','fusion_flame_pipeline.v','visual_flame_alarm.v','first_aid_detector.v','camera_frame_watchdog.v','alarm_board_io.v']
start=time.time();tests={}
for name,tb in [('fusion_controls_tb',R/'validation/fusion_controls_tb.v'),('alarm_v7_sequence_tb',V/'alarm_v7_sequence_tb.v')]:
 binary=V/(name+'.vvp')
 for stage,cmd in [('compile',[IV,'-g2012','-s',name,'-o',binary,tb]+[H/f for f in files]),('run',[IV.with_name('vvp.exe'),binary])]:
  p=subprocess.run(list(map(str,cmd)),cwd=R,capture_output=True,text=True,timeout=120)
  log=p.stdout+p.stderr;(V/(name+'_'+stage+'.log')).write_text(log,encoding='utf-8');assert p.returncode==0,(name,stage,log[-2000:])
  if stage=='run':assert 'PASS' in log;print(log[-1200:],flush=True)
 tests[name]={'pass':True,'log':str((V/(name+'_run.log')).relative_to(R))}
B=R.with_name('07_stylize_flame_fusion_v6_visual_aid')
hashes={str((H/f).relative_to(R)).replace('\\','/'):hashlib.sha256((H/f).read_bytes()).hexdigest() for f in files}
assert all((H/f).read_bytes()==(B/'user_source/hdl_source'/f).read_bytes() for f in files),'source unexpectedly changed'
result={'tests':tests,'source_sha256':hashes,'all_production_sources_byte_identical_v6':True,'first_entry_permanent_silence_reproduced':False,
 'scope':'Debounced physical keys, real bundled-data CDC and real pixel classifier/temporal confirmation. External SW5/SW6, buzzer wiring and audible hardware not simulated.',
 'candidate_vs_alarm':'Yellow candidate box may be present with O_target=1 and O_alarm=0; only confirmed red alarm enables linked sound.',
 'unchanged_unmute_phase_limit':'Mute hides existing oscillator; unmute can start in silent half-cycle for up to 250ms at default clock, but directed test does not stay silent across a complete period.',
 'seconds':round(time.time()-start,2)}
(V/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('ALARM_V7_VERIFICATION_PASS',flush=True)
