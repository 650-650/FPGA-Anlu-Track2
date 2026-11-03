"""Export source-bound V11 only after routed timing and all required checks."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,re,shutil,subprocess,sys
R=Path(__file__).resolve().parents[1];V=R/'validation';O=R/'output'
P=R/'td_project/camera_to_dsi_display_Runs/phy_1'
B=R.with_name('07_stylize_flame_fusion_v10_final_visual')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return p.read_text(encoding='utf-8')
def load(p):return json.loads(read(p))
subprocess.run([sys.executable,str(R/'tools/verify_v11_preservation.py')],check=True)
source={p.relative_to(R).as_posix():sha(p) for p in (R/'user_source').rglob('*') if p.is_file()}
assert source==load(V/'frozen_build_sources.json')['source_sha256'],'source changed during build'
prefix='user_source/hdl_source/'
scopes={
 'verification_result.json':['fusion_controls.v','fusion_flame_pipeline.v','visual_flame_alarm.v','first_aid_detector.v','camera_frame_watchdog.v','alarm_board_io.v'],
 'extra_verification_result.json':['anlogic_logo_rom.v','hdmi_mixer.v','fusion_hud.v','fusion_menu_rom.v','fusion_telemetry.v','osd_char_lib.v'],
 'feature_verification_result.json':['isp/stylize_v5_96.v','isp/isp_top.v','image_curve_rom.v','first_aid_detector.v','fusion_flame_pipeline.v'],
 'cartoon_v11/result.json':None,'cartoon_v11/quality_result.json':None,
 'cartoon_v11/detail_quality_result.json':None,
 'display_v11/result.json':None,'display_v11/quality_result.json':None,
 'display_v11/median_proof.json':None,'top_v11_protection/result.json':None,
}
results={}
for name,paths in scopes.items():
 a=load(V/name);hashes=a.get('source_sha256',a.get('source_and_oracle_sha256',{}));assert hashes,('unbound report',name)
 requested=list(hashes) if paths is None else [prefix+x for x in paths]
 for f in requested:assert sha(R/f)==hashes[f],('stale DUT/model',name,f)
 for f,h in a.get('oracle_sha256',{}).items():assert sha(R/f)==h,('stale oracle',name,f)
 for f,h in a.get('baseline_source_sha256',{}).items():assert sha(B/f)==h,('baseline changed',name,f)
 for f,h in a.get('generated_hdl_sha256',{}).items():assert sha(R/f)==h,('bench changed',name,f)
 assert a.get('tests') or a.get('pass'),('empty verification',name)
 assert all(t['pass'] for t in a.get('tests',{}).values()),('assertion failed',name)
 if 'pass' in a:assert a['pass'],name
 if name=='display_v11/result.json':assert a['native_vendor_model'],'no native RAM verification'
 results[name]={'pass':True,'tests':a.get('tests',{}),'scope':a.get('scope'),
     'verified_source_paths':requested,'report_sha256':sha(V/name)}
log=read(P/'build_console.log');syn=read(P.parent/'syn_1/build_console.log')
assert 'FUSION_BUILD_STAGE_PASS' in log and 'finish command "bitgen' in log,'incomplete TD build'
assert not re.search(r'(?mi)\bERROR\s*:',log+'\n'+syn),'TD error'
ts=read(P/'camera_to_dsi_display_phy.ts')
timing={k:float(re.search(rf'{k}:\s*([-\d.]+)ns',ts)[1]) for k in ['SWNS','STNS','HWNS','HTNS']}
assert timing['SWNS']>=0 and timing['HWNS']>=0 and timing['STNS']==timing['HTNS']==0,('final timing failed',timing)
area=read(P/'camera_to_dsi_display_phy.area');resources={}
for k in ['lut6','slice','slice reg','eram','dsp']:
 m=re.search(r'^\s*#'+re.escape(k)+r'\s+(\d+)\s+out of\s+(\d+)',area,re.M);assert m,k
 used,total=map(int,m.groups());assert used<=total,(k,used,total)
 resources[k]={'used':used,'total':total,'remaining':total-used}
assert resources['dsp']['used']==32,'unexpected DSP change'
old=load(B/'output/build_manifest.json');warnings=re.findall(r'(?m)^.*CRITICAL-WARNING:.*$',log)
assert sorted(set(warnings))==sorted(set(old['critical_warnings'])),('critical clock warnings changed',warnings)
roms={}
for name,count in [('curve_srgb.dat',6),('curve_gain_scaled.dat',2),('display_tone.dat',1)]:
 actual=len(re.findall(r'(?m)^SYN-2541[^\r\n]*'+re.escape(name),syn));assert actual==count,(name,actual,count);roms[name]=actual
for name in ['model_baseline.py','model_denoise.py','guide_v8_model.py','display_v9_model.py']:
 assert sha(R/'tools'/name)==sha(B/'tools'/name),('shared baseline model changed',name)
for item in load(V/'supplied_videos/media_manifest.json'):
 assert sha(Path(item['copied']))==item['sha256'],'supplied video copy changed'
bit=P/'camera_to_dsi_display.bit';assert bit.is_file() and bit.stat().st_size>1000000
assert bit.stat().st_mtime>max((R/f).stat().st_mtime for f in source),'bit predates source'
unit=load(V/'display_v11/result.json');top=load(V/'top_v11_protection/result.json')
assert unit['production_registered_stages']==3307 and unit['production_sample_edge_lag']==3306,'unexpected tested stage count'
assert top['registered_display_stages']==3313 and top['baseline_registered_stages']==1666 and top['added_display_stages']==1647,'top latency differs from delivery notes'
assert top['registered_raw_control_to_denoise_stages']==3307,'control latency differs from delivery notes'
O.mkdir(exist_ok=True);dst=O/'stylize_flame_fusion_v11_cartoon_regions.bit';shutil.copy2(bit,dst);assert sha(dst)==sha(bit)
for f in ['camera_to_dsi_display_phy.area','camera_to_dsi_display_phy.ts','camera_to_dsi_display_pr.timing']:shutil.copy2(P/f,O/f)
manifest={'date':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),'bitstream':dst.relative_to(R).as_posix(),
 'bit_sha256':sha(dst),'bit_bytes':dst.stat().st_size,'source_sha256':source,'tests':results,
 'resources':resources,'v10_resources':old['resources'],'timing_ns':timing,'critical_warnings':warnings,
 'critical_warning_contents_unchanged_v10':True,
 'high_utilization_warnings':sorted(set(re.findall(r'(?m)^PHY-7022[^\r\n]*',log))),
 'rom_initializations':roms,'preservation':load(V/'v11_preservation_result.json'),
 'display_unit_registered_stages':3307,'display_unit_sample_edge_lag':3306,
 'top_video_registered_stages':3313,'raw_control_to_denoise_registered_stages':3307,
 'cartoon_quality':load(V/'cartoon_v11/quality_result.json'),
 'cartoon_detail_diagnostic':load(V/'cartoon_v11/detail_quality_result.json'),
 'impulse_quality':load(V/'display_v11/quality_result.json'),
 'yellow_dot_video_diagnosis':'validation/yellow_dot_v11/diagnosis.md',
 'pre_repair_uniform_test':'validation/yellow_dot_v11/uniform_result.json',
 'programmed':False,'observed_on_board':False,
 'sensor_ae_awb_quality_curve_detection_tracking_aid_alarm_controls_guide_logo_pins_unchanged':True,
 'limits':['strong categorical quantization can increase threshold flicker/noise versus V10 continuous tones',
 'palette cleanup and impulse repair can remove legitimate tiny isolated details',
 'video-derived ROI bounds are approximate; sensor defect and exact source footprint are not proven',
 'larger or near-equal-luminance or noisy defects can escape the repair rules',
 'software and vendor RAM tests do not prove physical yellow spot disappearance or actual recognition accuracy'],
 'pending':['same-scene physical clear/cartoon and dark-noise comparison','physical yellow-spot disappearance',
 'physical SW2 tracking/aid/alarm regression','power-cycle and long-run stability']}
(O/'build_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print('V11_DELIVERY_READY',json.dumps({k:manifest[k] for k in ['bitstream','bit_sha256','resources','timing_ns','programmed']},ensure_ascii=False))
