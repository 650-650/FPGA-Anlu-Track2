"""Export only a fresh V15 build with nonnegative setup/hold and current tests."""
from pathlib import Path
import json,hashlib,re,datetime,shutil,argparse
p=argparse.ArgumentParser();p.add_argument('--run',choices=['phy_1','phy_seed2'],default='phy_1');run=p.parse_args().run
R=Path(__file__).resolve().parents[1];B=R.with_name('07_stylize_flame_fusion_v14_latency_provenance')
P=R/'td_project/camera_to_dsi_display_Runs'/run;O=R/'output'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
def hashes(values,base=R):
 for rel,h in values.items():
  p=Path(rel);p=p if p.is_absolute() else base/rel.replace('\\','/')
  assert p.is_file() and sha(p)==h,('STALE_SOURCE_OR_REPORT',str(p))
f=read(R/'validation/build_input_signature.json');hashes(f['source_sha256'])
assert set(f['source_sha256'])=={p.relative_to(R).as_posix() for p in (R/'user_source').rglob('*') if p.is_file()}|{'td_project/camera_to_dsi_display.al','td_project/camera_to_dsi_display.sdc','build.ps1','tools/prepare_project.py','tools/build_stage.tcl'}
start=datetime.datetime.fromisoformat(f['started']).timestamp();ps=start
implementation=None
if run=='phy_seed2':
 implementation=read(R/'validation/phy_seed2_input_signature.json');hashes(implementation['source_sha256'])
 assert implementation['source_sha256']==f['source_sha256'] and implementation['seed']==2
 assert implementation['original_build_signature_sha256']==sha(R/'validation/build_input_signature.json')
 assert implementation['gate_db_sha256']==sha(R/'td_project/camera_to_dsi_display_Runs/syn_1/camera_to_dsi_display_gate.db')
 hashes(implementation['config_sha256'],P);ps=datetime.datetime.fromisoformat(implementation['started']).timestamp()
for stage,ts in [('syn_1',start),(run,ps)]:
 p=R/'td_project/camera_to_dsi_display_Runs'/stage/'build_console.log';t=p.read_text(encoding='utf-8',errors='replace')
 assert p.stat().st_mtime>=ts and 'FUSION_BUILD_STAGE_PASS' in t
 assert not re.search(r'(?mi)\bERROR\s*:|license checkout failed',t)
 if stage=='phy_seed2':assert 'SEED2_PLACE_PARAMETER_CONFIRMED 2' in t
for n in ['camera_to_dsi_display_phy.ts','camera_to_dsi_display_phy.area','camera_to_dsi_display_pr.timing','camera_to_dsi_display.bit']:
 assert (P/n).is_file() and (P/n).stat().st_mtime>=ps,n
t=(P/'camera_to_dsi_display_phy.ts').read_text()
timing={k:float(re.search(r'\b'+k+r':\s*(-?[\d.]+)ns',t)[1]) for k in ['SWNS','STNS','HWNS','HTNS']}
assert timing['SWNS']>=0 and timing['HWNS']>=0 and timing['STNS']==timing['HTNS']==0,timing
critical=lambda p:set(l.strip() for l in p.read_text(encoding='utf-8',errors='replace').splitlines() if 'CRITICAL-WARNING:' in l)
assert critical(P/'build_console.log')==critical(B/'td_project/camera_to_dsi_display_Runs/phy_seed2/build_console.log'),'REVIEW_NEW_CRITICAL_WARNINGS'
reports={}
def report(label,rel,flag='pass'):
 p=R/rel;v=read(p);assert v[flag] in [True,'PASS'],(label,v.get(flag))
 if 'source_sha256' in v:hashes(v['source_sha256'])
 if 'sources' in v:hashes(v['sources'])
 if 'sources_still_current' in v:assert v['sources_still_current']
 reports[label]={'path':rel,'sha256':sha(p)};return v
s=report('source_preservation','validation/v15_scope/result.json');hashes(s['baseline_source_sha256'],B)
assert s['top_diff_only_passive_SW3_debug'] and s['video_out_only_observer_full_flag'] and s['sw1_styles_denoise_clarity_byte_exact'] and s['sw2_detector_tracking_alarm_byte_exact']
for label,folder,script in [('ddr_handshake','ddr_handshake','verify_ddr_handshake.py'),('ddr_handshake_continuous','ddr_handshake_stream','verify_ddr_handshake_stream.py')]:
 v=report(label,f'validation/{folder}/result.json','passed');assert len(v.get('cases',v.get('summary',[])))==9
 assert v['verifier_sha256']==sha(R/'tools'/script)
