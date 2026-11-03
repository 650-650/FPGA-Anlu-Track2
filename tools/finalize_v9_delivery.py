"""Require source-matched visual tests, protected V8 and real routed timing."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,re,shutil,subprocess,sys
sys.stdout.reconfigure(encoding='utf-8')
R=Path(__file__).resolve().parents[1];V=R/'validation';O=R/'output';H=R/'user_source/hdl_source';P=R/'td_project/camera_to_dsi_display_Runs/phy_1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return p.read_text(encoding='utf-8')
subprocess.run([sys.executable,str(R/'tools/verify_v9_preservation.py')],check=True)
source={p.relative_to(R).as_posix():sha(p) for p in (R/'user_source').rglob('*') if p.is_file()}
prefix='user_source/hdl_source/'
scopes={'verification_result.json':['fusion_controls.v','fusion_flame_pipeline.v','visual_flame_alarm.v','first_aid_detector.v','camera_frame_watchdog.v','alarm_board_io.v'],
 'extra_verification_result.json':['anlogic_logo_rom.v','hdmi_mixer.v','fusion_hud.v','fusion_menu_rom.v','fusion_telemetry.v','osd_char_lib.v'],
 'feature_verification_result.json':['isp/isp_top.v','image_curve_rom.v','first_aid_detector.v','fusion_flame_pipeline.v'],
 'display_v9/result.json':None,'display_v9/quality_result.json':None,'cartoon_finish_v9/result.json':None,
 'cartoon_v9/result.json':None,'cartoon_v9/quality_result.json':None,'cartoon_v9/area_equivalence/result.json':None,
 'cartoon_v9/fold_equivalence/result.json':None,'display_v9_integration/result.json':None}
results={}
for filename,paths in scopes.items():
 a=json.loads(read(V/filename));hashes=a['source_sha256'];requested=list(hashes) if paths is None else [prefix+p for p in paths]
 for f in requested:assert sha(R/f)==hashes[f].lower(),('stale DUT',filename,f)
 for f,d in a.get('oracle_sha256',{}).items():assert sha(R/f)==d,('stale oracle',filename,f)
 if filename!='display_v9/quality_result.json':
  assert a.get('tests') or a.get('pass'),('empty tests',filename)
  assert all(t['pass'] for t in a.get('tests',{}).values()),('test failed',filename)
 if 'pass' in a:assert a['pass'],filename
 if filename in ['display_v9/result.json','cartoon_finish_v9/result.json']:assert a['native_vendor_model'],filename
 results[filename]={'pass':True,'tests':a.get('tests',{}),'scope':a.get('scope'),'verified_source_paths':requested,'native_vendor_model':a.get('native_vendor_model',False)}
log=read(P/'build_console.log');syn=read(P.parent/'syn_1/build_console.log')
assert 'FUSION_BUILD_STAGE_PASS' in log and 'finish command "bitgen' in log,'build incomplete'
assert not re.search(r'(?mi)\bERROR\s*:',log+'\n'+syn),'TD error'
ts=read(P/'camera_to_dsi_display_phy.ts');timing={k:float(re.search(rf'{k}:\s*([-\d.]+)ns',ts)[1]) for k in ['SWNS','STNS','HWNS','HTNS']}
assert timing['SWNS']>=0 and timing['HWNS']>=0 and timing['STNS']==timing['HTNS']==0,('final routed timing failed',timing)
area=read(P/'camera_to_dsi_display_phy.area');resources={}
for key in ['lut6','slice','slice reg','eram','dsp']:
 m=re.search(r'^\s*#'+re.escape(key)+r'\s+(\d+)\s+out of\s+(\d+)',area,re.M);assert m,key
 used,total=map(int,m.groups());assert used<=total;resources[key]={'used':used,'total':total,'remaining':total-used}
assert resources['dsp']['used']==32,'unexpected DSP mapping'
baseline=json.loads(read(V/'v8_baseline.json'))['manifest'];warnings=re.findall(r'(?m)^.*CRITICAL-WARNING:.*$',log)
assert sorted(set(warnings))==sorted(set(baseline['critical_warnings'])),('new critical clock warning',warnings)
roms={}
for name,count in [('curve_srgb.dat',6),('curve_gain_scaled.dat',2),('median_majority.dat',0),('display_tone.dat',1)]:
 actual=len(re.findall(r'(?m)^SYN-2541[^\r\n]*'+re.escape(name),syn));assert actual==count,(name,actual,count);roms[name]=actual
bit=P/'camera_to_dsi_display.bit';assert bit.is_file() and bit.stat().st_size>1000000
assert bit.stat().st_mtime>max((R/f).stat().st_mtime for f in source),'bit older than production source'
O.mkdir(exist_ok=True);dst=O/'stylize_flame_fusion_v9_detail_motion.bit';shutil.copy2(bit,dst);assert sha(bit)==sha(dst)
for filename in ['camera_to_dsi_display_phy.area','camera_to_dsi_display_phy.ts','camera_to_dsi_display_pr.timing']:shutil.copy2(P/filename,O/filename)
integration=json.loads(read(V/'display_v9_integration/result.json'))['tests']['actual_top_against_v8']
cartoon=json.loads(read(V/'cartoon_v9/quality_result.json'));clear=json.loads(read(V/'display_v9/quality_result.json'))
manifest={'date':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),'bitstream':dst.relative_to(R).as_posix(),'bit_sha256':sha(dst),'bit_bytes':dst.stat().st_size,
 'resources':resources,'v8_resources':baseline['resources'],'timing_ns':timing,'critical_warnings':warnings,'critical_warning_contents_unchanged_v8':True,
 'high_utilization_warnings':sorted(set(re.findall(r'(?m)^PHY-7022[^\r\n]*',log))),
 'rom_initializations':roms,'source_sha256':source,'tests':results,'preservation':json.loads(read(V/'v9_preservation_result.json')),
 'test_sources_sha256':{p.relative_to(R).as_posix():sha(p) for d in [R/'tools',V] for p in d.rglob('*') if p.is_file() and p.suffix in ['.py','.v'] and 'work' not in p.parts},
 'top_registered_stages':integration['top_registered_stages'],'added_display_clocks_from_v8':integration['added_display_clocks_v8'],
 'camera_exposure_detection_controls_unchanged':True,'sketch_edge_mode_pixels_exact_v8':True,'programmed':False,'observed_on_board':False,
 'limits':['clear small cross trades some correlated-noise suppression and some periodic detail against much less wide-radius blur',
 'cartoon weak-noise transition can increase STD below accepted0.2 RGB codes','all physical motion shadows not proven solely caused by spatial filtering',
 'no sensor exposure, panel response, DDR or compression motion effects claimed fixed','bright-light flame/reflection classifier intentionally unchanged'],
 'pending':['same-scene near/far clarity and night-noise board A/B','moving-camera black-shadow board comparison','physical SW2 regression','power-cycle and long-run stability']}
(O/'build_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
rows='\n'.join(f"| {k} | {baseline['resources'][k]['used']} | {v['used']}/{v['total']} | {v['remaining']} |" for k,v in resources.items())
readme=f'''# V9 远景细节与运动暗边修正版

完成：{manifest['date']}。这是通过最终时序的V9紧凑布局版，独立保留 V8，未烧板，未声称实拍黑影全部解决。另一个普通V9布局虽产生文件但最终时序失败，不能作为成品。

bit：`{dst.name}`；SHA256：`{sha(dst)}`。

## 修改及原因

读取了用户2026-10-30的两段视频和五张图。第一段是清晰，第二段卡通；照片1/2卡通，3清晰，4素描，5边缘。原文件备份、哈希、抽帧和运动片段检查在同级 `v9_analysis/`，不是将拍屏压缩像素当原始传感器数据。

V8单侧STRIDE4邻点会磨掉细微纹理：合成周期8低对比纹理只保留约26%波动，带0～2级微纹理的32级边界可产生约4像素范围的暗晕。V9清晰显示改用上下左右一像素的对称小邻域、RGB相似门控、最大6级修正；不跨帧混合。代表性周期8纹理保留约93%，同类边界暗差约从−8减到−1。它不是“所有频率都改善”：周期4、极弱细线仍可能受损，相关块噪声抑制也弱于V8，详细反例和全部数字保存在 `validation/display_v9/quality_result.json`。这是优先修远景细纹与宽暗边的明确取舍，不能承诺所有噪声和所有细节同时无损。

卡通单独处理：在原W3窗口新增按RGB筛选的高斯平滑、容差细彩线保护、共同亮度的小幅连续色阶，保留颜色差；最低/最高亮度段锚定，减少黑白端噪声反弹。轮廓按强度减亮1/8～3/8，删除原先亮度达到96后直接置纯黑的跳变。卡通仍保留独立的跨块后置降噪，但修正限幅由12收至6，只服务卡通。这样清晰与卡通不会互相套用不合适的滤波。

卡通完整生产路线（包含后置滤波）1024组全灰阶、IID/2×2/3×3/4×4相关噪声、每组8帧±20噪声的模型对比均改善；192组较弱噪声中，连续色阶过渡仍可能增加小于0.15RGB码的STD，未宣称任意噪声都降低。弱细彩线可能有约9～15%额外软化，不能将保护机制说成每个像素都不改。卡通目标是更平滑的色块与柔和轮廓，颜色学习、曝光和白平衡没有另外添加。

## 明确保留

素描、边缘共享guide源文件未改；style中mode0/2/3共92160像素与V8真实guide逐值相同，所有模式仍16拍、帧锁存相同。火焰/跟踪/急救/报警、所有按键、原清晰曲线、曝光/白平衡/去灰、引脚/时钟约束、菜单/Logo均沿用V8。火焰强光漏检与反光误检本轮没有改阈值，保留目前已认可的识别表现。

实际顶层连接对照：256000有效检测输入同拍相同，报警/目标/坐标/LED/蜂鸣状态同拍相同；素描/边缘47240像素及SW2/SW3的118100像素对齐后相同，Logo文字19800像素原值保留。混合器输出至HDMI送入这一显示段为{integration['top_registered_stages']}个寄存级，比V8增加{integration['added_display_clocks_v8']}像素钟（约{integration['added_display_clocks_v8']/75:.2f}微秒）。RGB/VS/HS/DE和控制、叠字有效信息统一延迟，不是帧混合；检测输入/判定时间未增加。这不是相机到屏幕的完整端到端延迟测量。

## 编译与验证

| 资源 | V8 | V9 | 剩余 |
|---|---:|---:|---:|
{rows}

最终布线 Setup WNS {timing['SWNS']:.3f}ns、Hold WNS {timing['HWNS']:.3f}ns，TNS均0；原3条关键时钟布线告警内容集合相同。未提高时钟、未放宽约束。本版有高占用告警，逻辑与ERAM余量较紧，后续加功能要先做预算和共用运算，不能直接无限叠模块。初版卡通资源超限曾被正式构建拒绝；没有将失败构建作为成品，诊断在 `validation/build_attempt_1/`。后续将多次绝对值/最大值改为共享的单向9bit差和常数范围判定，346608个窗口逐位等值、真实全流水重验通过；质量模型数值通过此等值证据续接，未冒称在板上测得。

显示新行缓存：40960拍小场景、1237500拍1280×720整帧与独立模型逐36位核对，原厂ERAM模型再验完整1237500拍；覆盖启动、边界、空白区、模式变化、叠字和帧切换。卡通后处理另有全帧与原厂RAM逐值对照。卡通真实RTL735360像素和独立模型相同，包括移动细彩线、模式切换、全1280行宽。紧凑布局把864位邻点寄存改为360位完整精度行和，另经360960像素四模式/全宽对照逐值等效，保持16拍及最终统一截断，没有减少计算精度。火焰全宽、跟踪、报警控制、急救、Logo、HUD、原清晰曲线回归通过。`output/build_manifest.json`绑定生产源、模型、测试和bit哈希，导出脚本拒绝过期测试、资源超限及负最终WNS。

## 实板检查

保持同一机位、焦距与灯光，先用SW1 K1看远处文字、栏杆、布料；再缓慢和快速左右移动看暗边；然后K2看蓝/棕/肤色与大色块，最后确认K3素描、K4边缘及SW2。全下的基础清晰也使用新小邻域滤波；全部按键与V8一致，SW4仍独立控制Logo和文字。

从视频与代码还不能证明全部运动黑影都由此滤波造成：传感器曝光、显示器响应和拍屏过程不在RTL模拟中。本版针对已复现的空间暗晕和纯黑描线做修正，最终实景是否解决需要烧录后对比。夜间相关块噪声可能比V8更明显，若发生，应保留反馈与V8同场景比较，不能为了掩盖它牺牲清晰度或改坏SW2。

V8回退文件：`../07_stylize_flame_fusion_v8_visual_denoise/output/stylize_flame_fusion_v8_visual_denoise.bit`，原220源文件与bit已核对未改。

参考[OpenCV官方保边滤波说明](https://docs.opencv.org/4.11.0/d4/d13/tutorial_py_filtering.html)和[Guided Image Filtering作者页面](https://people.csail.mit.edu/kaiming/eccv10/index.html)核对边缘与平滑的取舍；本版是自己的定点小邻域方案，没有声称移植完整guided filter或照搬外部板级代码。

重建：从本工程目录运行 `build.ps1`；交付审计 `tools/finalize_v9_delivery.py`。状态与延续入口 `V9_WORKING_STATUS.md`。
'''
(R/'README.md').write_text(readme,encoding='utf-8');(O/'验证记录.md').write_text(readme,encoding='utf-8')
print('V9_DELIVERY_READY',json.dumps({k:manifest[k] for k in ['bitstream','bit_sha256','resources','timing_ns','programmed']},ensure_ascii=False))
