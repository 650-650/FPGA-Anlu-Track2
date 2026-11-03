from pathlib import Path
import json,hashlib,re
R=Path(__file__).resolve().parents[1]
# Do not run until the current formal manifest exists. py_compile is safe.
manifest_path=R/'output/build_manifest.json'
assert manifest_path.is_file(),'Current finalized manifest is required before documentation generation'
m=json.loads(manifest_path.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def passed(v):return any(v.get(k) in [True,'PASS'] for k in ['pass','passed','status','pass_all'])
bound=[]
for label,item in m['tests'].items():
    path=Path(item['path'].replace(chr(92),'/'))
    if not path.is_absolute():path=R/path
    assert path.is_file() and sha(path)==item['sha256'],('Bound report/tool changed',label,str(path))
    if path.suffix.lower()=='.json':bound.append((label,path.relative_to(R).as_posix(),json.loads(path.read_text(encoding='utf-8-sig'))))
def report(fragment):
    hits=[value for _,path,value in bound if fragment in path]
    assert len(hits)==1,('Required manifest report missing/ambiguous',fragment)
    assert passed(hits[0]),('Required report not passed',fragment)
    return hits[0]
def summary(v):
    out=[]
    def walk(x):
        if isinstance(x,dict):
            for k,z in x.items():
                if k=='summary' and isinstance(z,list):out.extend(str(t) for t in z)
                elif k in ['summary','output','log'] and isinstance(z,str) and ('_PASS' in z or '=' in z):out.append(z)
                elif isinstance(z,(dict,list)):walk(z)
        elif isinstance(x,list):
            for z in x:walk(z)
    walk(v);return '\n'.join(out)
def metric(v,key):
    if key in v:return v[key]
    values=re.findall(r'(?<![\w])'+re.escape(key)+r'=([-+]?\d+(?:\.\d+)?)',summary(v))
    assert values,('Metric missing from actual report',key)
    return values[-1]
def count(v):return f'{int(v):,}'
unit=report('validation/latency_v12_unit/result.json')
hud=report('validation/chinese_hud/result.json')
startup=report('validation/latency_startup/result.json')
actual=report('validation/latency_actual_clocks/result.json')
front=report('single_fifo/result.json')
prot=report('validation/v13_preservation/result.json')
quick=report('style_retiming/quick_result.json')
full=report('style_retiming/full_result.json')
structural=report('style_retiming/structural_result.json')
aid=report('aid_timing/result.json')
assert aid['exhaustive_rgb_count']>=1<<24 and aid['paired_frames']>=32
lat=quick['mathematical_identity']['fixed_latency_clocks']
assert lat==16 and full['mathematical_identity']['fixed_latency_clocks']==lat
full_test=next(iter(full['tests'].values()));fp=full_test['parameters']
quick_pixels=sum(int(metric(v,'pixels')) for k,v in quick['tests'].items() if k.startswith('quick_'))
full_pixels=metric(full_test,'pixels')
aid_state=aid['tests']['paired_detector']
repairs=m['repairs'];measurement=m['measurement']
sensor=repairs['sensor_window'];output_size=repairs['output_size'];roi=repairs['display_roi_y']
raw_gap=repairs['complete_isp_sof_to_packed_valid_clocks'];input_alignment=repairs['input_alignment_default_clocks']
fixed_startups=sum(str(case.get('case','')).startswith('fixed_') for case in startup['results'])
frequency=actual['clock_frequency_mhz']
clock_text=' / '.join(f'{key} {float(frequency[key]):.3f}MHz' for key in ['sys','camera','ddr','hdmi'])
run=m.get('implementation_run','phy_1');seed=m.get('placement_seed',0)
if run=='phy_1':
    implementation_text=f'本次清单选中的实施为 **{run}，布局种子{seed}**。本工程默认只运行该phy_1，正式bit仅绑定本轮冻结输入和该实施的最终结果。'
    alternate_run_text='默认重建只需syn_1与phy_1。以后若新增其他独立实施，应以新清单的implementation_run、placement_seed、额外签名及配置哈希为准，不能套用旧工作轮次。'
else:
    signature=m.get('implementation_signature');assert signature,'Selected extra implementation has no bound signature'
    implementation_text=f'本次清单选中的实施为 **{run}，布局种子{seed}**，额外输入签名为`{signature["path"]}`，SHA256 `{signature["sha256"]}`。仅引用本清单所选实施，不推定其他目录与其共用gate数据库或已经通过。'
    alternate_run_text=f'复现所选额外实施`{run}`，必须使用本清单对应的配置及额外输入签名并重新验证，正式导出选项为`--run {run}`；不能用旧签名重启一轮新构建。'
assert m['timing_ns']['SWNS']>=0 and m['timing_ns']['HWNS']>=0 and m['timing_ns']['STNS']==0 and m['timing_ns']['HTNS']==0
assert (R/'output'/m['bitstream']).is_file() and sha(R/'output'/m['bitstream'])==m['bit_sha256']
report_rows='\n'.join(f'| {label} | `{path}` | 通过（清单绑定哈希） |' for label,path,_ in bound)
t=m['timing_ns'];r=m['resources']
rows='\n'.join(f"| {n} | {v['used']} / {v['capacity']} | {v['remaining']} |" for n,v in r.items())
text=f'''# V13 时序修正版：同帧延迟、中文界面与正确裁切窗口

本版正式文件：`output/{m['bitstream']}`。完整工程、测试工具、日志和哈希均在本目录。本说明由当前正式清单及其绑定报告生成。

本轮完成源码修改、动态仿真、TD 综合与完整布局布线、最终时序核验和 bit 导出。**尚未烧录本版，也未直接观察本版实板；实际显示数值、中文可读性、黑点和现场画质仍需烧录验收。**

## 一、先怎样操作

1. BitWriter 选择本目录 `output/{m['bitstream']}`，先使用 `PROGRAM_SRAM` 测试。
2. SW1、SW2 拨下，只把 **SW3 拨上**；**SW4 拨上**开启标志和文字。
3. 短按 **K2**。页面应显示“同帧延迟”“延迟 XXX.XX 毫秒”“有效1”，下面的“源帧”随实际显示的来源更新，正常“状态00”。开机数帧建立完整缓存之前可以暂时无效。
4. SW4 拨下，标志和说明文字关闭；再拨上可恢复。SW4 独立，不改变当前功能。

请核对文件名，避免继续烧入 V12 或旧 V11。Bit SHA256：

`{m['bit_sha256']}`

## 二、测量到底是什么

对**同一来源帧**记录两个时刻：

`该帧首组有效 RAW 进入 ISP 前端 → ISP / 风格处理 → 实际 DDR 缓存等待与选帧 → 显示末级 → 同帧首个有效像素到 HDMI 发送器输入`

二者的时间差就是本页的延迟。它包含 FPGA 内图像处理、缓存等待和显示输出流水线；起点位于 MIPI/CSI 解包之后。因此不包含摄像头曝光、起点以前的串行接收/解包、HDMI 线缆和显示器内部响应，不能称为光到光延迟。

时钟计数分辨率为 {measurement['timer_us']} 微秒，页面显示分辨率为 {measurement['display_ms']} 毫秒。同步和量化存在误差，不是纳秒精度。比如“035.79 毫秒”仅是格式示例，实际数值由实时测量产生。

为防止残缺帧或缓存被覆盖仍显示假数，数值在该显示帧完整输出且缓存读会话核验结束后发布，显示的是**最近一个已核验完成的显示帧**。这比正在输出的画面晚更新一帧左右。页内的帧号、有效位、重复/跳帧与数值按帧一起冻结。

- **源帧**：实际被选中并显示的相机帧编号，四位十六进制，A…F 表示十进制10…15；16位编号会回绕。
- **重复1**：这次显示重复了上一次已确认的来源帧；仍保留该来源最初的采集时间，因此等待时间会增长。
- **跳帧1**：这次有效来源编号比上次前进超过1，表示中间来源未出现在这两个有效样本之间。它不是摄像头物理错误率。
- **有效0**：当前无法证明同帧完整关联，数值显示横线；不会用最近相机起点猜一个时间。

四个 DDR 缓冲区附带独立帧编号、时间戳和代际状态，跟随真实读写指针。没有新增整帧缓存或乘法器。

## 三、本轮等价时序优化与保留的有效性修复

### 风格梯度提前计算，输出周期不变

粗尺度Sobel梯度改用有符号差分与平衡加法，并提前到原窗口寄存器所在时钟沿计算。原窗口输出、线缓存、图像标签及总延迟 **LAT{lat}保持不变**；对外像素、valid/user/last/ready逐拍一致，没有增加显示延迟或改动清晰、卡通、素描、边缘的阈值/配色算法。

当前结构保护报告逐项核对声明重定时边界之外的源码：前级、palette/render/C1/C2/output及原窗口寄存输出和line memory保持原样，新增pre-tap对应原输出寄存器的精确右值，只有粗尺度分支使用提前的梯度。数学系数、符号位宽和梯度范围证明见当前quick报告；quick内部/外部梯度分支合计比较{count(quick_pixels)}个输出像素，full回归为{fp['W']}×{fp['H']}、{fp['F']}帧、{count(full_pixels)}个输出像素，覆盖四种模式及边界、有效间隙、SOF、模式变化和复位。

### 被动监测器B计数编码

每槽写进度由相对word计数改为绝对word游标，让写地址直接与游标比较，减少base加相对计数的组合链。旧逻辑计数范围及回绕、新帧优先级、顺序/对齐判断、完整性、错误/覆盖/欠载与读会话接受条件均保持；没有缩短来源编号或时间戳，也没有改变任何像素输入或显示时序。监测输出仍只进入HUD快照，不控制图像、DDR仲裁或报警。

该编码说明对应当前源码和本清单的监测器/启动/真实时钟及源保护回归。本文不引用历史小综合“省多少门”的数字作为本轮最终收益；资源只采用下面的完整实现报告。

### 急救green仅一项纯组合等价优化

保留green前缀、white、全部阈值和顺序状态/定位/框逻辑，只把尾项`g-minimum>=g[7:3]`换成显式9位并行条件`g>=r+(g>>3) || g>=b+(g>>3)`。原前缀已保证g严格高于r和b，所以minimum=min(r,b)；令q=g[7:3]，原式等价于g>=r+q或g>=b+q，9位加法不会溢出。没有增加流水级、改输入或移动输出框。

实际完整RTL穷尽{count(aid['exhaustive_rgb_count'])}种RGB，green/white共{count(aid['green_white_bits_compared'])}位一致；默认宽度{aid['paired_frame_width']}的{aid['paired_frames']}帧、{count(metric(aid_state,'cycles'))}拍全部实际顺序状态、target/box/center/hit/color逐拍一致。夹具确实经历获取/丢失/移动、双目标、右边界、关闭与复位，目标存在{count(metric(aid_state,'target_cycles'))}拍，完成绿色run{count(metric(aid_state,'runs'))}次。

参考SHA256：`{aid['reference_sha256']}`；当前SHA256：`{aid['current_sha256']}`。这些风格/急救源码属于**已证明等价的时序实现变化**，不能说成“字节完全没改”；其余受保护算法仍单独做字节级核对。

### 启动VS、RAW错误与完整前端时序

旧版 `video_out` 的三个 VS 同步寄存器没有明确复位。合法的启动情况下，DDR 时钟在复位期间没有运行，硬件寄存器初值为0，而其输入为反相 VS 的空闲电平1；开机便可能制造一个额外 `read_start`。缓存读端多计一帧，显示端没有多计，之后帧号持续相差1，所以页面有来源编号却一直“有效0”。

本版明确将这三个寄存器复位到输入空闲值 **1**，保留帧代际一致性校验。对照仿真已复现旧版永久错位，修复后在{fixed_startups}种启动时钟/VS条件下均能匹配。它是已证实的代码缺陷，尚不能断言它是用户那块板上一切无效情况的唯一原因。

另外，只有真实 RAW 有效数据拍上的 lane 错误才标坏本帧；空白或重同步阶段的 lane 事件不再追溯污染已经结束的 RAW 帧。有效数据拍错误、缺帧、额外数据、缓存覆盖、旧返回、欠载和不完整输出仍被拒绝。

当前生产FIFO入口默认额外延迟为 **{input_alignment}拍**。完整生产前端报告中的SOF到第一笔packed valid间隔为 **{raw_gap}个相机时钟**，原裁切版FIFO复位间隔已足够；不能用简化夹具的不同间隔推导给完整ISP额外插延迟。可选延时仅供受控夹具，默认分支维持正确窗口版的原数据/valid通路。

## 四、中文页面与按键

可选页面、操作说明、状态、方向、计数和延迟单位均改为中文；保留板上丝印 K1…K4、SW1…SW4 和数字/十六进制字符。16×16汉字点阵放大到32像素，四行透明叠加，位置在画面下部；两次同步 ROM 读取保持原叠加器时序。

SW1、SW2、SW3 大功能只选一个拨上，其他拨下；全下为基础清晰画面。SW4 单独控制标志和文字。

| 开关选择 | K1短按 | K2短按 | K3短按 | K4短按 |
|---|---|---|---|---|
| SW1…SW3全下 | 自动颜色并重学 | 色温向冷微调 | 色温向暖微调 | 色偏：中性→品红→绿色循环 |
| 仅SW1上 | 清晰 | 卡通 | 素描 | 边缘 |
| 仅SW2上 | 火焰检测 | 目标跟踪 | 声光联动；已在本页时再按切软件静音 | 绿底白十字急救标志 |
| 仅SW3上 | 帧率与运行时间 | 同帧延迟 | 链路状态 | 已有曝光、增益和颜色参数 |

全局长按 **K3两秒复位**，长按 **K4一秒重新学习颜色**，长按松手不触发对应短按功能。首次选择 SW1 默认进入卡通，与原控制逻辑一致。

SW2 的“声音使能1”表示软件联动条件，不代表蜂鸣器物理上必然已发声，还受既有硬件开关、来源状态和确认条件影响；这些逻辑本轮保持原样。急救对象为绿底白十字，页面用中文“上部/中部/下部、左侧/中央/右侧”显示方向。

SW3 K1 的帧率不是延迟；K3 缓存错误统计未接入时仍明确写未接入，不伪装成零；K4 曝光显示单位为半行、增益为序号，不假称毫秒或倍数。多开 SW1…SW3 的组合页提示只选一个，按原逻辑停用报警。

## 五、最新裁切版本确实保留了什么

以 `07_stylize_flame_fusion_v11_sensor_window_fix` 为保护基线，传感器纵窗保留 **{sensor[0]}…{sensor[1]}**，输出仍 **{output_size[0]}×{output_size[1]}、原Bayer相位**，没有缩放或降分辨率。

两份摄像头初始化配置逐字节与该窗口版一致，测试图/方向、stream-on后原等待设置保持；顶层异常点修复 ROI 保留 **Y{roi[0]}…{roi[1]-1}**（上界{roi[1]}不含）。不是仅复制一个滤波模块却漏掉顶层参数。

当前保护报告中，{count(prot['exact_protected_source_count'])}项文件与正确窗口基线逐字节相同；ROM绝对路径迁移和明确的观察/UI变化分别列出。火焰/跟踪/声光、按键及原图参数仍受字节保护；风格梯度和急救green按上述结构/数学/逐拍等价证据保护。没有用改算法阈值、降低清晰度、改变像素输出周期来换时序。新增观察信号只去延迟/文字，不控制图像数据、DDR仲裁或检测阈值；原VS同步复位修复也明确作为传输控制差异列出。

这是源码保护与仿真证据；摄像头真实场景下的黑点消除、清晰度和识别表现仍应在同光照条件实板对比。

## 六、无效时怎样读状态

“状态”是两位十六进制位掩码，多种原因可相加。正常应为00，80只表示等待当前帧核验。

| 值 | 含义 |
|---|---|
| 01 | 来源元数据或RAW完整性未确认 |
| 02 | 写入未完成或缓存已标坏（地址/溢出/源错误等） |
| 04 | 读会话不能确认：未完整读出、旧返回、复位/覆盖等 |
| 08 | 缓存读代际与HDMI代际不匹配 |
| 10 | 显示FIFO欠载 |
| 20 | 显示有效像素数不完整或超出 |
| 40 | 来源时间超过支持的1秒范围 |
| 80 | 等待完整帧/读会话核验 |

若稳定运行数秒仍无数值，请记录本版文件名、有效位、状态和源帧，再定位对应原因。无需反复改风格或白平衡来试探延迟页。

## 七、最终构建与验证

TD 6.2.168116 / PH1P35MDG324。使用本工程 `.al`、主 `.sdc` 与 `fusion_cdc.sdc`，保留原时钟频率和时序约束。

{implementation_text}

最终布局布线：Setup WNS **{t['SWNS']:+.3f}ns**，Hold WNS **{t['HWNS']:+.3f}ns**，Setup/Hold TNS均0。

| 资源 | 使用 / 总量 | 剩余 |
|---|---|---|
{rows}

继承的原厂时钟/IP critical warning逐条记录在 `output/build_manifest.json`，与窗口基线相同；资源利用率较高，仍需把实板长期稳定性单独验收。

验证入口与结果：

- `tools/verify_style_retiming.py --quick` / `--full`：结构保护、数学与逐拍数据/控制/标签证明见当前quick/full报告，完整规模与像素数列于上文。
- `tools/verify_style_retiming_scope.py`：重定时声明边界以外源码保护；其余测试负责边界内行为等价。
- `tools/verify_aid_timing_equivalence.py`：完整RGB穷尽与{aid['paired_frames']}帧真实状态/输出逐拍对照，见上文计数及参考/当前哈希。
- `tools/latency_v12_unit_verify.py`：当前监测器的{unit['cases']}个场景、{unit['checks']}项断言，独立测试台事件时间核验差值；不是电脑时间或实板测量。
- `tools/verify_latency_startup.py`：旧缺陷对照与{fixed_startups}种新启动条件；实际VTC、原生FIFO/视频/MC及受控末级同步延时，测试边界以当前报告为准。
- `tools/verify_latency_actual_clocks.py`：当前真实名义时钟{clock_text}，{actual['metrics']['updates']}次有效更新、欠载{actual['metrics']['under']}；HUD快照相位采到{actual['hud_snapshot_valid_frames']}帧有效元组。缩高夹具为{actual['width']}×{actual['height']}，不是实板读数；同来源重复时仍沿用最初采集时间。
- `tools/verify_latency_frontend.py --video --csi --single`：完整{output_size[0]}×{output_size[1]}真实CSI RAW10解包、adapter和ISP调度；核对{count(front['checked_raw_groups'])}组RAW、{count(front['packed_words'])}个packed word、默认原生输入写入{count(front['native_written_words_align0'])}个word、溢出{front['overflow_hits']}。demosaic RAM采用同步兼容模型，只验证调度/数量，不证明真实相机颜色。
- `tools/verify_latency_blank_error.py`：空白错误与有效拍错误的拒绝语义回归。
- `tools/verify_chinese_hud.py`：{hud['page_cases']}页/状态组合、{count(hud['compared_pixels'])}个像素、{count(hud['control_switch_probes'])}次切页探针，保持两拍。
- `tools/verify_v13_preservation.py`：正确窗口基线保护、明确等价例外、输入原通路、旧遥测与新增数值、包含原因码的逐帧完整HUD快照。

| 当前清单项 | 报告路径 | 状态 |
|---|---|---|
{report_rows}

所有验收报告都带当前源码哈希；`output/build_manifest.json`同时绑定构建输入签名、bit、最终时序/资源和验证报告。`tools/finalize_v13_delivery.py`在任何哈希失配、旧输出、负最终时序或测试未通过时拒绝导出。

### 重新构建的完整顺序

直接烧录正式bit不依赖其他工程。重新执行保护验证和正式导出需要保留正确的 `07_stylize_flame_fusion_v11_sensor_window_fix`。本轮已核对其移动后的实际位置为 **`{m['baseline']}`**；bit仍为8204e549…ac95，全部223个清单文件哈希匹配。工具优先读取环境变量`FPGA_V13_BASELINE`，其次查找V13同级目录和当前已验证的位置；任何位置都必须通过固定bit身份与全部清单源检查。迁移到其他电脑时可将环境变量指向正确窗口基线；不要用旧 `v11_cartoon_regions` 替代。同时保留本工程`validation/reference_v13/`风格参考源和`validation/aid_timing/reference_original.v`，以复现等价证明。

隔离工程未带入两份原厂生成的DDR过程/DRC日志；它们没有列入TD设计输入，保护报告单独列出这两项。所有设计源、约束和算法保护检查均执行。

在V13根目录按顺序执行：

1. `tools/prepare_project.py`：修正当前目录下的ROM和TD路径。
2. 先执行`tools/verify_style_retiming_scope.py`、`tools/verify_style_retiming.py --quick`与`--full`、`tools/verify_aid_timing_equivalence.py`（重验不加--install）；再运行上列监测器、启动、真实时钟、空白错误、完整前端（`--video --csi --single`）、中文与保护工具，生成绑定当前源的报告。移动路径后不能沿用旧报告哈希。
3. `tools/freeze_v13_build.py`：冻结本轮全部构建输入和起始时间。**build.ps1不会自动执行这一步。**
4. 根目录 `build.ps1`：等待完整 `syn_1`、`phy_1`完成。
5. `tools/finalize_v13_delivery.py`：核验当前源码、全部测试、最终时序及新产物，再导出正式bit。
6. 仅在当前正式manifest已经生成后运行`tools/write_v13_docs.py`，按绑定报告生成本说明和验证记录。

{alternate_run_text}

Python工具可使用本机的 `C:/Users/Harry/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`。其他电脑需把工具中的Python/TD/Icarus本机路径改为实际安装路径，再完整验证。复制、移动或准备路径本身不会重新生成bit；改源或重新准备后要重做签名和构建。

当前证据边界：未进行本版SRAM下载、实板读数、物理DDR/TMDS仿真、长时间运行或Flash断电保持验收。不能把软件构建/仿真通过写成这些项目已通过。
'''
(R/'README_先读我.md').write_text(text,encoding='utf-8')
(R/'WORKING_STATUS.md').write_text(f"# V13 时序修正版软件交付状态\n\n正式bit：output/{m['bitstream']}，SHA256 {m['bit_sha256']}。\n\n当前清单绑定的动态验证、完整TD构建和最终时序核验已通过。风格LAT{lat}重定时、monitor B计数编码、急救单尾项分别按等价证据保护，不能写成所有源码字节未改。所选实施{run}，seed{seed}。\n\n本版实板烧录、延迟/中文/黑点/视觉识别、长期运行及断电保持尚待验收。详见README_先读我.md和output/build_manifest.json。\n",encoding='utf-8')
(R/'output/验证记录.md').write_text(text,encoding='utf-8')
print('V13_DOCS_WRITTEN')
