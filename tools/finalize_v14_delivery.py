"""Strict V14 release: fresh timing, unchanged SW1/2, measured provenance."""
from pathlib import Path
import hashlib,json,re,datetime,shutil,argparse
parser=argparse.ArgumentParser();parser.add_argument('--run',choices=['phy_1','phy_seed2'],default='phy_1');run=parser.parse_args().run
R=Path(__file__).resolve().parents[1];O=R/'output';P=R/'td_project/camera_to_dsi_display_Runs'/run;B=R.with_name('07_stylize_flame_fusion_v13_latency_chinese_timing')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
def hashes(values,base=R):
 for rel,h in values.items():
  p=Path(rel);p=p if p.is_absolute() else base/rel.replace('\\','/')
  assert p.is_file() and sha(p)==h,('Source/report stale',str(p))
freeze=read(R/'validation/build_input_signature.json');hashes(freeze['source_sha256'])
assert set(freeze['source_sha256'])=={p.relative_to(R).as_posix() for p in (R/'user_source').rglob('*') if p.is_file()}|{'td_project/camera_to_dsi_display.al','td_project/camera_to_dsi_display.sdc','build.ps1','tools/prepare_project.py','tools/build_stage.tcl'}
start=datetime.datetime.fromisoformat(freeze['started']).timestamp()
implementation_start=start;implementation=None
if run=='phy_seed2':
 implementation=read(R/'validation/phy_seed2_input_signature.json');hashes(implementation['source_sha256'])
 assert implementation['source_sha256']==freeze['source_sha256'] and implementation['seed']==2 and implementation['run']==run
 assert implementation['original_build_signature_sha256']==sha(R/'validation/build_input_signature.json')
 assert implementation['gate_db_sha256']==sha(R/'td_project/camera_to_dsi_display_Runs/syn_1/camera_to_dsi_display_gate.db')
 hashes(implementation['config_sha256'],P)
 implementation_start=datetime.datetime.fromisoformat(implementation['started']).timestamp()
for stage in ['syn_1',run]:
 p=R/'td_project/camera_to_dsi_display_Runs'/stage/'build_console.log';s=p.read_text(encoding='utf-8',errors='replace')
 assert p.stat().st_mtime>=(start if stage=='syn_1' else implementation_start) and 'FUSION_BUILD_STAGE_PASS' in s
 assert not re.search(r'(?mi)\bERROR\s*:|license checkout failed',s)
 if stage=='phy_seed2':assert 'SEED2_PLACE_PARAMETER_CONFIRMED 2' in s
for name in ['camera_to_dsi_display_phy.ts','camera_to_dsi_display_phy.area','camera_to_dsi_display_pr.timing','camera_to_dsi_display.bit']:
 assert (P/name).is_file() and (P/name).stat().st_mtime>=implementation_start
text=(P/'camera_to_dsi_display_phy.ts').read_text();times={k:float(re.search(r'\b'+k+r':\s*(-?[\d.]+)ns',text)[1]) for k in ['SWNS','STNS','HWNS','HTNS']}
assert times['SWNS']>=0 and times['HWNS']>=0 and times['STNS']==times['HTNS']==0,times
critical=lambda p:set(l.strip() for l in p.read_text(encoding='utf-8',errors='replace').splitlines() if 'CRITICAL-WARNING:' in l)
assert critical(P/'build_console.log')==critical(B/'td_project/camera_to_dsi_display_Runs/phy_1/build_console.log'),'New critical warnings require review'
reports={}
def report(label,rel,status='pass'):
 p=R/rel;v=read(p);assert v[status] in [True,'PASS'],(label,v.get(status));reports[label]={'path':rel,'sha256':sha(p)};return v
