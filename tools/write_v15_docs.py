from pathlib import Path
import json,hashlib
R=Path(__file__).resolve().parents[1];O=R/'output';m=json.loads((O/'build_manifest.json').read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(O/m['bitstream'])==m['bit_sha256']
for v in m['tests'].values():assert sha(R/v['path'])==v['sha256']
t=m['timing_ns'];f=json.loads((R/'validation/paxi_720p/result.json').read_text(encoding='utf-8'))
table='\n'.join(f"|{k}|{v['used']}/{v['capacity']}|{v['remaining']}|" for k,v in m['resources'].items())
text=f'''# V15 同帧延迟最终排查候选

正式固件：`output/{m['bitstream']}`  
SHA256：`{m['bit_sha256']}`

源码、仿真、TD综合、布局布线和最终时序已检查完成。**本版没有由软件代理烧录；真实板上数值、画质和长时间运行仍待验收。**

## 先这样测试

1. 在 BitWriter 中加载上述 output 内固件，用 `PROGRAM_SRAM` 下载。先不用改 Flash，保留已有演示版本。
2. SW1、SW2拨下，SW3拨上；SW4拨上开启中文文字和标志。
3. 短按 K2，等待约10秒：应看到“延迟 XXX.XX毫秒、有效1、状态00”，并有来源帧编号。上电前几帧建立缓存时可暂时是横线。
4. K1是运行与帧率；K2是同帧延迟；K3是链路/延迟原因；K4是已有曝光、增益等参数。短按，不需要长按重置或重新学颜色。
5. 若延迟仍持续横线，短按K3，记录“延迟状态”和四位“原因”；本版能区分旧返回未清空、FIFO丢返回、地址/字数问题等，不再只有含义模糊的04。对应表见 `排查说明.md`。
6. 用相同镜头/灯光回到 SW1 K1至K4 和 SW2 K1至K4，核对视觉、检测和声光表现。实际观测确认前，不将源码保护测试写成板上效果保证。

SW4仍只控制标志与文字开关。SW1/SW2所有模式选择、算法、检测阈值、裁切、相机设置保留。SRAM下载后断电会回到原Flash版本，测试时不需要断电。

## 这次真正改了什么

真实DDR封装把读、写地址的READY混在一起，旧命令FIFO可能在AR尚未被接收时弹出读请求。一个请求丢失后，待返回计数永远差1，延迟一直无效。现在保持命令到对应通道真正握手，AW/W分别确认；用原FIFO，只加两个接收状态位。

强背压仿真还查到输出FIFO已满时丢像素却可能误报延迟有效。现在仅增加FULL的被动观察，将这类帧拒绝，恢复正常后再发布可信数字。不修改预取、像素或FIFO控制。

此外 SW3 K3 增加中文原因位图。49组其他页面的实际RTL像素与V14完全一致，仅K3的两组画面改变。保留最新裁切和已认可的SW1/SW2图像/识别算法。

## 数值到底测什么

第一组有效RAW像素进入解包后的FPGA采集接口记t0，同一来源图像实际到达最终HDMI发射模块像素输入端记t1。测量`t1－t0`，包括处理、DDR等待和显示扫描等待，不含传感器曝光和显示器内部响应。

按实际四缓冲区的写入代、读出代和来源编号关联。整帧输出和读会话结算后才发布，所以页面显示最近一帧已经验证的数值，有约一帧更新滞后。重复帧保留原始t0，故重复显示的年龄会增加。

## 验证结果

- 实际MC+原厂命令FIFO+实际PAXI封装：9类协议场景通过，50000笔随机独立背压精确收发。
- 共用READY：5000笔连续刺激、6510比较拍，新旧实际接受事务、像素载荷和返回逐拍相同，没有新增正常传输周期。
- 32个来源/时间场景、172项检查，以及8个上电时钟/VS场景通过。
- 观察器新增原因前后32场景、20253拍，原有输出逐拍一致。
- 强背压与跨VS迟到返回的坏帧被拒绝，后续正确帧恢复；未以放宽有效门槛换数字。
- 另在已有2帧通过后注入迟到返回：受影响帧拒绝，之后9个正确帧恢复；故障诱发的输入溢出和少写也按实际FIFO接纳预算核对，未冒充完整图像。
- 完整1280×720实际PAXI运输测试：9个来源帧，{f['pixel_verified_valid_frames']}个有效完整输出帧，每帧921600个像素的来源/坐标与独立t0/t1校验通过；正常场景没有输出FIFO溢出或欠载。重复帧继续使用同一来源时间。
- 51个中文OSD画面、11750400像素、4096控制切换探针通过；其他49画面与V14像素完全一致。
- 最终布线STA：SWNS **+{t['SWNS']:.3f}ns**，HWNS **+{t['HWNS']:.3f}ns**，STNS和HTNS均0。使用原有时序约束，没有改时钟周期或放宽约束来过关。

|资源|使用/总量|余量|
|---|---|---|
{table}

布局布线路径：`td_project/camera_to_dsi_display_Runs/{m['implementation_run']}`。主时钟/异步域约束和旧版一致；报告STA覆盖率95.32%，并非所有路径都由普通同步STA覆盖。异步元数据使用原握手CDC。原有PHY-5060/PHY-5079关键警告保留，未出现新增同类关键警告。完整时序报告见output。

## 复现命令

在本工程目录用 `C:\\python\\python.exe` 运行：

```
python tools/verify_v15_scope.py
python tools/verify_ddr_handshake.py
python tools/verify_ddr_handshake_stream.py
python tools/verify_v15_handshake_waveform.py
python tools/verify_latency_provenance.py
python tools/verify_v15_monitor_equivalence.py
python tools/verify_v15_startup.py
python tools/verify_chinese_hud.py
python tools/verify_v15_hud_preservation.py
python tools/verify_latency_paxi_transport.py --lines 8 --strong-backpressure
python tools/verify_latency_paxi_transport.py --lines 8 --fault-vs-return
python tools/verify_latency_paxi_transport.py --lines 720
python tools/verify_latency_paxi_late_healthy.py
```

正常重建：先 `python tools/prepare_project.py`，然后 `python tools/freeze_v13_build.py`（历史文件名，当前冻结本V15），再执行 `.\\build.ps1`。严格导出是 `python tools/finalize_v15_delivery.py --run {m['implementation_run']}`；它会核对全部源码/测试哈希及新鲜时序，缺项会拒绝导出。

部分测试引用相邻V14作为受保护基线，复现时保留它。不要把旧工具名中的V12/V13理解成当前固件基线；V15生产源码、编译输入和报告哈希以manifest为准。

## 证据边界

真实RTL已经复现旧握手缺陷，但还没有在物理板上探测到READY不一致的瞬间，不能据此宣称唯一实板原因已全部测明。完整仿真使用真实封装/FIFO/VTC/视频运输与观察器，行为模型代替加密DDR控制器和物理PHY，受控流水代替ISP内部处理。

强背压反例会故意制造坏图像，本版保证不把这些坏帧冒充可信延迟；没有重新设计原预取算法。正常工作条件下协议周期一致性、逐像素图像顺序和时间来源有仿真证据，板上显示与长期稳定仍需按上面步骤确认。

更多原因分析、原始VCD波形、具体源码保护和官方/GitHub参考见 `排查说明.md`；所有报告索引与哈希见 `output/build_manifest.json`。
'''
(R/'README_先读我.md').write_text(text,encoding='utf-8',newline='\n')
(R/'WORKING_STATUS.md').write_text('V15 strict software/build verification complete. Formal bit in output; PROGRAM_SRAM and board visual/latency acceptance pending. See README_先读我.md.\n',encoding='utf-8')
print('V15_DOCS_WRITTEN')
