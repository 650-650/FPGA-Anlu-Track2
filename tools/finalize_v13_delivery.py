"""Export only fresh, timing-clean V13 artifacts bound to verified sources."""
from pathlib import Path
import hashlib,json,re,shutil,datetime,argparse,sys
R=Path(__file__).resolve().parents[1]
from v13_baseline import resolve_baseline
B=resolve_baseline(R)
parser=argparse.ArgumentParser()
parser.add_argument('--run',choices=['phy_1','phy_seed2'],default='phy_1')
run=parser.parse_args().run
P=R/'td_project/camera_to_dsi_display_Runs'/run
O=R/'output';O.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def js(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def check_hashes(values,root=R):
    for name,h in values.items():
        p=Path(name)
        if not p.is_absolute():p=root/str(name).replace('\\','/')
        assert p.is_file() and sha(p)==h,('stale input',str(p))
signature=js(R/'validation/build_input_signature.json')
check_hashes(signature['source_sha256'])
started=datetime.datetime.fromisoformat(signature['started']).timestamp()
implementation_started=started
implementation_signature=None
if run!='phy_1':
    ip=R/'validation'/f'{run}_input_signature.json'
    implementation_signature=js(ip)
    check_hashes(implementation_signature['source_sha256'])
    assert implementation_signature['original_build_signature_sha256']==sha(R/'validation/build_input_signature.json')
    assert implementation_signature['seed']==2 and implementation_signature['run']==run
    gate=R/'td_project/camera_to_dsi_display_Runs/syn_1/camera_to_dsi_display_gate.db'
    assert sha(gate)==implementation_signature['gate_db_sha256'],'synthesis database changed'
    implementation_started=datetime.datetime.fromisoformat(implementation_signature['started']).timestamp()
for stage in ['syn_1',run]:
    p=R/f'td_project/camera_to_dsi_display_Runs/{stage}/build_console.log'
    s=p.read_text(encoding='utf-8',errors='replace')
    threshold=started if stage=='syn_1' else implementation_started
    assert p.stat().st_mtime>=threshold and 'FUSION_BUILD_STAGE_PASS' in s,(stage,'not complete')
    assert not re.search(r'(?mi)\bERROR\s*:|license checkout failed',s),(stage,'tool error')
    if stage=='phy_seed2':assert 'SEED2_PLACE_PARAMETER_CONFIRMED 2' in s,'seed setting was not confirmed by TD'
timing=P/'camera_to_dsi_display_phy.ts';area=P/'camera_to_dsi_display_phy.area'
bit=P/'camera_to_dsi_display.bit'
for p in [timing,area,bit,P/'camera_to_dsi_display_pr.timing']:
    assert p.is_file() and p.stat().st_mtime>=implementation_started,('old/missing artifact',str(p))
t=timing.read_text(encoding='utf-8')
times={n:float(re.search(r'\b'+n+r':\s*(-?[\d.]+)ns',t)[1]) for n in ['SWNS','STNS','HWNS','HTNS']}
assert times['SWNS']>=0 and times['HWNS']>=0 and times['STNS']==0 and times['HTNS']==0,times
a=area.read_text(encoding='utf-8');resources={}
for n,pattern,cap in [('lut6',r'^#lut6\s+(\d+)',21216),('slice',r'^#slice\s+(\d+)',21216),('slice_reg',r'^\s*#slice reg\s+(\d+)',42432),('eram',r'^#eram\s+(\d+)',108),('dsp',r'^#dsp\s+(\d+)',40)]:
    used=int(re.search(pattern,a,re.M)[1]);assert used<=cap,(n,used,cap)
    resources[n]={'used':used,'capacity':cap,'remaining':cap-used}
reports={}
def report(label,rel,status='pass'):
    p=R/rel;v=js(p);assert v[status] in [True,'PASS'],(label,v.get(status))
    reports[label]={'path':rel,'sha256':sha(p)}
    return v
unit=report('observer','validation/latency_v12_unit/result.json')
assert unit['cases']>=30 and unit['checks']>=158
check_hashes(unit['source_sha256']);check_hashes(unit['test_sources_sha256'])
hud=report('chinese_hud','validation/chinese_hud/result.json','status');check_hashes(hud['sources'])
assert hud['page_cases']>=51 and hud['compared_pixels']>=11750400
start=report('startup_and_vtc','validation/latency_startup/result.json','passed')
for v in start['results']:
    assert v['returncode']==0 and v['sources_still_current'];check_hashes(v['source_sha256'])
actual=report('actual_clock_hud_snapshot','validation/latency_actual_clocks/result.json','passed')
check_hashes(actual['source_sha256'])
assert actual['sources_still_current'] and actual['clock_period_ns']['ddr']==15.0
assert actual['hud_snapshot_valid_frames']>=3 and all(s['status_hex']=='00' for s in actual['hud_snapshot_samples'])
assert int(actual['metrics']['updates'])>=5 and int(actual['metrics']['under'])==0
assert actual['testbench_sha256']==sha(R/'validation/latency_actual_clocks/actual_clocks_tb.sv')
assert actual['tool_sha256']==sha(R/actual['tool'].replace('\\','/'))
front=report('full_raw_isp','validation/latency_frontend/native_video/csi_unpack/single_fifo/result.json')
check_hashes(front['source_sha256'])
assert not front['fast'] and front['native_video'] and front['csi_unpack'] and front['single_fifo'] and front['source_unchanged_during_test']
front_log=(R/'validation/latency_frontend/native_video/csi_unpack/single_fifo/run.log').read_text(encoding='utf-8')
assert front['testbench_sha256']==sha(R/'validation/latency_frontend/native_video/csi_unpack/single_fifo/frontend_tb.v')
assert (front['checked_raw_groups'],front['packed_words'],front['native_written_words_align0'],front['overflow_hits'])==(460800,345600,345600,0)
assert front['sof_to_valid_clocks']==[55,55]
assert 'FRONTEND_IDENTITY_PASS raw=460800 packed=345600' in front_log
assert 'NATIVE_VIDEO_INPUT_SINGLE_PASS packed=345600 align0=345600 overflow=0' in front_log
assert re.findall(r'PACK_VALID_GAP frame=\d+ gap=(\d+) clocks',front_log)==['55','55']
blank=report('blank_error','validation/latency_frontend/blank_error/result.json');check_hashes(blank['source_sha256'])
prot=report('preservation','validation/v13_preservation/result.json')
check_hashes(prot['source_sha256']);check_hashes(prot['baseline_source_sha256'],B)
assert set(prot['timing_equivalent_sources'])=={
    'user_source/hdl_source/isp/stylize_v5_96.v',
    'user_source/hdl_source/isp/style_guide_v8.v',
    'user_source/hdl_source/first_aid_detector.v'}
scope_ref=prot['timing_equivalence_reports']['style_retiming_scope']
assert sha(R/scope_ref['path'])==scope_ref['sha256']
scope=report('style_retiming_scope',scope_ref['path']);check_hashes(scope['source_sha256'])
assert scope['tool_sha256']==sha(R/'tools/verify_style_retiming_scope.py')
for label in ['style_retiming_quick','style_retiming_full']:
    ref=prot['timing_equivalence_reports'][label]
    assert sha(R/ref['path'])==ref['sha256']
    sv=report(label,ref['path']);check_hashes(sv['source_sha256'])
    assert sv['tool_sha256']==sha(R/'tools/verify_style_retiming.py')
    assert sv['mathematical_identity']['fixed_latency_clocks']==16
    for name,test in sv['tests'].items():
        assert test['pass'] and test['testbench_sha256']==sha(R/'validation/style_retiming'/name/'tb.sv')
aidref=prot['timing_equivalence_reports']['aid_timing'];assert sha(R/aidref['path'])==aidref['sha256']
aid=report('aid_timing',aidref['path'])
assert aid['current_sha256']==sha(R/'user_source/hdl_source/first_aid_detector.v')
assert aid['reference_sha256']==sha(B/'user_source/hdl_source/first_aid_detector.v')
assert aid['verifier_sha256']==sha(R/'tools/verify_aid_timing_equivalence.py')
assert aid['exhaustive_rgb_count']==16777216 and aid['paired_frames']>=32
assert prot['verifier_sha256']==sha(R/'tools/verify_v13_preservation.py')

for p in [R/'tools/finalize_v13_delivery.py',R/'tools/freeze_v13_build.py',R/'tools/v13_baseline.py']:
    reports[p.stem]={'path':p.relative_to(R).as_posix(),'sha256':sha(p)}
log=(P/'build_console.log').read_text(encoding='utf-8',errors='replace')
critical=list(dict.fromkeys(l.strip() for l in log.splitlines() if 'CRITICAL-WARNING:' in l))
# This is the crop baseline's inherited clock/IP warning set. Review every new item.
baseline_log=(B/'td_project/camera_to_dsi_display_Runs/phy_1/build_console.log').read_text(encoding='utf-8',errors='replace')
baseline_critical=list(dict.fromkeys(l.strip() for l in baseline_log.splitlines() if 'CRITICAL-WARNING:' in l))
assert set(critical)==set(baseline_critical),('new critical warning',critical,baseline_critical)
name='stylize_flame_fusion_v13_latency_chinese_timing.bit'
# Independent implementations can finish in either order. Only a fully
# verified implementation may claim the release, and a later run cannot
# silently replace its bit/manifest while the user is reading the result.
selection=R/'validation/selected_implementation.json'
choice={'run':run,'bit_sha256':sha(bit),'timing_ns':times}
try:
    with selection.open('x',encoding='utf-8') as f:json.dump(choice,f,indent=2)
except FileExistsError:
    previous=js(selection)
    if previous['run']!=run:
        print('V13_IMPLEMENTATION_NOT_SELECTED',previous['run'])
        sys.exit(10)
    assert previous['bit_sha256']==sha(bit),'selected implementation changed; explicit review needed'
shutil.copy2(bit,O/name)
for p in [area,timing,P/'camera_to_dsi_display_pr.timing']:shutil.copy2(p,O/p.name)
manifest={
    'date':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
    'baseline':str(B),'baseline_bit_sha256':js(B/'output/fix_manifest.json')['sha256'],
    'bitstream':name,'bit_sha256':sha(O/name),'bit_bytes':(O/name).stat().st_size,
    'implementation_run':run,'placement_seed':2 if run=='phy_seed2' else 0,
    'implementation_signature':None if implementation_signature is None else {
        'path':f'validation/{run}_input_signature.json','sha256':sha(R/'validation'/f'{run}_input_signature.json')},
    'implementation_configuration_sha256':{p.relative_to(R).as_posix():sha(p) for p in [P/'settings.cfg',P/'camera_to_dsi_display.tcl',P/'camera_to_dsi_display.prj']},
    'timing_ns':times,'resources':resources,'critical_warnings':critical,'new_critical_warnings':False,
    'high_utilization_warnings':list(dict.fromkeys(l.strip() for l in log.splitlines() if 'PHY-7022 WARNING:' in l)),
    'source_sha256':{p.relative_to(R).as_posix():sha(p) for p in (R/'user_source').rglob('*') if p.is_file()},
    'build_input_signature':{'path':'validation/build_input_signature.json','sha256':sha(R/'validation/build_input_signature.json')},
    'tests':reports,
    'measurement':{'start':'First accepted RAW group before ISP, after MIPI/CSI unpacking',
        'end':'First active pixel at final HDMI transmitter input of that same frame',
        'includes':['ISP processing','actual DDR buffer waiting and read selection','final display pipeline'],
        'excludes':['sensor exposure','MIPI/CSI unpacking before RAW measurement point','HDMI cable and monitor response'],
        'result':'Last fully observed and retired display frame; not the newest camera timestamp',
        'timer_us':1,'display_ms':0.01,'maximum_ms':1000,'empty_or_unprovable':'hyphens and diagnostic status'},
    'repairs':{'startup':'video_out inverse-VS synchronizers explicitly reset to idle 1; no synthetic read frame',
        'raw_error':'Only active RAW groups qualify lane-error invalidation',
        'input_alignment_default_clocks':0,'complete_isp_sof_to_packed_valid_clocks':55,
        'chinese':'All selectable OSD pages translated, hardware key IDs and hexadecimal digits retained',
        'style_timing':'Equivalent window/gradient retiming; all four modes cycle-exact at unchanged LAT16',
        'aid_timing':'Only green tail expression rewritten; complete 24-bit RGB and paired state equality',
        'monitor_encoding':'Equivalent absolute 22-bit word counter representation; decoded relative count retains all validity guards',
        'sensor_window':[192,1639],'output_size':[1280,720],'display_roi_y':[176,208]},
    'programmed':False,'observed_on_board':False,
    'pending':['Board latency numeric readout and Chinese readability','Visual/recognition comparison in same lighting','Black-spot result and long-run/power-cycle hardware acceptance'],
    'limits':['Simulation uses behavioral RAM/ordered DDR where documented; physical MIPI/DDR/TMDS are not simulated',
        'Source equality preserves existing algorithms but is not proof of physical board visual acceptance',
        'Existing vendor clock/IP critical warnings are retained and enumerated; no new critical warning is accepted']}
(O/'build_manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
(O/'SHA256.txt').write_text(manifest['bit_sha256']+'  '+name+'\n',encoding='ascii')
print('V13_DELIVERY_AUDIT_PASS',json.dumps({'bit':name,'sha256':manifest['bit_sha256'],'timing_ns':times,'resources':resources},ensure_ascii=False))