v=report('real_RTL_waveform','validation/handshake_waveform/result.json');assert v['vcd_sha256']==sha(R/'validation/handshake_waveform/lost_read.vcd')
v=report('provenance_unit','validation/latency_provenance_unit/result.json');assert v['cases']==32 and v['checks']>=172
assert v['testbench_sha256']==sha(R/'validation/latency_provenance_unit/tb.sv')
v=report('monitor_cycle_equivalence','validation/monitor_equivalence/result.json');assert v['cases']==32 and v['compared_hdmi_clocks']>=20000
v=report('startup_8','validation/latency_startup_v15/result.json','passed');assert v['cases']==8
for case in v['results']:assert case['returncode']==0 and case['sources_still_current'];hashes(case['source_sha256'])
v=report('chinese_HUD','validation/chinese_hud/result.json','status');assert v['page_cases']==51
v=report('HUD_preservation','validation/hud_preservation/result.json');assert len(v['byte_identical_simulated_cases'])==49 and len(v['only_changed_cases'])==2
assert v['old_result_sha256']==sha(B/'validation/chinese_hud/result.json') and v['new_result_sha256']==sha(R/'validation/chinese_hud/result.json')
for label,folder,lines in [('late_returns_rejected','paxi_8p_late_return',8),('overflow_rejected','paxi_8p_strong_stall',8),('full720p_actual_PAXI','paxi_720p',720)]:
 v=report(label,f'validation/{folder}/result.json','passed')
 assert v['height']==lines and v['width']==1280 and v['source_frames']==9
 assert v['pixel_verified_valid_frames']>=5 and v['event_time_verified_frames']==v['pixel_verified_valid_frames']
 assert v['verifier_still_current'] and v['verifier_sha256']==sha(R/'tools/verify_latency_paxi_transport.py')
 assert v['testbench_sha256']==sha(R/f'validation/{folder}/tb.sv')
 if lines==720:
  log=(R/f'validation/{folder}/run.log').read_text(encoding='utf-8')
  assert re.search(r'PAXI_PIXEL_SUMMARY .*output_fifo_overflows=0\b',log)
  assert re.search(r'VTC_RESULT .*under=0\b',log)
v=report('late_return_after_healthy_frames','validation/paxi_8p_late_healthy_return/result.json','passed')
assert v['healthy_frames_before_fault']>=2 and v['healthy_frames_after_fault']>=4
assert v['verifier_sha256']==sha(R/'tools/verify_latency_paxi_late_healthy.py')
area=(P/'camera_to_dsi_display_phy.area').read_text();resources={}
for key,pat,cap in [('slice',r'^#slice\s+(\d+)',21216),('lut6',r'^#lut6\s+(\d+)',21216),('slice_reg',r'^\s*#slice reg\s+(\d+)',42432),('eram',r'^#eram\s+(\d+)',108),('dsp',r'^#dsp\s+(\d+)',40)]:
 n=int(re.search(pat,area,re.M)[1]);assert n<=cap;resources[key]={'used':n,'capacity':cap,'remaining':cap-n}
name='stylize_flame_fusion_v15_ddr_latency_final.bit';bit=P/'camera_to_dsi_display.bit'
m={'version':'V15','bitstream':name,'bit_sha256':sha(bit),'bit_bytes':bit.stat().st_size,
 'timing_ns':timing,'resources':resources,'implementation_run':run,'placement_seed':2 if run=='phy_seed2' else 0,
 'baseline':str(B),'baseline_bit_sha256':s['baseline_bit_sha256'],'source_sha256':s['source_sha256'],
 'tests':reports,'build_input_signature_sha256':sha(R/'validation/build_input_signature.json'),
 'critical_warnings':sorted(critical(P/'build_console.log')),
 'measurement':'First accepted unpacked RAW group -> first final active HDMI transmitter-input pixel of actual buffer generation. Publish after whole frame and read retirement. Excludes sensor exposure and monitor response.',
 'changes':['Fix actual AR/AW/W handshake and command FIFO retirement; hold stable until accepted.',
 'Observe output FIFO full drops as invalid, without changing any FIFO control or pixel routing.',
 'Add coherent read-rejection reason bitmap to existing Chinese SW3 K3 page.'],
 'image_algorithms_camera_crop_detection_controls_unchanged':True,'shared_DDR_transport_modified':True,
 'programmed':False,'observed_on_board':False,
 'limits':['Legal PAXI mismatch deterministically reproduces the lost request. The physical board mismatch event has not been directly probed.',
 'Controller/PHY/memory are behavioral; actual wrapper, native FIFOs/packer/guide/VTC/video transport and observer are used. ISP is a controlled delay fixture.',
 'Strong-stall and late-return fixtures intentionally corrupt some output frames; the observer rejects them. The original prefetch algorithm was not redesigned.',
 'Static timing and simulation do not establish new physical board success or visual acceptance.']}
O.mkdir(exist_ok=True);shutil.copy2(bit,O/name)
for n in ['camera_to_dsi_display_phy.ts','camera_to_dsi_display_phy.area','camera_to_dsi_display_pr.timing']:shutil.copy2(P/n,O/n)
(O/'build_manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8')
(O/'SHA256.txt').write_text(m['bit_sha256']+'  '+name+'\n',encoding='ascii')
print('V15_STRICT_DELIVERY_PASS',name,m['bit_sha256'],timing,resources)
