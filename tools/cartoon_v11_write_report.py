"""Write the human-readable selected V11 quality evidence, no RTL edits."""
from pathlib import Path
import json
R=Path(__file__).resolve().parents[1];V=R/'validation/cartoon_v11'
q=json.loads((V/'quality_result.json').read_text(encoding='utf-8'));rtl=json.loads((V/'result.json').read_text(encoding='utf-8'));area=json.loads((V/'area_probe/result.json').read_text(encoding='utf-8'));detail=json.loads((V/'detail_quality_result.json').read_text(encoding='utf-8'))
n=q['noise_summary'];worst=n['worst_extra_cleanup'];extra=worst['v11_final']-worst['v11_before_cleanup']
text=f'''# V11 分类色块卡通：实现与验证

当前选择为 **六档硬分类＋3×3标签中值＋原RGB色差＋有限墨线**。与 V10 的连续明暗曲线不同，这次确实将像素归入离散亮度类别，再涂成大片色块；没有继续增加高斯模糊半径。硬类别的亮度为 `[0,51,102,153,204,255]`，标签阈值为 `[25,76,127,178,229]`。

style SHA256：`{q['source_sha256']['user_source/hdl_source/isp/stylize_v5_96.v']}`。
最终显示 SHA256：`{q['source_sha256']['user_source/hdl_source/display_denoise_v11.v']}`。

## 实现边界

复用原有 B2 去噪颜色与 W3 行缓存，将九个有序亮度标签做中值，再确定类别填充亮度。颜色使用一个共同 RGB 亮度偏移，并统一限制在三个通道都不越界的范围，保持原通道差；深蓝、棕色、肤色不会被独立粗RGB量化误归为灰色。弱轮廓最多减亮1/4，强轮廓最多减亮1/2。未添加跨帧混合、白平衡学习、自动曝光调整或新的图像帧缓存。

最终 HDMI 显示模块复用稀疏 radius2 的九样本向量中值，按 `{{Y8,RGB24}}` 排序取真实 RGB 样本。卡通仅在中心与中值亮度相差至少32、外围至少7/8样本与中值RGB距离不超过24时替换孤点；没有再次进行RGB平均，不产生中间混色。固定疑点ROI的亮/彩异常点处理由同一显示模块承担，详见其独立验证。

模式0清晰、模式2素描、模式3边缘的 style 输出与 V10 逐值相同，固定16拍。最终显示端时延和36位packet对齐另由组合显示RTL/原厂ERAM测试验证，不能将本模型的原坐标RGB返回值当作实测时延。

## 实际验证

- style真实RTL：735360像素与独立模型相同，含全1280行宽、随机有效间隙、帧模式锁存、颜色噪声与移动细线；其中92160保留模式像素与真实V10 RTL逐值相同。
- 最终整数显示模型的1280原生灰度渐变，输出确认为六档 `[0,51,102,153,204,255]`。
- 28组普通及暗化色卡保持非中性；例如深蓝 `[18,32,70]→[31,45,83]`，棕色 `[86,52,29]→[83,49,26]`，肤色 `[210,160,130]→[198,148,118]`；是模型参考，不是实板测得颜色。
- 600042个颜色/目标档组合检查共同gamut限幅不改变RGB通道差；非中性固定校色参考保持精确 `R+2G+B`。
- 4张旧raw RGB样张和2张用户视频帧，均先按 **1280×720原生像素完成style、校色和最终display**，最后才为联系图缩小。另提供100%原生裁切。最终RGB集合是输入style RGB集合的子集；会检测旧平均滤波被误接回的问题。

本轮预览修正了此前“先缩图再运行硬件核”的尺度错误。`production_native_comparison.png` 是新流程，`*_production_final_100pct.png` 是100%原生裁切。两张手机拍屏视频帧已包含屏幕、相机、透视和OSD影响，只作纹理/风格示意，没有冒充原始传感器数据。

校色参考明确采用 gainR/gainB=4096、trim0，因此该源方程是精确恒等；另外的非中性参考只验证加色后仍保留亮度。没有猜测当前板上学习到的增益，也不声称模型复现了实际照明、传感器、DDR或显示器。

## 全链噪声与细节取舍

硬分类让色块更明确，也会放大接近类别阈值的帧间微小波动。测试保留了全部256灰度、IID/3×3/4×4相关噪声、±12、每组8帧，共768组，不只挑好看的灰度。

| 模型路线 | 全灰度平均STD |
|---|---:|
| V10连续风格＋旧后滤波 | {n['mean_v10_std']:.6f} |
| V11硬类别，孤点清理前 | {n['mean_v11_raw_std']:.6f} |
| V11最终向量孤点清理后 | {n['mean_v11_final_std']:.6f} |

孤点清理在 {n['cleanup_improved_or_equal']}/768组中STD没有增加，平均从约5.47降到4.98；最坏额外约{extra:.5f}码，反例完整保留。它不能解决整块场景恰好跨类别阈值的跳变：最坏灰180的STD仍约24，明显高于V10连续风格。不能宣称本版每一种噪声、每一个场景都更少；本版首先实现用户要求的明显分类卡通，并在保持类别颜色的前提下清理孤点。

物理像素噪声夹具为96×72，未缩放输入；此处小尺寸仅控制计算量，不是把自然图先缩小再作为硬件像素。该尺寸不包含固定疑点ROI，因此这组数字代表其余画面位置的全局卡通孤点清理；完整1280样张仍使用真实默认ROI。

最终display模型32组真点/细线测试中，1/2像素长线、斜线及边缘的内部区域均保持；但真实孤立1像素点、2×2亮点和部分3×3小块可能被当作孤点删除。完整style链在该有限夹具里额外修改了pipeline边界的2像素和1个肤色真孤点。不能据此声称所有真实小细节都不受影响。数值见 `detail_quality_result.json`。

## 资源

相同器件、相同低引脚测试顶层的模块级 TD optimize-gate 探针，**不是最终整机布线资源**：

| style核 | LUT6 | 预打包Slice | 寄存器 | ERAM | DSP |
|---|---:|---:|---:|---:|---:|
| V10 | {area['v10']['lut6']} | {area['v10']['slice']} | {area['v10']['slice reg']} | {area['v10']['eram']} | {area['v10']['dsp']} |
| V11 | {area['v11']['lut6']} | {area['v11']['slice']} | {area['v11']['slice reg']} | {area['v11']['eram']} | {area['v11']['dsp']} |

本style核减少558 LUT、736寄存器、6 ERAM，未增加DSP；最终组合显示模块与整机是否通过资源/时序，以主交付记录为准。

## 结果文件与未采用方案

正式证据：`result.json`、`quality_result.json`、`detail_quality_result.json`、`area_probe/result.json`。每份数值报告都绑定生产源码/独立模型/脚本哈希，正式quality在运行前后核对其未变。

连续过渡guard、粗糙度guard、提前第二次标签median、8档等均仅作为比较模型保留；native图显示某些保护会使用户墙面重新变成照片膜感，另一些将噪声热点转移到过渡肩，故未写入最终选择。生产常量 `GUARD_DISABLED=1`，综合会消除未使用的实验辅助运算；它们不是当前画面路线。

没有执行V11实板烧录或宣称观察到V11实景效果。'''
(V/'quality_report.md').write_text(text,encoding='utf-8');print(V/'quality_report.md')
