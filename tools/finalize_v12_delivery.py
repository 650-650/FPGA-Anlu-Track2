"""Export V12 only when final timing, current tests and source bindings pass."""
from pathlib import Path
import hashlib,json,re,shutil,datetime
R=Path(__file__).resolve().parents[1]
B=R.with_name('07_stylize_flame_fusion_v11_cartoon_regions')
P=R/'td_project/camera_to_dsi_display_Runs/phy_1'
O=R/'output';O.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def js(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def check_hashes(values,root=R):
    for name,h in values.items():
        p=root/str(name).replace('\\','/')
        assert p.is_file() and sha(p)==h,('stale input',str(p))

signature=js(R/'validation/build_input_signature.json')
check_hashes(signature['source_sha256'])
started=datetime.datetime.fromisoformat(signature['started']).timestamp()
for stage in ['syn_1','phy_1']:
    p=R/f'td_project/camera_to_dsi_display_Runs/{stage}/build_console.log'
    s=p.read_text(encoding='utf-8',errors='replace')
    assert p.stat().st_mtime>=started and 'FUSION_BUILD_STAGE_PASS' in s,(stage,'not complete')
    assert not re.search(r'(?mi)\bERROR\s*:|license checkout failed',s),(stage,'tool error')
timing=P/'camera_to_dsi_display_phy.ts'
area=P/'camera_to_dsi_display_phy.area'
bit=P/'camera_to_dsi_display.bit'
for p in [timing,area,bit,P/'camera_to_dsi_display_pr.timing']:
    assert p.is_file() and p.stat().st_mtime>=started,('old/missing build artifact',str(p))
t=timing.read_text(encoding='utf-8')
times={name:float(re.search(r'\b'+name+r':\s*(-?[\d.]+)ns',t)[1]) for name in ['SWNS','STNS','HWNS','HTNS']}
assert times['SWNS']>=0 and times['HWNS']>=0 and times['STNS']==0 and times['HTNS']==0, times
a=area.read_text(encoding='utf-8')
resources={}
for name,pattern,cap in [('lut6',r'^#lut6\s+(\d+)',21216),('slice',r'^#slice\s+(\d+)',21216),
                         ('slice_reg',r'^\s*#slice reg\s+(\d+)',42432),('eram',r'^#eram\s+(\d+)',108),('dsp',r'^#dsp\s+(\d+)',40)]:
    used=int(re.search(pattern,a,re.M)[1]);assert used<=cap,(name,used,cap)
    resources[name]={'used':used,'capacity':cap,'remaining':cap-used}

unitp=R/'validation/latency_v12_unit/result.json';unit=js(unitp)
assert unit['pass'] and unit['cases']>=30 and unit['checks']>=158
check_hashes(unit['source_sha256']);check_hashes(unit['test_sources_sha256'])
protp=R/'validation/latency_v12_preservation/result.json';prot=js(protp)
assert prot['pass']
check_hashes(prot['source_sha256']);check_hashes(prot['baseline_source_sha256'],B)
assert prot['verifier_sha256']==sha(R/'tools/latency_v12_preservation.py')
native=[]
for sub,height in [('lead0_style1_align24_sparse1_h8_full',8),('lead0_style1_align24_sparse1_h720_full',720)]:
    p=R/f'validation/latency_v12_video/{sub}/result.json';v=js(p)
    assert v['returncode']==0 and v['completed'] and v['sources_still_current']
    params=v['parameters'];assert params['style']==1 and params['lead']==0 and params['alignment']==24 and params['height']==height
    check_hashes(v['compiled_source_sha256'])
    m={k:int(value) for k,value in v['metrics'].items()}
    assert m['packed']==m['writes']==1280*height*24//128,m
    assert m['pixels']==1280*height and m['mismatches']==0 and m['identities']==0,m
    assert m['source_full']==0 and m['output_under']==0 and m['valid_measurements']>=1 and m['timestamp_checks']>=1,m
    native.append({'report':str(p.relative_to(R)).replace('\\','/'),'sha256':sha(p),'metrics':m,
                   'scope':v['scope']})
original=js(R/'validation/baseline_v11/original_sources.json')
check_hashes(original,B)
physical_log=(P/'build_console.log').read_text(encoding='utf-8',errors='replace')
critical=list(dict.fromkeys(line.strip() for line in physical_log.splitlines() if 'CRITICAL-WARNING:' in line))
baseline_manifest=js(B/'output/build_manifest.json')
assert set(critical)==set(baseline_manifest['critical_warnings']),('review new critical warnings',critical)
utilization=list(dict.fromkeys(line.strip() for line in physical_log.splitlines() if 'PHY-7022 WARNING:' in line))
name='stylize_flame_fusion_v12_frame_latency.bit'
shutil.copy2(bit,O/name)
for p in [area,timing,P/'camera_to_dsi_display_pr.timing']:shutil.copy2(p,O/p.name)
now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
manifest={'date':now,'baseline':str(B),'bitstream':name,'bit_sha256':sha(O/name),'bit_bytes':(O/name).stat().st_size,
          'resources':resources,'timing_ns':times,'critical_warnings':critical,
          'critical_warning_contents_unchanged_v11':True,'high_utilization_warnings':utilization,
          'source_sha256':{p.relative_to(R).as_posix():sha(p) for p in (R/'user_source').rglob('*') if p.is_file()},
          'build_input_signature':{'path':'validation/build_input_signature.json','sha256':sha(R/'validation/build_input_signature.json')},
          'project_sha256':{p.relative_to(R).as_posix():sha(p) for p in [R/'td_project/camera_to_dsi_display.al',R/'td_project/camera_to_dsi_display.sdc']},
          'tests':{'unit':{'path':unitp.relative_to(R).as_posix(),'sha256':sha(unitp),'cases':unit['cases'],'checks':unit['checks']},
                   'preservation':{'path':protp.relative_to(R).as_posix(),'sha256':sha(protp)},'production_video':native},
          'observation_scope':'First valid RAW group at FPGA stream input to first active pixel at final HDMI TX input; last completed, retired frame. Excludes sensor exposure/MIPI front-end before RAW input and monitor internal response.',
          'timer_resolution_us':1,'display_resolution_ms':0.01,'display_limit_ms':1000,
          'transport_exception':{'input_alignment_camera_clocks':24,'purpose':'Preserve packed source prefix through existing SOF FIFO reset','rgb_bits_modified':False,'ddr_policy_modified':False,
             'not_claimed':'Full pixel stream or SW2 detector input is not cycle-equivalent to V11; the old discarded prefix is now restored.'},
          'original_v11_sources_unchanged':True,'programmed':False,'observed_on_board':False,
          'pending':['Actual FPGA latency readout and visual/recognition comparison on board','Power-cycle and long-run hardware acceptance'],
          'limits':['Unit timestamp tests include synchronization and quantization tolerance; do not claim nanosecond precision',
                    'Production video simulation includes actual style/packer/FIFO/video/MC and behavioral ordered DDR; not a transistor-accurate PHY or a complete camera ISP/HDMI serial simulation',
                    'Invalid or unsupported/partial/overwritten frames show hyphens rather than a guessed value',
                    'SKIP is a valid source-ID gap, not a measured physical camera error rate']}
(O/'build_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print('V12_DELIVERY_AUDIT_PASS',json.dumps({'bit':name,'sha256':manifest['bit_sha256'],'resources':resources,'timing_ns':times},ensure_ascii=False))
