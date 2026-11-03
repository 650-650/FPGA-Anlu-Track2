"""Export only a source-bound V10 with passing final routed setup and hold."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,re,shutil,subprocess,sys

R=Path(__file__).resolve().parents[1];V=R/'validation';O=R/'output'
P=R/'td_project/camera_to_dsi_display_Runs/phy_1'
B=R.with_name('07_stylize_flame_fusion_v9_detail_motion_compact')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return p.read_text(encoding='utf-8')
def dump(p,a):p.write_text(json.dumps(a,ensure_ascii=False,indent=2),encoding='utf-8')
subprocess.run([sys.executable,str(R/'tools/verify_v10_preservation.py')],check=True)
source={p.relative_to(R).as_posix():sha(p) for p in (R/'user_source').rglob('*') if p.is_file()}
frozen=json.loads(read(V/'frozen_build_sources.json'))['source_sha256']
assert source==frozen,'source changed during build'
prefix='user_source/hdl_source/'
scopes={
 'verification_result.json':['fusion_controls.v','fusion_flame_pipeline.v','visual_flame_alarm.v','first_aid_detector.v','camera_frame_watchdog.v','alarm_board_io.v'],
 'extra_verification_result.json':['anlogic_logo_rom.v','hdmi_mixer.v','fusion_hud.v','fusion_menu_rom.v','fusion_telemetry.v','osd_char_lib.v'],
 'feature_verification_result.json':['isp/stylize_v5_96.v','isp/isp_top.v','image_curve_rom.v','first_aid_detector.v','fusion_flame_pipeline.v'],
 'display_v10/result.json':None,'display_v10/quality_result.json':None,
 'cartoon_finish_v9/result.json':None,'cartoon_v10/result.json':None,
 'cartoon_v10/quality_result.json':None,'top_v10_protection/result.json':None,
}
results={}
for filename,paths in scopes.items():
 a=json.loads(read(V/filename));hashes=a['source_sha256']
 requested=list(hashes) if paths is None else [prefix+p for p in paths]
 for f in requested:assert sha(R/f)==hashes[f].lower(),('stale DUT',filename,f)
 for f,h in a.get('oracle_sha256',{}).items():assert sha(R/f)==h,('stale test/model',filename,f)
 for f,h in a.get('baseline_source_sha256',{}).items():assert sha(B/f)==h,('reference changed',filename,f)
 for f,h in a.get('generated_hdl_sha256',{}).items():assert sha(R/f)==h,('generated bench changed',filename,f)
 assert a.get('tests') or a.get('pass'),('no assertions',filename)
 assert all(t['pass'] for t in a.get('tests',{}).values()),('failed assertions',filename)
 if 'pass' in a:assert a['pass'],filename
 if filename in ['display_v10/result.json','cartoon_finish_v9/result.json']:assert a['native_vendor_model'],filename
 results[filename]={'pass':True,'tests':a.get('tests',{}),'scope':a.get('scope'),
   'verified_source_paths':requested,'report_sha256':sha(V/filename),
   'native_vendor_model':a.get('native_vendor_model',False)}
log=read(P/'build_console.log');syn=read(P.parent/'syn_1/build_console.log')
assert 'FUSION_BUILD_STAGE_PASS' in log and 'finish command "bitgen' in log,'TD incomplete'
assert not re.search(r'(?mi)\bERROR\s*:',log+'\n'+syn),'TD error'
ts=read(P/'camera_to_dsi_display_phy.ts')
timing={k:float(re.search(rf'{k}:\s*([-\d.]+)ns',ts)[1]) for k in ['SWNS','STNS','HWNS','HTNS']}
assert timing['SWNS']>=0 and timing['HWNS']>=0 and timing['STNS']==timing['HTNS']==0,('final timing failed',timing)
area=read(P/'camera_to_dsi_display_phy.area');resources={}
for key in ['lut6','slice','slice reg','eram','dsp']:
 m=re.search(r'^\s*#'+re.escape(key)+r'\s+(\d+)\s+out of\s+(\d+)',area,re.M);assert m,key
 used,total=map(int,m.groups());assert used<=total,(key,used,total)
 resources[key]={'used':used,'total':total,'remaining':total-used}
assert resources['dsp']['used']==32,'unexpected DSP use'
old=json.loads(read(B/'output/build_manifest.json'))
warnings=re.findall(r'(?m)^.*CRITICAL-WARNING:.*$',log)
assert sorted(set(warnings))==sorted(set(old['critical_warnings'])),('changed critical clock warning',warnings)
roms={}
for name,count in [('curve_srgb.dat',6),('curve_gain_scaled.dat',2),('display_tone.dat',1)]:
 actual=len(re.findall(r'(?m)^SYN-2541[^\r\n]*'+re.escape(name),syn));assert actual==count,(name,actual,count);roms[name]=actual
bit=P/'camera_to_dsi_display.bit';assert bit.is_file() and bit.stat().st_size>1000000
assert bit.stat().st_mtime>max((R/f).stat().st_mtime for f in source),'bit older than source'
O.mkdir(exist_ok=True);dst=O/'stylize_flame_fusion_v10_final_visual.bit'
shutil.copy2(bit,dst);assert sha(dst)==sha(bit)
for filename in ['camera_to_dsi_display_phy.area','camera_to_dsi_display_phy.ts','camera_to_dsi_display_pr.timing']:
 shutil.copy2(P/filename,O/filename)
cartoon=json.loads(read(V/'cartoon_v10/quality_result.json'))
coloured=json.loads(read(V/'cartoon_v10/coloured_quality_result.json'))
assert coloured['production_sha256']==sha(R/'user_source/hdl_source/isp/stylize_v5_96.v'),'stale coloured-noise production'
assert coloured['model_sha256']==sha(R/'tools/cartoon_v10_model.py'),'stale coloured-noise model'
assert coloured['quality_script_sha256']==sha(R/'tools/cartoon_v10_colour_quality.py'),'stale coloured-noise script'
dependencies={}
for name in ['model_baseline.py','model_denoise.py','guide_v8_model.py','cartoon_v9_model.py','denoise_v8_model.py']:
 f='tools/'+name
 assert sha(R/f)==sha(B/f),('shared independent model dependency changed',name)
 dependencies[f]=sha(R/f)
manifest={'date':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),'bitstream':dst.relative_to(R).as_posix(),
 'bit_sha256':sha(dst),'bit_bytes':dst.stat().st_size,'source_sha256':source,'tests':results,
 'resources':resources,'v9_resources':old['resources'],'timing_ns':timing,
 'critical_warnings':warnings,'critical_warning_contents_unchanged_v9':True,
 'high_utilization_warnings':sorted(set(re.findall(r'(?m)^PHY-7022[^\r\n]*',log))),
 'rom_initializations':roms,'preservation':json.loads(read(V/'v10_preservation_result.json')),
 'unchanged_model_dependencies_sha256':dependencies,
 'top_video_registered_stages':1666,'raw_control_to_output_registered_stages':1660,
 'clear_filter_exact_v9':True,'sketch_edge_exact_v9':True,
 'camera_exposure_awb_dehaze_clear_curve_detection_tracking_aid_alarm_controls_unchanged':True,
 'cartoon_quality':cartoon,'coloured_noise_diagnostic':coloured,
 'all8_natural_inputs_improved':cartoon['diagnostics']['all8_improved'],
 'programmed':False,'observed_on_board':False,
 'limits':['software checks do not guarantee same-scene visual preference or all noise levels improve',
 'cartoon colour quantization deliberately reduces fine shading; threshold shoulders may amplify noise',
 'clear noise/detail alternatives were rejected; clear output is unchanged from accepted compact V9',
 'sensor exposure, DDR traffic, display response and physical alarm sound are outside these simulations'],
 'pending':['same-scene hardware comparison of cartoon colour regions and dark noise',
 'physical SW1/SW2 controls and detection/alarm regression','power-cycle and long-run stability']}
dump(O/'build_manifest.json',manifest)
print('V10_DELIVERY_READY',json.dumps({k:manifest[k] for k in ['bitstream','bit_sha256','resources','timing_ns','programmed']},ensure_ascii=False))
