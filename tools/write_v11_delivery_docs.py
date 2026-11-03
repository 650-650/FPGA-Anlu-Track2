"""Write factual V11 delivery notes from the audited final build."""
from pathlib import Path
import json
R=Path(__file__).resolve().parents[1];O=R/'output'
m=json.loads((O/'build_manifest.json').read_text(encoding='utf-8'))
t=m['timing_ns'];rows='\n'.join(f"| {k} | {m['v10_resources'][k]['used']} | {v['used']}/{v['total']} | {v['remaining']} |" for k,v in m['resources'].items())
doc=f'''# V11 六档色块卡通与局部异常点修复

生成：{m['date']}。本工程以最近交付的V10为基线，原222份生产源和V10 bit均完整保留；用户两段视频已复制、哈希、逐帧分析。视频确认普通/卡通模式和黄点现象，未确认当时烧入的bit文件名。软件修改、RTL仿真、完整布局布线及导出审计已完成；本轮没有下载到FPGA，尚无V11实板观测。

本版按强卡通测试候选交付。色阶分界附近的噪声诊断高于V10，实际黄点消除也尚待上板确认；“所有场景都更好”的要求仍待满足。

烧录：[stylize_flame_fusion_v11_cartoon_regions.bit](output/stylize_flame_fusion_v11_cartoon_regions.bit)

SHA256：`{m['bit_sha256']}`。

## 卡通真正改为分类填色

V10连续曲线仍保留大量色阶；旧自然图预览还先缩图再处理，使3×3滤波看起来比真实720p强，验证方式已纠正。本版先完整1280×720执行整数算法和最终显示模型，最后才缩图，另附100%原尺寸裁剪。用户拍屏视频的再处理示意只是风格参照，不能当原始传感器响应预测。

卡通现在把原有两级降噪后的亮度分成六档，3×3标签中值决定填充类别，再取固定亮度0、51、102、153、204、255；保留原RGB色差并统一限制亮度偏移，保护深蓝、棕色、肤色。删除第三层高斯和弱连续棚形曲线。墨线弱边减亮1/4、强边最多1/2，使用已有可信导引，没有恢复一到阈值就置纯黑的逻辑。

分类之后不再使用旧的跨4像素RGB平均。新显示单元只在确认的孤立类别点上，选择九点中的真实RGB向量，不生成平均中间色；邻域至少7/8相近、亮度差至少32才清理，长细线、斜线和正常色块边界有专门对照。少量真实小点和细小字形也可能被清理，这是简化纹理的明确代价。

预览：[完整分辨率处理后的模型对照](validation/cartoon_v11/production_native_comparison.png)。所有图片都是软件模型示意，非V11实板照片。

## 黄点来源与修复边界

两段视频中该点相对显示画面固定，用户补充素描时变灰、边缘时不明显，切回彩色又发黄，支持异常进入图像处理链。修改前实际mixer/HUD/Logo/显示链的1843200像素均匀帧测试，没有在非叠字区自行产生额外彩点；这不等于确定传感器损坏。基准源码快照、完整裁剪、模板配准和测试均保存在validation/yellow_dot_v11。

由实际RTL叠字模板映射到1280×720显示平面，位置约696,159，误差约±20×12像素。因此只把x672..719、y144..175作为异常检测候选区，绝不整片涂黑或无条件替换坐标。使用半径2的九点RGB向量中值；中心必须显著偏亮或偏色、至少五个背景样本一致、没有H/V/对角细线延续，才以邻域真实像素替换。Logo、文字、检测框叠字和素描/边缘不参与该修复。

该修复位于识别之后，包含SW2彩色显示；识别器仍收到原始像素。顶层回归明确要求：ROI内黄色异常显示像素修好，检测端仍只收到同一个原始黄色像素，ROI内另外注入的红/绿框角叠字逐值保留。它不是通过改变火焰或急救阈值来隐藏问题。

平背景且高对比的1×1至4×4热点夹具验证通过；噪声、较大簇、近等亮彩点仍可能漏检，ROI内真实孤立亮点也无法与缺陷无条件区分。是否能把视频中的实际点完全清除，必须烧板再看；不能把模拟修复写成实物黄点已消失。

## 清晰、其他模式和同步保护

清晰的原ISP、画质曲线、去灰、曝光、白平衡、摄像头寄存器都未改。组合显示单元复用V9对称一像素cross，32/16阈值、限幅6的公式完全相同；除有证据的局部异常事件外逐值一致。素描、边缘的导引和渲染保持V10，92160个真实style样例逐值相同。按键、Logo、说明、追踪、火焰、急救、声光算法不变。

新四行缓存替换旧卡通后滤波和旧清晰缓存，RGB、VS、HS、DE、overlay、control整包同步。生产实测显示单元lag3306、3307寄存级；mixer输出到最终HDMI送入段3313寄存级，较V10多1647像素钟，约21.96微秒。检测输入和判定时间没有增加。这里只是该软件显示段的延迟，不是完整相机到屏幕端到端测量。

没有跨帧RGB平均；缓存只为当前空间邻域，不把上一帧物体混回当前画面。没有用追加全屏模糊处理来隐藏噪点。

## 验证与实际限制

实际卡通RTL735360像素和独立整数模型一致，固定16拍、1280行宽、模式锁存和随机间隙通过。显示小场景122880包、全帧1237500包、全帧均匀输入1237500包、原厂ERAM模型1237500包逐36bit通过，均匀帧零改变。中值网络所有362880种九元素排序及随机向量验证通过。最终顶层、检测状态、实际火焰报警/蜂鸣波形、全宽急救和ROI叠字保护均绑定当前源码；详情在output/build_manifest.json。

六档中性渐变的最终输出严格只有六个目标亮度；28组暗色/肤色保留、600042个共同gamut偏移样例、固定校色亮度守恒、原生分辨率处理顺序和分类后RGB集合闭合检查均通过。

必须说明：更强的离散分类会放大接近档位分界的输入抖动。本次768组±12噪声诊断中，V10连续风格平均STD约2.25，六档硬分类约5.47，类别孤点清理后约4.98；分类分界最坏样例仍约24。清理相对硬分类在763/768组不增，最坏额外约0.024码，但这不能宣称相对V10所有噪声更少。与单纯模糊不同，当前目标是明显分色块；如果实板暗部在某些照明下恰好位于色阶分界，仍可能跳色。全部反例、被拒的柔化保护和真实小点损失都保留在validation/cartoon_v11内。

## 最终资源与时序

| 资源 | V10使用 | V11使用/容量 | 剩余 |
|---|---:|---:|---:|
{rows}

最终布线setupWNS {t['SWNS']:.3f}ns、holdWNS {t['HWNS']:.3f}ns，setup/holdTNS均0。原关键时钟布线告警内容与V10相同，没有放宽约束、提高时钟或改引脚。逻辑略增，ERAM由104降至{m['resources']['eram']['used']}，DSP仍32；余量仍需以此最终报告为准。

## 使用、回退和复现

按键沿用：SW1 K1清晰、K2卡通、K3素描、K4边缘；SW2检测/追踪/声光/急救及SW4 Logo/说明不变。先在同焦距、同机位、同照明下看大色块、深色和肤色、镜头移动时边缘及固定黄点，再检查SW2和长时稳定。建议保留原V10烧录文件以便同场景切回对照。

回退：[原V10 bit](../07_stylize_flame_fusion_v10_final_visual/output/stylize_flame_fusion_v10_final_visual.bit)。重建build.ps1；导出tools/finalize_v11_delivery.py；说明生成tools/write_v11_delivery_docs.py；延续入口V11_WORKING_STATUS.md。

研究参考：[Cornell真实FPGA卡通项目](https://people.ece.cornell.edu/land/courses/ece5760/FinalProjects/f2010/kaf42_jay29_teg25/teg25_jay29_kaf42/index.html)和[Real-Time Video Abstraction论文](https://cs.colby.edu/courses/S19/cs365/papers/winnemoller-videoAbstraction-SIG06.pdf)，核对减少颜色、轮廓、分类闪烁及时间平均的风险。没有复制其板级设计、时间平均或HSL转换。管线研究和旧预览问题复现见validation/cartoon_pipeline_review_v11.md。
'''
(R/'README.md').write_text(doc,encoding='utf-8');(O/'验证记录.md').write_text(doc,encoding='utf-8')
(R/'V11_WORKING_STATUS.md').write_text(f'''# V11当前交付状态

软件修改/当前源仿真/完整布线时序/导出审计完成，尚未烧板。唯一交付output/{Path(m['bitstream']).name}，SHA256 {m['bit_sha256']}。

基线V10原222生产文件+bit未改。卡通style637a49d66485bd46b881823d59314a54e76c82055a304b057cc8e11b334e058f；新组合显示827a2e145417c6a3bc5be403c7d4568c6408eb4dbc801ea1ef98beec94add4ab。Top只替换检测后的显示级，两个ROM路径迁移。

6档hard+标签median+原色差，分类后actual-vector孤点清理，ROI强异常修复，不用旧RGB平均。清晰公式/素描/边缘/检测/按键/AE/AWB/摄像头不动。新的显示单元3307级、top3313级。SWNS {t['SWNS']}、HWNS {t['HWNS']}，TNS0。

重要限制：硬分类在分界处有比V10更高的跳色/噪声；不能称所有方面都变好。点在视频约696,159，不是精确坏pixel地址；只按ROI+异常证据修复，实际是否消失未知。新preview先native再缩图，禁止复用旧480处理方式夸大效果。用户实板反馈应从当前README/manifest继续，原视频和所有证据均在validation，勿回滚到普通V9失败布局。
''',encoding='utf-8')
print('V11_DOCS_READY',m['bit_sha256'])
