from pathlib import Path
import json
R=Path(__file__).resolve().parents[1]
m=json.loads((R/'output/build_manifest.json').read_text(encoding='utf-8'))
resources=m['resources'];timing=m['timing_ns'];bit=m['bitstream']
rows='\n'.join(f"| {name} | {v['used']} / {v['capacity']} | {v['remaining']} |" for name,v in resources.items())
body=f'''# V12 同帧采集到 HDMI 延迟可视化

本版独立基于 V11，增加真实帧来源、时间戳和 SW3 K2 延迟页。本次没有实现 K1 风格强度分档，按键方案不变。原 V7、V9 compact、V11 及桌面三版交接包均保留。

正式文件：[烧录 {bit}](output/{bit})。

SHA256：`{m['bit_sha256']}`。大小：{m['bit_bytes']}字节。

软件与最终布线检查已完成；本轮没有下载到 FPGA，没有把模型结果当作实板时延或实板画质验收。

## 使用

1. 建议先 PROGRAM_SRAM，保留原 V11 bit 以便回退。
2. SW1、SW2不选，仅选择SW3；SW4打开Logo和文字。开关极性沿用已验证工程，以SW4显隐确认。
3. 短按K2，进入 SAME FRAME DELAY。等待相机/DDR就绪及若干完整帧后看VALID。
4. DELAY以 `XXX.XX MS` 显示，SOURCE FRAME为16位十六进制源帧号；这个编号会循环回绕。
5. VALID=1表示该条同帧测量有匹配和完整性证据；VALID=0时延迟显示 `---.--`，不会用旧成功值冒充新结果。
6. REPEAT表示相邻有效测量来自同一源帧和采集时间；SKIP表示相邻有效源帧编号出现间隔，不等于测得物理摄像头错误率。

显示的是上一条已完成输出并完成DDR读代际退役的测量，约晚一个输出帧发布。HUD的延迟、帧号和状态在显示帧边界整体锁存，迟到的状态不会把新帧号配上旧数字。

K1仍是SW3运行统计，K3仍是链路状态，K4仍是已有ISP参数。SW1四种视觉、SW2火焰/跟踪/声光/急救的选择及SW4显隐不变。K3长按2秒复位、K4长按1秒重新学色不变。

## 测量的起止位置

起点是实际首组有效RAW像素进入图像处理流，即顶层 `S_raw_tuser/S_raw_tvalid` 对应的第一有效组；终点是同一源帧在最终 `S_hdmi_out_de` 上的首个有效像素，位于HDMI发送器输入处。

包含RAW入口以后的ISP、缓存等待和末端显示处理；不包含传感器曝光、RAW入口以前的MIPI/CSI前端时间、TMDS串行线缆传播和显示器内部响应。它不是光到光延迟，也不是最近两个SOF脉冲的相位差。

统一注册Gray微秒计数在相机和HDMI域同步采样。计时分辨率1us，屏幕显示分辨率0.01ms；存在跨时钟同步/量化误差，没有宣称纳秒精度或完成硬件仪器校准。测试夹具计时容限为±2us。超过1000ms显示支持范围的结果保守标无效。

## 同帧身份与异常处理

RAW帧来源先进入小型元数据队列，按真实packed SOF顺序取出；不把最新RAW时间戳直接当作正在输出帧的时间戳。实际写槽声明绑定帧号、采集时间、有效性；按真实写命令地址与字数检查完整性。

读槽在原video_out帧边界选择事件锁存，读期间检查槽是否被覆盖、代际是否变化、读地址是否连续及旧返回是否跨FIFO复位。读侧原本有帧末预取，因此只校验图像范围内前172800个字，不把正常额外预取误判成整帧错误。

最终首DE先形成候选。完整921600像素输出、没有溢出/下溢/覆盖且DDR读代际安全退役后，才发布这条结果。短帧、空帧、错序、旧返回、迟到/丢失描述符、无退役证据和超龄等情况均显示无效。新帧完成/失败边界优先于旧的迟到结果，避免旧成功复活或覆盖新pending。

## 必须说明的原输入链修复

真实生产style和packer实测：packed SOF只比首valid早1个相机拍，而原video_in会用SOF启动FIFO复位，并等待多级同步释放。原厂生成FIFO行为仿真中，开头48像素被丢掉；完整720p每帧仅写172560个128bit字，少于应有172800字，尾部不足一个240word突发而未发出。

如果只加严格观察器、不处理这个问题，测量页会一直无效。因此V12给video_in增加 `INPUT_ALIGN_CYCLES=24`：data和valid一起推迟24个相机时钟，再进入原FIFO；原SOF复位、槽指针、DDR仲裁/地址策略保持。按基线时序报告约60MHz相机钟计，新增约0.4us。

该对齐不修改任何128bit数据字中的RGB位值，不增加全屏模糊、亮度/色温处理、整帧缓存或乘法器。但它确实修复原来漏掉的图像前缀，所以不能声称完整画面或SW2检测输入与V11逐拍相同；图像位置/原缺失内容恢复后仍需实板对比。没有修改风格、检测阈值、跟踪、报警、AE/AWB算法。参数0保留原输入连接用于对照，正常交付使用24。

## 验证证据

- 异步多时钟单元：30场景、158断言。包括四槽回绕、重复/跳过、RAW/DDR短长帧、乱序、覆盖、上下溢、旧返回、复位期间返回、迟到描述符、丢失verdict、三种同拍竞争、时间/ID回绕和超龄。
- 真实原厂FIFO/生产style/packer/video/MC：1280×8与1280×720均通过。720p的172800字完整写入，921600个输出RGB、源坐标和帧身份逐值一致，无上溢/下溢；真实首DE与独立t0计时scoreboard一致。
- 生产视频测试采用原style(mode0)、packer、两个生成的像素FIFO、命令FIFO、video_in/out及MC接口，加有序行为DDR、64 DDR拍返回延迟和背压；不是物理DDR PHY、完整前端ISP或TMDS仿真。夹具finalDE只有video_out后两拍；实际最终显示端点接线另外由顶层保护核对，不能把夹具约3.579ms当作整机实测。
- 非延迟页507904个HUD像素与旧版逐拍相同；新页1024字符、65536字库像素匹配；旧telemetry字段5976时钟保持，18组BCD换算通过。
- 24拍对齐1167个有效128bit词逐位保持；参数0的1644次输入、1174次DDR策略/指针对照旧版一致；12帧4349时钟HUD快照测试通过。
- 未完成的早期测试/被停止的构建都明确保留为诊断，不被最终发布清单当成当前通过证据。最终清单绑定实际当前源码、测试和bit哈希。

详细结果：[单元](validation/latency_v12_unit/result.json)、[保护](validation/latency_v12_preservation/result.json)、[720p生产链路](validation/latency_v12_video/lead0_style1_align24_sparse1_h720_full/result.json)、[最终清单](output/build_manifest.json)。

## 最终资源与时序

| 资源 | 使用与容量 | 剩余 |
|---|---:|---:|
{rows}

最终setup WNS：{timing['SWNS']:.3f}ns；hold WNS：{timing['HWNS']:.3f}ns；setup/hold TNS均0。未修改时钟频率、引脚或原SDC来放宽检查。原3条关键时钟布线告警内容与V11相同；另有较高利用率告警，不能称零告警。

没有增加ERAM或DSP，但稳健元数据和校验增加了逻辑/寄存器，逻辑余量已很紧。后续风格强度分档仍未实现，不能直接沿用修改前的余量估计，需要先重新预算或压缩新增逻辑。

## 上板与回退检查

先确认基础清晰、远景细节、暗部和运动边界，再检查卡通/素描/边缘及原黄点区域，最后复核SW2火焰、跟踪、声光和绿底白十字。输入前缀恢复是本次唯一影响原像素传输的修复，不能只看延迟数字就跳过画面对照。

SW3 K2正常应逐帧更新来源ID和延迟；重复帧可保持ID并增长帧龄，切光照/焦距不应被解释为软件延迟固定不变。首次启动、复位、输入错误或完整性证据不足时出现横线是明确无效，不应改阈值硬显示数字。若持续无效，先看SW3 K3源/DDR状态、重新复位并保存所烧bit哈希与现象。

本轮没有上板、长跑、断电固化或物理准确率验收。原V11回退文件保持在相邻工程 `07_stylize_flame_fusion_v11_cartoon_regions/output/stylize_flame_fusion_v11_cartoon_regions.bit`；原三版没有改。

## 重建

在副本运行 `tools/prepare_project.py` 更新ROM与工程路径，再运行 `build.ps1`。TD仍为原6.2.1 Engineer。最终输出不能只看文件存在：先确认当前单元/保护/生产视频测试、源码绑定、setup/hold WNS非负、TNS0与资源不过限，再运行 `tools/finalize_v12_delivery.py` 导出，最后运行本说明生成器。

`tools/integrate_latency_v12.py`只是最初接线的历史脚手架，不是最终重建脚本，不应重放。所有实际生产实现以本目录当前源为准。
'''
(R/'README.md').write_text(body,encoding='utf-8')
(R/'output/验证记录.md').write_text(body,encoding='utf-8')
(R/'V12_WORKING_STATUS.md').write_text(f'''# V12 已完成软件交付

正式bit：output/{bit}
SHA256：{m['bit_sha256']}

当前源码、30例单元、保护、720p生产链测试与最终布局布线均通过并由manifest绑定。原三版保留。详细范围与必要24拍输入对齐修复见README。没有自动烧板，实板画质/识别/延迟和长跑验收待完成。
''',encoding='utf-8')
print('V12_DOCUMENTATION_WRITTEN')
