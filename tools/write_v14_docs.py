from pathlib import Path
import json,hashlib
R=Path(__file__).resolve().parents[1];O=R/'output'
m=json.loads((O/'build_manifest.json').read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(O/m['bitstream'])==m['bit_sha256']
for ref in m['tests'].values():assert sha(R/ref['path'])==ref['sha256']
tim=m['timing_ns'];rows='\n'.join(f"|{k}|{v['used']}/{v['capacity']}|{v['remaining']}|" for k,v in m['resources'].items())
text=f'''# V14：只修SW3同帧延迟，保留SW1/SW2

正式固件：`output/{m['bitstream']}`。SHA256：`{m['bit_sha256']}`。

本版已完成源码修改、仿真、完整TD综合/布局布线和最终时序检查。**尚未烧录本版，实板数值显示与稳定性待验收。**

## 操作

1. 用BitWriter的`PROGRAM_SRAM`烧录上面文件。
2. SW1、SW2拨下；SW3拨上。SW4拨上开启文字和标志。
3. 短按K2查看同帧延迟：延迟`XXX.XX毫秒`，正常显示有效1、状态00。
4. K1运行信息、K3链路页面、K4已有ISP参数仍保持原控制。SW4只负责开关标志与文字。

首次启动需要数帧建立完整缓存；不要通过长按复位/重学白平衡来试探延迟。SRAM测试时不需断电。

## 本次查到的阻断与改动

用户提供的2.77秒视频中，源帧号持续更新，延迟为横线、有效0、状态05。它说明来源检查未通过，并导致读会话拒绝。它并不是BCD转换没画出来，也不是没有进入K2页面。

旧代码将RAW像素完整性结论`raw_complete`作为时间测量的前置条件。已构造并导出真实RTL的旧/新配对波形：来源时间戳存在、DDR按地址完整写入并选中该代、完整读出及输出时，仅RAW计数检查未完成就会让旧版产生相同05；新版给出与测试台独立记录的t0/t1相符的真实差值。

这定位了**阻断门限**；没有直接量到实板RAW计数，因此不把模拟出来的RAW数量差异说成已证实的唯一物理原因。

新版“有效”表示**时间来源与传输关联有效**，不是RAW像素/颜色/CRC质量合格证。它要求：

- 第一组有效RAW产生的帧编号和时间戳，经过packed SOF队列匹配实际DDR槽；没有来源就无效。
- 该槽有完整、连续、无溢出的DDR写入，读出确实选择此槽及其代际。
- 完整读出、同帧最终HDMI有效像素数量正确，缓存未覆盖、没有欠载或旧返回污染。
- 输出取的是上述来源原始采集时间；重复显示同帧时沿用原时间，绝不改成最近一帧相机时间。

RAW像素数量/对齐错误本身不改变已经确定的首像素时间来源。仅这项图像质量观测不再一票否决时间数值；RAW短少同时导致DDR写入不足时，仍然不报有效延迟。

三个旧RAW质量单元场景的期望因此有意改变，完整日志和修改字典见`validation/latency_provenance_unit/result.json`，没有将其伪装成旧拒绝策略逐拍不变。所有来源/缓存/读写/输出保护仍独立测试。

## 测量范围

起点是同帧第一组有效RAW进入ISP前端的时刻，位于MIPI/CSI解包之后；终点是同来源帧首个有效像素到达最终HDMI发送器输入的时刻。

包含图像处理、实际DDR等待与显示末级流水线；不包含摄像头曝光、起点以前的解包、HDMI线缆或显示器内部响应。计时分辨率1微秒，显示0.01毫秒；跨域同步和量化存在微秒级误差。

数值在该显示帧完整输出、读会话核验结束后发布，页面冻结最近一份结果。不是帧率，也不是两次不同来源帧开始之间的间隔。

## SW1/SW2保护

与已交付V13 timing（bit SHA `b2aeca38…799dfe0`）比较，**唯一功能源变更是`frame_latency_monitor.v`**。220个生产文件字节相同，另外两份ROM初始化文件仅绝对路径迁移。顶层连接、按键、四种风格、图像清晰度处理、相机初始化/裁切、曝光/颜色、火焰与急救识别、跟踪、声光联动全部保持原代码。

监测器输出仅进入原有文字快照，不控制像素、DDR仲裁、识别或报警；SDC与时钟频率保持。依据见`validation/v14_scope/result.json`。本说明不把代码保护说成已观察到本版实板视觉表现。

## 时序与验证

所选实施为`{m['implementation_run']}`，布局种子{m['placement_seed']}；同一冻结RTL和综合gate数据库。最终完整布局布线Setup WNS `{tim['SWNS']:+.3f}ns`，Hold WNS `{tim['HWNS']:+.3f}ns`，Setup/Hold TNS均0。保留并核对原厂继承的critical warning，没有通过删除约束取得通过。初次phy_1实施有一条hold负余量，保留在Runs作为失败证据，未正式交付。

|资源|使用/总量|剩余|
|---|---|---|
{rows}

- `verify_latency_board_repro.py`：旧/新版共用真实事件输入，复现05门限；正常样本不变，无来源/不完整DDR均拒绝。VCD为`validation/board_status05/status05.vcd`，从VCD生成的波形图为同目录`status05_wave.png`。
- `verify_latency_provenance.py`：32场景、172断言；独立时间记录核验差值，含重复/跳帧、覆盖、溢出、欠载、乱序地址、旧返回、残缺输出、超龄、回绕和晚到判定竞争。
- `verify_latency_startup.py`：旧启动缺陷与四种修复启动条件对照、原生FIFO/仲裁/VTC缩高测试。
- `verify_latency_actual_clocks.py`：工程真实名义时钟下的缩高连续帧与HUD采样相位验证。
- `verify_latency_720p_transport.py`：完整1280×720、9个来源帧，以实际DDR读出像素中编码的来源编号核对监测器编号，并以测试台独立t0/t1核验延迟；不再仅看内部计数自证。使用原生packer/FIFO/视频/MC代码，ISP延迟为受控管线、DDR响应为有序行为模型，不是物理PHY/DDR仿真。
- `verify_chinese_hud.py`：51页/状态组合、11750400像素及4096切页探针，确认原中文显示链路。
- `verify_v14_scope.py`：SW1/SW2所有功能源及顶层、约束保护。

每份报告与本轮源哈希、正式bit、时序和资源绑定，见`output/build_manifest.json`。`finalize_v14_delivery.py`拒绝旧产物、源/报告失配、失败测试和负最终时序。

## 重新验证/构建

先`tools/prepare_project.py`；运行上述验证（startup先于actual_clocks和720p_transport，因为后两者读取其夹具），再执行沿用的`tools/freeze_v13_build.py`冻结V14当前全部输入，然后运行根目录`build.ps1`，等syn_1/phy_1完整结束。若默认实施最终时序合格，执行`tools/finalize_v14_delivery.py`和`tools/write_v14_docs.py`。

本次额外实施seed2按TD自带MultiSeed流程只改变`set_param place seed 2`，使用独立run目录和源/gate/config签名；正式导出命令是`tools/finalize_v14_delivery.py --run {m['implementation_run']}`。`launch_seed2.ps1`为防重复启动的本轮启动器，不能拿旧签名重复开启一轮新构建。重新实现应在独立工作副本准备新配置和签名。保护验证需要保留同级原V13 timing目录；直接烧录bit不依赖它。

本版没有进行SRAM下载、板上数值观察、长期运行或Flash断电保持测试。若仍显示横线，应记录**V14文件名、状态、源帧**继续定位，不能以仿真代替实板成功。
'''
(R/'README_先读我.md').write_text(text,encoding='utf-8');(O/'验证记录.md').write_text(text,encoding='utf-8')
(R/'WORKING_STATUS.md').write_text('V14软件构建/仿真/最终时序/导出完成，正式bit与SHA见output。SW1/SW2功能源不变。尚未烧录或观察实板，详见README_先读我.md。\n',encoding='utf-8')
print('V14_DOCS_WRITTEN')
