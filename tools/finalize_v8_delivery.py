"""Publish only source-matched tests plus a fully routed timing-clean V8 bit."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,re,shutil,subprocess,sys
sys.stdout.reconfigure(encoding='utf-8')
R=Path(__file__).resolve().parents[1];V=R/'validation';H=R/'user_source/hdl_source';O=R/'output'
P=R/'td_project/camera_to_dsi_display_Runs/phy_1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return p.read_text(encoding='utf-8')
subprocess.run([sys.executable,str(R/'tools/verify_v8_preservation.py')],check=True)
source={p.relative_to(R).as_posix():sha(p) for p in (R/'user_source').rglob('*') if p.is_file()}
prefix='user_source/hdl_source/'
scopes={
 'verification_result.json':['fusion_controls.v','fusion_flame_pipeline.v','visual_flame_alarm.v','first_aid_detector.v','camera_frame_watchdog.v','alarm_board_io.v'],
 'extra_verification_result.json':['anlogic_logo_rom.v','hdmi_mixer.v','fusion_hud.v','fusion_menu_rom.v','fusion_telemetry.v','osd_char_lib.v'],
 'feature_verification_result.json':['isp/isp_top.v','image_curve_rom.v','first_aid_detector.v','fusion_flame_pipeline.v'],
 'native_curve_model/result.json':['isp/isp_top.v','image_curve_rom.v','curve_srgb.dat','curve_gain_scaled.dat','isp/stylize_v5_96.v'],
 'alarm_v7/result.json':None,'cartoon_v8/result.json':None,'cartoon_v8/quality_result.json':None,
 'cartoon_v8/clear_result.json':None,'guide_v8/result.json':None,'denoise_v8/result.json':None,
 'denoise_v8/quality_result.json':None,'tone_v8/result.json':None,'display_v8_integration/result.json':None}
results={}
for filename,files in scopes.items():
 a=json.loads(read(V/filename));hashes=a['source_sha256']
 if isinstance(hashes,str):hashes={prefix+'isp/stylize_v5_96.v':hashes.lower()}
 requested=list(hashes) if files is None else [prefix+f for f in files]
 for f in requested:assert sha(R/f)==hashes[f].lower(),('stale DUT',filename,f)
 for f,d in a.get('oracle_sha256',{}).items():assert sha(R/f)==d,('stale oracle',filename,f)
 if 'guide_model_sha256' in a:assert sha(R/'tools/guide_v8_model.py')==a['guide_model_sha256'],filename
 assert a.get('tests') or a.get('pass') or a.get('native_vendor_model'),('empty validation',filename)
 assert all(t['pass'] for t in a.get('tests',{}).values()),('failed test',filename)
 if 'pass' in a:assert a['pass'],filename
 if filename in ['native_curve_model/result.json','denoise_v8/result.json','tone_v8/result.json']:assert a['native_vendor_model'],filename
 results[filename]={'pass':True,'verified_source_paths':requested,'tests':a.get('tests',{}),'scope':a.get('scope'),
  'native_vendor_model':a.get('native_vendor_model',False)}
log=read(P/'build_console.log');syn=read(P.parent/'syn_1/build_console.log')
assert 'FUSION_BUILD_STAGE_PASS' in log and 'finish command "bitgen' in log,'incomplete build'
assert not re.search(r'(?mi)\bERROR\s*:',log+'\n'+syn),'TD error'
ts=read(P/'camera_to_dsi_display_phy.ts')
timing={k:float(re.search(rf'{k}:\s*([-\d.]+)ns',ts)[1]) for k in ['SWNS','STNS','HWNS','HTNS']}
assert timing['SWNS']>=0 and timing['HWNS']>=0 and timing['STNS']==timing['HTNS']==0,('routed timing failed',timing)
resources={};area=read(P/'camera_to_dsi_display_phy.area')
for key in ['lut6','slice','slice reg','eram','dsp']:
 m=re.search(r'^\s*#'+re.escape(key)+r'\s+(\d+)\s+out of\s+(\d+)',area,re.M);assert m,key
 used,total=map(int,m.groups());assert used<=total;resources[key]={'used':used,'total':total,'remaining':total-used}
assert resources['dsp']['used']==32,'DSP use changed unexpectedly'
roms={}
for name,n in [('curve_srgb.dat',6),('curve_gain_scaled.dat',2),('median_majority.dat',0),('display_tone.dat',1)]:
 count=len(re.findall(r'(?m)^SYN-2541[^\r\n]*'+re.escape(name),syn));assert count==n,(name,count,n);roms[name]=count
baseline=json.loads(read(V/'v7_baseline.json'))['manifest']
warnings=re.findall(r'(?m)^.*CRITICAL-WARNING:.*$',log)
assert sorted(set(warnings))==sorted(set(baseline['critical_warnings'])),('new critical clock warning requires review',warnings)
bit=P/'camera_to_dsi_display.bit';assert bit.is_file() and bit.stat().st_size>1000000
assert bit.stat().st_mtime>max((R/f).stat().st_mtime for f in source),'bit older than source'
O.mkdir(exist_ok=True);dst=O/'stylize_flame_fusion_v8_visual_denoise.bit';shutil.copy2(bit,dst);assert sha(dst)==sha(bit)
for name in ['camera_to_dsi_display_phy.area','camera_to_dsi_display_phy.ts','camera_to_dsi_display_pr.timing']:shutil.copy2(P/name,O/name)
quality=json.loads(read(V/'denoise_v8/quality_result.json'));guide=json.loads(read(V/'guide_v8/result.json'))
manifest={'date':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),'bitstream':dst.relative_to(R).as_posix(),'bit_sha256':sha(dst),
 'bit_bytes':dst.stat().st_size,'resources':resources,'v7_resources':baseline['resources'],'timing_ns':timing,
 'critical_warnings':warnings,'critical_warning_contents_unchanged_v7':True,'rom_initializations':roms,'tests':results,
 'source_sha256':source,'test_sources_sha256':{p.relative_to(R).as_posix():sha(p) for parent in [R/'tools',V] for p in parent.rglob('*') if p.is_file() and p.suffix in ['.py','.v'] and 'work' not in p.parts},
 'project_sha256':{p.relative_to(R).as_posix():sha(p) for p in [R/'td_project/camera_to_dsi_display.al',R/'td_project/camera_to_dsi_display.sdc']},
 'preservation':json.loads(read(V/'v8_preservation_result.json')),'display_latency_pixel_clocks':10,'added_display_clocks_from_v7':4,
 'detector_input_clock_latency_unchanged':True,'resolution_unchanged':[1280,720],
 'classification_camera_exposure_controls_alarm_unchanged':True,'programmed':False,'observed_on_board':False,
 'pending':['same scene real day/night clarity, haze and colour regression','real flame/aid/alarm regression on physical board',
 'very weak noisy texture versus detail tradeoff','power-cycle and long-run stability','end-to-end matched-frame latency remains unimplemented']}
(O/'build_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
rows='\n'.join(f"| {k} | {baseline['resources'][k]['used']} | {v['used']}/{v['total']} | {v['remaining']} |" for k,v in resources.items())
readme=f'''# V8 视觉去噪版

完成时间：{manifest['date']}。基于用户刚测过的 V7，独立工程，原 V7 源码及 bit 全部保留。**已完成软件验证和整机编译，尚未烧板，实景改善待实板对比。**

成品：[{dst.name}](output/{dst.name})。SHA256：`{sha(dst)}`。

## 本版具体改动

基础清晰与 SW1 清晰：保留原 1280×720、原 ISP 清晰曲线、曝光、原去灰和白平衡源；在检测之后添加限幅、按 RGB 相似程度筛选邻点的显示滤波。当前像素位置不移动，强颜色边界和规则细线受保护，Logo、文字、检测框旁路。不能把“分辨率与原清晰链不变”解释成所有细微纹理绝无变化。

夜间不再把整片低灰底一起抬高。降低最低灰阶，分开提中间调；0 与 255 固定，所有曲线单调，白天原曲线保留。例：最暗等级、无额外偏移时，Y20 从 V7 的30变为19，Y96为104、Y128为132；这有助于去灰并保留中间调，不能从数学上保证任意真实场景既完全去雾又完全无暗部取舍。

卡通：去掉内部第二套自学习去色、灰度分档与饱和度增益，改为保留已平滑的真实 RGB，再叠加可信轮廓；沿用唯一一次原显示校色。深蓝、棕色、肤色不再因旧的分档/中性色拟合被主动置灰。风格是保色平滑加描线，色阶会比 V7 连续；传感器本身没有采到的暗色无法凭空恢复。

素描、边缘：复用同一套细/粗两尺度窗口，综合方向、线条连通、法向峰值与两尺度一致性抑制孤点和相关块噪声；素描用固定局部墨线强度，远处亮物/纹理不再把本地弱线压掉。边缘仍是黑底白线，素描仍是白纸黑线。强相关噪声仍可能留下纹理，未宣称噪声全部根除。

## SW2 保护与操作

按键、开关方向均沿用 V7：SW1 下 K1清晰/K2卡通/K3素描/K4边缘；SW2 下 K1火焰/K2跟踪/K3声光联动与静音/K4绿底白十字急救；SW3状态页；SW4独立开关 Logo 与文字。全下基础页面的色调短按键、K3长按复位、K4长按校色不变。SW5/SW6板级功能照旧。

火焰、跟踪、急救、报警及按键核心逐字节相同；检测输入的原 ISP mode0 旁路、检测校色、曝光、统计取样与引脚/时钟约束保持。新滤波在检测核心之后，SW2/SW3滤波旁路且使用逐值相同的旧曲线。实际顶层抽取与 V7 并行对照：256000有效像素的检测输入同拍相同，目标/报警/坐标/候选数/LED/蜂鸣状态同拍相同；SW2/SW3最终 RGB 对齐4拍后，118100样本完全相同。Logo文字19800样本精确保留。

最终显示段延迟从6拍变为10拍，增加4个75MHz像素时钟，约53纳秒；RGB/DE/HS/VS一起延迟，不增加一帧缓存或移动当前像素坐标。传感器/DDR/PHY与实体声音不属于该顶层片段仿真范围。

## 编译结果

| 资源 | V7 | V8 | 剩余 |
|---|---:|---:|---:|
{rows}

最终布线 Setup WNS **{timing['SWNS']:.3f}ns**，Hold WNS **{timing['HWNS']:.3f}ns**，Setup/Hold TNS 均为0。已有3种关键时钟布线告警内容集合与 V7相同。移除了独立边缘运算和旧风格自学习/分档逻辑，换取共用窗口与显示降噪；没有提高时钟或放宽时序约束。

## 验证证据

- 显示滤波：小帧与1280×720全帧共1247740时钟逐值对照独立模型，原厂 ERAM 模型另验110000时钟；覆盖同步、真实行消隐、叠字、模式切换和检测/状态旁路。四拍流水化与先前公式的像素结果相同。
- 明暗曲线：1053959样本与独立数学模型对照；原厂 ROM 覆盖4096地址、8192次读；411216 legacy样本与 V7精确相同。
- 联合去噪与夜间曲线：168组独立/2×2/3×3/4×4相关噪声、不同亮度/强度的固定暗等级模型夹具，输出噪声标准差均低于V7；最弱改善的比值为 {quality['tests']['joint_night_noise']['worst_std_ratio']:.4f}。25组已知细线/阶跃和低色差边界逐值保留，有限孤立脉冲降低。此数值只代表夹具，不能当实拍降噪比例。
- 风格：自然图/暗场/全1280行宽、三模式及18帧颜色噪声，共800640有效像素与独立模型相同；原清晰mode0的245760像素与V7逐值相同，所有模式同步与锁存时机相同。8组自然图模型确认非描线填色等于真实B2 RGB；弱线不随远处纹理消失。
- 局部轮廓：{guide['exact_windows']}窗口与RTL相同；含逐帧新噪声、相关块噪声、Bayer相位差及8/12/17/32/64级四方向细线。保留局部线，减少背景墨点；高噪声下仍有残余，记录未隐藏。
- 原清晰曲线：200268样本、全部表项/随机RGB/复位/空拍，Icarus和原厂RAM模型均通过。火焰全分辨率、跟踪、首次声光联动、绿底白十字急救、控制CDC、Logo/HUD回归通过；不是一次完整的相机至实体HDMI硬件仿真。
- `validation/v8_preservation_result.json` 核对原V7的218源文件及bit未改；本版仅6个既有源文件有变动、增加2个源文件，具体路径和验证源哈希均在记录中。

第一次三拍滤波原型在时序检查时未达标，已停止构建，没有作为成品交付；依据实际关键路径拆为四拍并改用等值并行判定、平衡求和树，之后重跑全部受影响验证。旧诊断保存在 `validation/build_attempt_1/`。

## 实板对比顺序

用同一夜间场景、同一机位与灯光先看基础清晰；再用SW1 K1/K2/K3/K4观察深蓝/棕色/皮肤、弱线和墙面噪点。比较自动色调时统一从复位进入，不要一版手动偏冷一档、一版自动；第一段V7视频HUD显示的是手动C1档。拍屏反光与手机曝光会影响灰雾观感，边缘本身只有黑白输出。最后复核SW2的火焰、跟踪、声光与急救。未替用户执行烧录，未把模型图当板上效果图。

回退路径：`{R.with_name('07_stylize_flame_fusion_v7_shadow_clean').as_posix()}/output/stylize_flame_fusion_v7_shadow_clean.bit`。

## 参考及复现

参考[OpenCV官方滤波说明](https://docs.opencv.org/4.11.0/d4/d13/tutorial_py_filtering.html)、[MathWorks官方HDL卡通与保边滤波示例](https://www.mathworks.com/help/visionhdl/ug/generate-cartoon-images-using-bilateral-filtering.html)、[AMD mini-isp作者工程](https://github.com/amd/mini-isp)。取保边、局部平滑与轮廓叠加思路，没有复制第三方相机接口、板级工程或套用他板参数，也没有声称本实现是完整高斯双边滤波。

从本工程目录执行 `build.ps1` 重建；生成菜单/曲线或移动工程后先运行 `tools/prepare_project.py` 修正工程内部路径。最终交付审计使用 `tools/finalize_v8_delivery.py`，会拒绝过期测试、修改过的基线、非零TNS或负WNS。
'''
(R/'README.md').write_text(readme,encoding='utf-8')
(O/'验证记录.md').write_text(readme,encoding='utf-8')
print('V8_DELIVERY_READY',json.dumps({k:manifest[k] for k in ['bitstream','bit_sha256','timing_ns','resources','programmed']},ensure_ascii=False))
