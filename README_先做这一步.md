# V11 摄像头窗口修正版

在独立副本中合入 V7 已采用的窗口规避方法，原 V11 源码和 bit 保留。

- 摄像头纵向窗口由 256..1703 改为 192..1639：取景上移 64 个传感器行，相当于 32 个输出行。
- 输出仍为 1280×720，窗口高度、时序、binning、BGGR 相位不变；恢复正常实景和方向。
- V11 六档卡通、清晰/素描/边缘、控制、OSD、火焰检测和报警算法保持。
- 随取景变化，原显示黄点修正 ROI 从 x=672..719/y=144..175 调为 x=672..719/y=176..207；修正规则、强度和保护条件保持。
- 这是通过调整取景避开异常底缘的方案。V11 版本的实板消斑效果尚待确认。

下载文件：`output/stylize_flame_fusion_v11_sensor_window_fix.bit`。

BitWriter 选择 PROGRAM_SRAM，SW1-SW4 全下；下载完成后等待约 10 秒。先看清晰画面，再切卡通、素描、边缘，改变环境亮度核对原黑斑区域。不要在 SRAM 下载后按电源重启来判断此版本，重启会回到板载 Flash 程序。

构建完成后以 `output/修正版构建记录.md` 和 `output/fix_manifest.json` 为准。构建和仿真通过不等于已完成实板验收。

复现：运行 tools/prepare_project.py、tools/verify_window_fix.py、tools/verify_v11_roi.py、build.ps1，检查最终时序，再运行 tools/export_window_fix.py。导出脚本避免覆盖既有输出 bit。
