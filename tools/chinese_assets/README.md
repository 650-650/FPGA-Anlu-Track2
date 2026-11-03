# 中文菜单源资产

修改 `menu_zh.json` 后运行 `build_chinese_assets.py --install`，随后运行上一级 `verify_chinese_hud.py`。生产 ROM 和 HUD 常量会同步更新，不能直接把 Unicode 码点写进紧凑字形 ID 字段。

`legacy_ascii_font.v.txt` 只保留旧版 ASCII 位图作为可复现输入，不参与项目综合。生成器取本机16像素宋体子集，数字沿用旧位图并补小数点；不复制完整字体。`generated/` 是独立资产预览和中间存储，不应作为额外 Verilog 源一起加入 TD；工程只编译 `user_source/hdl_source/` 中已登记的两个 ROM。

详细实际 RTL 验证见 `validation/chinese_hud/README.md` 和 `result.json`。生成器自己的预览只是排版示例，以 RTL 验证渲染和最终实板为准。
