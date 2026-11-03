"""Human-readable delivery facts generated from the audited final manifest."""
from pathlib import Path
import json
R=Path(__file__).resolve().parents[1];O=R/'output'
m=json.loads((O/'build_manifest.json').read_text(encoding='utf-8'))
q=m['cartoon_quality'];s=q['noise_strong'];w=q['noise_weak']
dark=[x for x in s['details'] if x['gray']<64]
dark_extra=max(x['v10_std']-x['v9_std'] for x in dark)
rows='\n'.join(f"| {k} | {m['v9_resources'][k]['used']} | {v['used']}/{v['total']} | {v['remaining']} |" for k,v in m['resources'].items())
t=m['timing_ns']
doc=f'''# V10 视觉定稿：卡通色块与暗部保护

生成时间：{m['date']}。本工程基于已交付V9紧凑版；原V9的222份生产文件与bit完整保留。已完成源代码、动态仿真、完整布局布线和导出审计；尚未烧板，不能用模型预览代替本次实板效果。

烧录文件：[stylize_flame_fusion_v10_final_visual.bit](output/stylize_flame_fusion_v10_final_visual.bit)

SHA256：`{m['bit_sha256']}`。

## 本次真正改变了什么

卡通由弱亮度修正改为明确的亮度/色差分级，形成更明显的颜色平坦区域；保留原有空间窗口，不继续追加模糊层。删除昂贵的逐邻点RGB选择器，复用现有高斯行和。采用定点YCoCg分离亮度与色差，弱色差小于16时保留，避免把深蓝、棕色等微弱颜色统一归灰。轮廓仍按颜色比例有限减亮，没有恢复“超过亮度阈值直接画纯黑”的旧逻辑，也没有跨帧混合。

为保护夜间表现，亮度低于64使用V9柔和的暗部响应；中亮部使用25%平台宽度的连续色阶。较强的50%平台与最初暗部32周期方案均因噪声代价被拒绝。所有模型探针和被替代的第一轮源码/构建在validation内保留，第一轮归档bit是非交付.bin文件。

清晰滤波维持V9逐字节相同。测试过扩大阈值、扩大邻域、平场增强等候选：噪声数字变好时，弱斜线和远景纹理损失或暗边会变差，因此没有采用。不能把“更糊”算成降噪成功。原清晰曲线、亮度、去灰、曝光、白平衡、摄像头配置均未改。

素描与边缘导引也未改，mode0/2/3与V9真实RTL逐像素相同。不同时间、照明下的观感变化不足以支持临近交付再降低边缘阈值；否则容易恢复已经压下去的暗部散点。追踪、火焰、绿底白十字急救、声光联动、按键、SW4文字和Logo维持原样。

## 质量证据与必须保留的限制

卡通真实RTL共735360像素与独立定点模型逐值匹配，覆盖1280行宽、移动细彩线、颜色与噪声、随机间隙、帧首模式锁存；受保护模式另有92160像素与真实V9一致，固定16拍。全部16777216种RGB的调色函数模型穷举中，彩色变中性、灰色变彩色、Co/Cg符号翻转均为0；最大单通道调色改动10码。该穷举针对调色函数模型，不等于1677万次硬件事务，也不包含后续描线/饱和截断的所有视觉判断。少量原始通道差不超过2码的颜色会改变通道排序，不能声称色相逐点完全无损。

4组正常亮度自然样张的同色相邻像素比例增加、独特色数减少，模型更接近区域填充。4组0.35倍暗化样张仍完整保留作诊断：其中dark_bakery平坦比例下降约0.00324个百分点、独特色数增加10；所以原来“8组全部更平坦”的假设为假，已明确保存在quality_all8_hypothesis.json及最终diagnostics中。正式风格目标检验4组正常亮度，未删除暗部样本或修改它们的数字。

完整生产卡通路线（含原后置滤波）测试1024组强噪声和192组弱噪声，每组8帧。低于64的256个强噪声样例相对V9最大额外STD为{dark_extra:.6f}个RGB码；暗部最初候选该数约1.20，最终未采用。强噪声全部亮度并非都改善：{s['improved_or_equal']}/{s['cases']}改善或相同，中位STD比例{s['median_ratio']:.6f}；最差比例约{s['worst_ratio']['ratio']:.3f}，最大绝对额外STD约{s['worst_absolute_increase']['absolute_std_increase']:.3f}码。弱噪声最大额外STD约{w['worst_absolute_increase']['absolute_std_increase']:.3f}码。色阶过渡肩仍可能放大少量噪声，不能保证所有照度、材质和噪声同时变好。

有色平场另做144组当前生产模型对照，中位STD比例1.00498，最大比例约1.184、最大额外STD约0.464码。颜色区域化与抑噪有取舍，不把保持颜色和更平的正常场景外观写成所有彩色噪声同时下降。

模型预览：[输入/V9/V10对照](validation/cartoon_v10/model_comparison.png)。它是旧样张的算法演示，非本次烧录实拍，也不是手机照片到传感器真实响应的校准。

## 检测与显示保护

实际顶层连接提取后与独立改名的V9模块同拍对照：307200个检测输入、578150次元数据、414143次源时钟检查一致；叠字24480像素、素描/边缘56544像素、SW2/SW3共141360像素精确相同。配对真实火焰流水产生17855个报警有效与6168个蜂鸣器低电平采样，均与V9相同；急救流水3812958拍、1598946个目标有效采样，框线11999像素，急救模式保持静音。它证明这些RTL保护范围一致，不是实物识别准确率、真实声音或完整DDR/MIPI电路仿真。

清晰行缓存与卡通后滤波均做完整1280×720逐36bit测试，并使用安路原厂ERAM模型附验。原清晰曲线200268样例、全宽急救3812959样例、火焰全宽/跟踪/按键/报警/Logo/HUD回归通过。显示RGB/VS/HS/DE延迟1666寄存级；原始控制从更后面的阶段进入，因此控制元数据延迟1660寄存级，不能混为一个数字。延迟与V9相同，检测输入判定没有新增时延。

## 最终资源与时序

| 资源 | V9使用 | V10使用/容量 | V10剩余 |
|---|---:|---:|---:|
{rows}

最终布线setupWNS {t['SWNS']:.3f}ns、holdWNS {t['HWNS']:.3f}ns，setup/holdTNS均0；没有放宽时钟或引脚约束，原3条关键时钟布线告警内容集合与V9相同。逻辑余量增加，但ERAM仅剩{m['resources']['eram']['remaining']}块，不能把逻辑精简误读为任何新功能都可以直接再加。完整审计在output/build_manifest.json，数值来自本工程最终报告，没有借用旧工程构建。

## 上板核对与重建

按键完全沿用V9：SW1的K1清晰、K2卡通、K3素描、K4边缘；SW2识别/跟踪/声光与急救不变，SW4仍控制Logo/说明。先在相同焦距、机位和照明下对比V9/V10卡通的大色块、深蓝/棕色/肤色与暗部散点，再确认K1、K3、K4及SW2。尚需实板的明暗场景、移动镜头、断电重启与长时稳定检查；本轮没有编程下载到FPGA。

V9回退：[原V9烧录文件](../07_stylize_flame_fusion_v9_detail_motion_compact/output/stylize_flame_fusion_v9_detail_motion.bit)。原文件哈希已在最终导出时重核。

重建运行build.ps1；导出审计tools/finalize_v10_delivery.py；说明生成tools/write_v10_delivery_docs.py。硬件资料与公开研究决策见validation/hardware_audit_v10.md及validation/research_v10.md。公开参考采用原作者实时视频抽象论文的“平滑、量化、轮廓分开”思路，未复制外部板级工程。
'''
(R/'README.md').write_text(doc,encoding='utf-8')
(O/'验证记录.md').write_text(doc,encoding='utf-8')
(R/'V10_WORKING_STATUS.md').write_text(f'''# V10当前最终状态

软件工作完成，待用户实板反馈。唯一交付output/{Path(m['bitstream']).name}，SHA256 {m['bit_sha256']}。

基线V9 compact保持原样。最终style源c366fa33ae92051a5a8a0e2174b9361d1830211c5a0c0382e7b97948821fe450；仅卡通重做、两处ROM路径迁移。清晰/素描/边缘/SW2逻辑不动。时序通过SWNS {t['SWNS']}、HWNS {t['HWNS']}，TNS0。

质量不能概括为所有输入更好：暗部散点接近V9，正常亮度色块增加，过渡肩仍有噪声反例；完整README和validation/cartoon_v10/quality_result.json保留。第一轮候选不是成品，保存在validation/attempt1_cartoon25_dark32。软件验证和真正烧板分开；尚未下载或观察V10实板，后续从当前README、输出manifest和用户反馈继续，不要回到普通V9失败布局。
''',encoding='utf-8')
print('V10_DOCS_READY',m['bit_sha256'])
