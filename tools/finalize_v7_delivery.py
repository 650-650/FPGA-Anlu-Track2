"""Publish a source-matched V7 only after real routed timing and targeted tests."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,re,shutil,subprocess,sys
sys.stdout.reconfigure(encoding='utf-8')
R=Path(__file__).resolve().parents[1];V=R/'validation';O=R/'output';P=R/'td_project/camera_to_dsi_display_Runs/phy_1';H=R/'user_source/hdl_source'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return p.read_text(encoding='utf-8')
subprocess.run([sys.executable,str(R/'tools/verify_v7_preservation.py')],check=True)
source={p.relative_to(R).as_posix():sha(p) for p in (R/'user_source').rglob('*') if p.is_file()}
prefix='user_source/hdl_source/'
scopes={
 'verification_result.json':['fusion_controls.v','fusion_flame_pipeline.v','visual_flame_alarm.v','first_aid_detector.v','camera_frame_watchdog.v','alarm_board_io.v'],
 'extra_verification_result.json':['anlogic_logo_rom.v','hdmi_mixer.v','fusion_hud.v','fusion_menu_rom.v','fusion_telemetry.v','osd_char_lib.v'],
 'display_v7/result.json':None,'display_v7_native/result.json':None,'alarm_v7/result.json':None,
 'edge_v7/result.json':None,'edge_v7/temporal/result.json':None,'cartoon_v7/result.json':None,'cartoon_v7/quality_result.json':None,
 'native_curve_model/result.json':['isp/isp_top.v','image_curve_rom.v','curve_srgb.dat','curve_gain_scaled.dat','isp/stylize_v5_96.v']}
results={}
for filename,files in scopes.items():
 a=json.loads(read(V/filename));hashes=a['source_sha256']
 if isinstance(hashes,str):hashes={prefix+'isp/stylize_v5_96.v':hashes.lower()}
 if files is None:files=list(hashes)
 else:files=[prefix+s for s in files]
 for f in files:assert hashes[f].lower()==source[f],('stale DUT verification',filename,f)
 for f,s in a.get('oracle_sha256',{}).items():assert sha(R/f)==s,('stale oracle',filename,f)
 assert all(t['pass'] for t in a.get('tests',{}).values()),('failed test',filename)
 if filename.startswith('native_') or filename=='display_v7_native/result.json':assert a['native_vendor_model'],filename
 assert a.get('tests') or a.get('native_vendor_model'),('empty result',filename)
 results[filename]={'pass':True,'verified_dut_sources':files,'tests':a.get('tests',{}),'scope':a.get('scope'),
  'native_vendor_model':a.get('native_vendor_model',False)}
contours=json.loads(read(V/'edge_v7/noisy_contour_metrics.json'))
log=read(P/'build_console.log');syn=read(P.parent/'syn_1/build_console.log')
assert 'FUSION_BUILD_STAGE_PASS' in log and 'finish command "bitgen' in log,'incomplete build'
assert not re.search(r'(?mi)\bERROR\s*:',log+'\n'+syn),'TD error'
roms={}
for name,n in [('curve_srgb.dat',6),('curve_gain_scaled.dat',2),('median_majority.dat',0),('display_tone.dat',1)]:
 count=len(re.findall(r'(?m)^SYN-2541[^\r\n]*'+re.escape(name),syn));assert count==n,(name,count,n);roms[name]=count
ts=read(P/'camera_to_dsi_display_phy.ts');timing={k:float(re.search(rf'{k}:\s*([-\d.]+)ns',ts)[1]) for k in ['SWNS','STNS','HWNS','HTNS']}
assert timing['SWNS']>=0 and timing['HWNS']>=0 and timing['STNS']==timing['HTNS']==0,('routed timing failed',timing)
resources={};area=read(P/'camera_to_dsi_display_phy.area')
for key in ['lut6','slice','slice reg','eram','dsp']:
 m=re.search(r'^\s*#'+re.escape(key)+r'\s+(\d+)\s+out of\s+(\d+)',area,re.M);assert m,key
 used,total=map(int,m.groups());assert used<=total;resources[key]={'used':used,'total':total,'remaining':total-used}
assert resources['dsp']['used']<=36,'unexpected DSP mapping'
baseline=json.loads(read(V/'v6_baseline.json'))['manifest'];warnings=re.findall(r'(?m)^.*CRITICAL-WARNING:.*$',log)
assert sorted(set(warnings))==sorted(set(baseline['critical_warnings'])),('new critical warning',warnings)
bit=P/'camera_to_dsi_display.bit';assert bit.is_file() and bit.stat().st_size>1000000
assert bit.stat().st_mtime>max((R/f).stat().st_mtime for f in source),'stale bitstream'
O.mkdir(exist_ok=True);dst=O/'stylize_flame_fusion_v7_shadow_clean.bit';shutil.copy2(bit,dst);assert sha(dst)==sha(bit)
for name in ['camera_to_dsi_display_phy.area','camera_to_dsi_display_phy.ts','camera_to_dsi_display_pr.timing']:shutil.copy2(P/name,O/name)
test_sources={p.relative_to(R).as_posix():sha(p) for parent in [R/'tools',V] for p in parent.rglob('*') if p.is_file() and p.suffix in ['.py','.v'] and 'work' not in p.parts}
result={'date':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),'bitstream':dst.relative_to(R).as_posix(),'bit_sha256':sha(dst),
 'bit_bytes':dst.stat().st_size,'resources':resources,'v6_resources':baseline['resources'],'timing_ns':timing,
 'critical_warnings':warnings,'critical_warning_contents_unchanged_v6':True,'rom_initializations':roms,'tests':results,
 'edge_noisy_contour_metrics':contours,
 'source_sha256':source,'test_sources_sha256':test_sources,'preservation':json.loads(read(V/'v7_preservation_result.json')),
 'project_sha256':{p.relative_to(R).as_posix():sha(p) for p in [R/'td_project/camera_to_dsi_display.al',R/'td_project/camera_to_dsi_display.sdc']},
 'inherited_v6_evidence':{'scope':'Unmodified protected camera/colour/recognition sources; not represented as fresh V7 simulation.',
  'native_camera_transport':baseline['tests']['native_awb_model/result.json'],
  'colour_integer_luma_and_v5_equivalence':baseline['tests']['kernel_equivalence_result.json']},
 'programmed':False,'observed_on_board':False,'display_latency_unchanged_from_v6':True,
 'sketch_visual_algorithm_unchanged':True,'classification_thresholds_unchanged':True,
 'pending':['actual scene day/night clarity and colour comparison','residual sketch noise intentionally not retuned','very weak contours in strong noise can become discontinuous','first-entry buzzer silence not reproduced; no speculative alarm change','real flame and aid regression','long-run stability','matched-frame latency','buffer error counters','frame difference motion']}
(O/'build_manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
rows='\n'.join(f"| {k} | {baseline['resources'][k]['used']} | {v['used']}/{v['total']} | {v['remaining']} |" for k,v in resources.items())
(O/'验证记录.md').write_text(f'''# V7 构建与验证记录

完成时间：{result['date']}。本轮未烧录，未声称实景改善已验收。原 V6 保留。

bit：`{dst.name}`，SHA256：`{sha(dst)}`。

| 资源 | V6 | V7 | 剩余 |
|---|---:|---:|---:|
{rows}

最终布线 Setup WNS {timing['SWNS']:.3f}ns、Hold WNS {timing['HWNS']:.3f}ns、TNS 均零。原有关键时钟布线告警内容集合相同。

## 新鲜验证与保护

最终源对应 {len(results)} 组验证记录，逐一核对被测模块哈希。火焰/急救/报警/控制、传感器、曝光、原去灰、清晰曲线及检测校色不改。实际顶层抽取并行对照 V6，24,543 有效样本的实际检测输入相同；4,905 个叠字像素精确保留，6,546 个风格输入像素不再二次校色/明暗处理，RGB/同步仍为 6 个像素时钟。

夜间/日间显示 2,426,811 样本，含所有灰阶、4096 随机彩色输入，黑白端点、单亮/暗区域抗扰、白天灰雾变化、卡通/素描/边缘/叠字旁路及两拍同步验证通过。原厂新曲线 ROM 2048 地址、4096 读与独立数学模型完全一致。

卡通模型、64 帧自适应与全 1280 行宽比较 516,096 像素；清晰/素描/外部边缘旁路比较 368,640 像素与 V6 相同。暗蓝、棕、绿不再被误学成灰；三组干净轮廓夹具保留全部 V6 轮廓。暗部残余梯度没有冒称全部去除，改为有颜色的弱轮廓；明亮平面噪声轮廓减少。素描视觉算法保持，仅 4 个等值乘法改用 DSP，未称素描噪点已经根治。

新边缘 4,300,800 像素与独立模型一致，含随机空拍、帧首、全宽与多种噪声。带噪线条测试必须按源坐标对齐：V6 回看 1 行/像素、V7 回看 2 行/像素；共同内部区域中，32/64 级线在标准差 4/8 噪声下可见率 99.31%～100%。16 级弱线叠加标准差 8 噪声仍会断续，不作所有线无损的承诺。详细数据见 validation/edge_v7/noisy_contour_metrics.json。

时变噪声另用每帧独立采样的标准差 4/8 噪声各 12 帧，与实际 V6/V7 RTL 逐帧核对：两侧各 737,280 像素及门限轨迹相同于各自独立模型。冷启动 12 帧平均，背景白点从 21.73%/38.35% 降至 4.86%/18.23%，背景翻转率从 34.03%/46.94% 降至 8.61%/28.31%；该夹具32/64级四方向轮廓始终可见。标准差8时门限仍在收敛，不能称稳态，也不是实景噪声测量。

首次声光联动未复现永久无声：真实按键/CDC/分类/确认序列 14 检查、55,338 样本、8,603 蜂鸣低电平样本通过。黄候选框与红确认框不是同一状态；实体 SW5/SW6、驱动和声音不在 RTL 仿真中。保留报警逻辑，不将未定位的问题列为已修复。

参考 OpenCV 官方滤波/梯度说明及公开 FPGA 作者项目，取处理思路，没有复制第三方板级接口或认定其效果适用于本板。完整参考在 README 与 validation/alarm_v7/research_sources.md。
''',encoding='utf-8')
print('V7_DELIVERY_READY',json.dumps({k:result[k] for k in ['bitstream','bit_sha256','timing_ns','resources','programmed']},ensure_ascii=False))