scope=report('sw1_sw2_preservation','validation/v14_scope/result.json');hashes(scope['source_sha256']);hashes(scope['baseline_source_sha256'],B)
assert scope['top_byte_exact'] and scope['observer_outputs_only_to_hud_snapshot']
assert scope['changed_design_sources']==['user_source/hdl_source/frame_latency_monitor.v']
unit=report('provenance_unit','validation/latency_provenance_unit/result.json');hashes(unit['source_sha256'])
assert unit['cases']>=32 and unit['checks']>=172 and unit['verifier_sha256']==sha(R/'tools/verify_latency_provenance.py')
assert unit['testbench_sha256']==sha(R/'validation/latency_provenance_unit/tb.sv')
repro=report('board_status05_repro','validation/board_status05/result.json');hashes(repro['source_sha256'])
assert repro['tool_sha256']==sha(R/'tools/verify_latency_board_repro.py') and repro['waveform_sha256']==sha(R/repro['waveform'])
assert 'old_status=05 new_status=00' in repro['log']
startup=report('startup_native','validation/latency_startup/result.json','passed')
for case in startup['results']:assert case['returncode']==0 and case['sources_still_current'];hashes(case['source_sha256'])
actual=report('real_clocks','validation/latency_actual_clocks/result.json','passed');hashes(actual['source_sha256']);assert actual['hud_snapshot_valid_frames']>=3
assert actual['sources_still_current'] and int(actual['metrics']['under'])==0
full=report('full720p_pixel_origin','validation/latency_720p_transport/result.json');hashes(full['source_sha256'])
assert full['width']==1280 and full['height']==720 and full['measured_frames']>=4 and full['source_unchanged']
assert full['verifier_sha256']==sha(R/'tools/verify_latency_720p_transport.py') and full['testbench_sha256']==sha(R/'validation/latency_720p_transport/tb.sv')
hud=report('chinese_hud','validation/chinese_hud/result.json','status');hashes(hud['sources']);assert hud['page_cases']>=51
area=(P/'camera_to_dsi_display_phy.area').read_text();resources={}
for key,pat,cap in [('slice',r'^#slice\s+(\d+)',21216),('lut6',r'^#lut6\s+(\d+)',21216),('slice_reg',r'^\s*#slice reg\s+(\d+)',42432),('eram',r'^#eram\s+(\d+)',108),('dsp',r'^#dsp\s+(\d+)',40)]:
 n=int(re.search(pat,area,re.M)[1]);assert n<=cap;resources[key]={'used':n,'capacity':cap,'remaining':cap-n}
name='stylize_flame_fusion_v14_latency_provenance.bit';bit=P/'camera_to_dsi_display.bit'
manifest={'version':'V14','bitstream':name,'bit_sha256':sha(bit),'bit_bytes':bit.stat().st_size,'timing_ns':times,'resources':resources,
 'implementation_run':run,'placement_seed':2 if run=='phy_seed2' else 0,
 'implementation_signature_sha256':sha(R/'validation/phy_seed2_input_signature.json') if implementation else None,
 'baseline':str(B),'baseline_bit_sha256':scope['baseline_bit_sha256'],'source_sha256':scope['source_sha256'],'tests':reports,
 'build_input_signature_sha256':sha(R/'validation/build_input_signature.json'),'critical_warnings':sorted(critical(P/'build_console.log')),
 'measurement':'First accepted RAW group -> first final HDMI active pixel of actual DDR frame generation. Published after complete output/read retirement. Excludes sensor exposure and monitor response.',
 'validity':'Timing provenance/transport integrity, not RAW payload image-quality certification. RAW count/lane quality alone no longer prevents a known full DDR frame from reporting time.',
 'no_sw1_sw2_source_changes':True,'programmed':False,'observed_on_board':False,
 'limits':['Status05 RAW-completeness gate counterexample reproduced; actual physical RAW discrepancy not measured on board.',
 'Full720p pixel-origin/time oracle uses controlled ISP delay and behavioral ordered DDR, not physical PHY.',
 'Static timing and simulation do not establish successful new board readout.']}
O.mkdir(exist_ok=True);shutil.copy2(bit,O/name)
for name2 in ['camera_to_dsi_display_phy.ts','camera_to_dsi_display_phy.area','camera_to_dsi_display_pr.timing']:shutil.copy2(P/name2,O/name2)
(O/'build_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
(O/'SHA256.txt').write_text(manifest['bit_sha256']+'  '+name+'\n',encoding='ascii')
print('V14_STRICT_DELIVERY_PASS',name,manifest['bit_sha256'],times,resources)
