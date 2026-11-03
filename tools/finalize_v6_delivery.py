"""Export only a source-matched, routed, verified V6 build. Never program hardware."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,re,shutil,subprocess,sys
sys.stdout.reconfigure(encoding='utf-8')
R=Path(__file__).resolve().parents[1];V=R/'validation';O=R/'output';P=R/'td_project/camera_to_dsi_display_Runs/phy_1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return p.read_text(encoding='utf-8')
subprocess.run([sys.executable,str(R/'tools/verify_v6_preservation.py')],check=True)
source={p.relative_to(R).as_posix():sha(p) for p in (R/'user_source').rglob('*') if p.is_file()};prefix='user_source/hdl_source/'
# Freshness is scoped to each test's actual DUT dependencies. An unrelated RAM
# edit cannot invalidate an exact colour comparison; a changed tested DUT can.
scopes={
 'verification_result.json':['fusion_controls.v','fusion_flame_pipeline.v','visual_flame_alarm.v','camera_frame_watchdog.v','alarm_board_io.v','first_aid_detector.v'],
 'extra_verification_result.json':['anlogic_logo_rom.v','hdmi_mixer.v','fusion_hud.v','fusion_menu_rom.v','fusion_telemetry.v','osd_char_lib.v'],
 'feature_verification_result.json':['isp/stylize_v5_96.v','isp/isp_top.v','image_curve_rom.v','curve_srgb.dat','curve_gain_scaled.dat','fusion_flame_pipeline.v','first_aid_detector.v','visual_flame_alarm.v','camera_frame_watchdog.v','alarm_board_io.v'],
 'color_verification_result.json':['color_luma_preserve.v','scene_color_control.v','isp/auto_black_96.v'],
 'camera_flame_verification_result.json':['awb.v','wb_gain_control.v','signal_delay.v','signal_delay_compact.v','awb_line_memory.v','visual_flame_alarm.v'],
 'display_stage_verification_result.json':['design_top_wrapper.v','color_luma_preserve.v','fusion_controls.v'],
 'v6_unit_result.json':['first_aid_detector.v','display_contrast.v'],
 'edge_preservation_result.json':['isp/stylize_v5_96.v','isp/edge_detect_96.v'],
 'visual_verification_result.json':['isp/stylize_v5_96.v'],
 'kernel_equivalence_result.json':['isp/isp_top.v','image_curve_rom.v','curve_srgb.dat','curve_gain_scaled.dat','isp/stylize_v5_96.v','color_luma_preserve.v'],
 'native_curve_model/result.json':['isp/isp_top.v','image_curve_rom.v','curve_srgb.dat','curve_gain_scaled.dat','isp/stylize_v5_96.v'],
 'native_awb_model/result.json':['awb.v','wb_gain_control.v','signal_delay.v','signal_delay_compact.v','awb_line_memory.v']}
checks={}
for filename,files in scopes.items():
 result=json.loads(read(V/filename))
 for f in files:assert result['source_sha256'][prefix+f]==source[prefix+f],('stale tested DUT',filename,f)
 assert all(t['pass'] for t in result.get('tests',{}).values()),filename
 if 'native_' in filename:assert result['native_vendor_model'],filename
 checks[filename]={'pass':True,'checked_dut_sources':files,'tests':result.get('tests',{}),'native_vendor_model':result.get('native_vendor_model',False)}
log=read(P/'build_console.log');syn=read(P.parent/'syn_1/build_console.log')
assert 'FUSION_BUILD_STAGE_PASS' in log and 'finish command "bitgen' in log,'bitgen incomplete'
assert not re.search(r'(?mi)\bERROR\s*:',log+'\n'+syn),'TD error'
roms={}
for name,n in [('curve_srgb.dat',6),('curve_gain_scaled.dat',2),('median_majority.dat',0)]:
 found=len(re.findall(r'(?m)^SYN-2541[^\r\n]*'+re.escape(name),syn));assert found==n,(name,found,n);roms[name]=found
ts=read(P/'camera_to_dsi_display_phy.ts');timing={k:float(re.search(rf'{k}:\s*([-\d.]+)ns',ts)[1]) for k in ['SWNS','STNS','HWNS','HTNS']}
assert timing['SWNS']>=0 and timing['HWNS']>=0 and timing['STNS']==timing['HTNS']==0,('timing failed',timing)
area=read(P/'camera_to_dsi_display_phy.area');resources={}
for name in ['lut6','slice','slice reg','eram','dsp']:
 m=re.search(r'^\s*#'+re.escape(name)+r'\s+(\d+)\s+out of\s+(\d+)',area,re.M);assert m,name
 n,total=map(int,m.groups());assert n<=total;resources[name]={'used':n,'total':total,'remaining':total-n}
baseline=json.loads(read(V/'v5_baseline.json'))['manifest']
assert resources['eram']['used']<baseline['resources']['eram']['used'] and resources['dsp']['used']<baseline['resources']['dsp']['used']
warnings=re.findall(r'(?m)^.*CRITICAL-WARNING:.*$',log)
assert sorted(set(warnings))==sorted(set(baseline['critical_warnings'])),('new critical warnings',warnings)
bit=P/'camera_to_dsi_display.bit';assert bit.is_file() and bit.stat().st_size>1000000
assert bit.stat().st_mtime>max((R/f).stat().st_mtime for f in source),'stale bit'
O.mkdir(exist_ok=True);dst=O/'stylize_flame_fusion_v6_visual_aid.bit';shutil.copy2(bit,dst);assert sha(dst)==sha(bit)
for f in ['camera_to_dsi_display_phy.area','camera_to_dsi_display_phy.ts','camera_to_dsi_display_pr.timing']:shutil.copy2(P/f,O/f)
result={'date':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),'bitstream':dst.relative_to(R).as_posix(),'bit_sha256':sha(dst),'bit_bytes':dst.stat().st_size,'resources':resources,'v5_resources':baseline['resources'],'timing_ns':timing,'critical_warnings':warnings,'critical_warnings_unchanged_from_v5':True,'rom_initializations':roms,'tests':checks,'source_sha256':source,'preservation':json.loads(read(V/'preservation_result.json')),'project_sha256':{p.relative_to(R).as_posix():sha(p) for p in [R/'td_project/camera_to_dsi_display.al',R/'td_project/camera_to_dsi_display.sdc']},'added_display_latency_clocks_over_v5':2,'programmed':False,'observed_on_board':False,'pending':['actual lighting: clear contrast and shadow detail','cartoon colour and edge continuity on hardware','aid false positives, loss and box geometry with actual sign','V5/V6 flame side-by-side hardware regression','long-run stability','matched-frame end-to-end latency','buffer overflow/error counters','frame difference motion detector']}
(O/'build_manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
rows='\n'.join(f"| {k} | {baseline['resources'][k]['used']} | {v['used']}/{v['total']} | {v['remaining']} |" for k,v in resources.items())
(O/'验证记录.md').write_text(f'''# V6 构建与验证记录

时间：{result['date']}。工程独立于 V5；未烧板，未做实景验收。

文件：`{dst.name}`。SHA256：`{sha(dst)}`。

| 资源 | V5 | V6 | V6 剩余 |
|---|---:|---:|---:|
{rows}

最终布线：Setup {timing['SWNS']:.3f}ns，Hold {timing['HWNS']:.3f}ns，Setup/Hold TNS 均零。既有关键时钟布线告警与 V5 相同。

已检查 {len(checks)} 组验证记录的实际被测模块哈希；逐项结果见 build_manifest.json。相机原厂模型比较 2,764,800 像素完全一致；校色与 V5 比较 1,035,306 像素完全一致；清晰/素描全宽模式切换比较 368,640 像素完全一致。清晰保留指新增显示对比度之前的像素，最终显示的亮度曲线是主动改进项，不能称 RGB 不变。

边缘使用新整数模型核对 983,040 像素，包含左右相同弱细线及两种帧首形式；卡通/素描模型与多帧自适应、完整 1280 行缓存地址均核对。急救检查多绿物体、抖动、移动、遮挡、消失、阴性场景和显示通路模式切换。火焰核心、曝光、自动色统计与检测接线保持 V5，原火焰回归通过；显示补偿在检测之后。

资源节省来自峰值通道查表、等价多数逻辑、短移位缓存、相机行缓存缩容及候选分时复用；没有减少像素数、帧率或时钟。新增全分辨率边缘、多候选急救、显示统计也消耗逻辑，不能把每类资源都说成下降。

仿真、综合、时序通过不等于实景效果已改善。需烧录后对照同一场景、相同按键和光线验证，尤其火焰识别、弱细线、暗部层次和实际急救包。
''',encoding='utf-8')
print('V6_DELIVERY_READY',json.dumps({k:result[k] for k in ['bitstream','bit_sha256','resources','timing_ns','programmed']},ensure_ascii=False))
