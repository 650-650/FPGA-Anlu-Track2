# 主线素描ROM门级初始化门禁

生成/刷新（在工程根目录）：
C:/python/python.exe tools/verify_sketch_rom_gate.py

只读复核：
C:/python/python.exe tools/verify_sketch_rom_gate.py --check-certificate

默认先核对当前build_input_signature.json全部源码，要求当前syn_1阶段PASS且gate.db新鲜。工具在本目录创建私有工程副本，原Runs只读；从当前gate.db导出实际PH1P_PHY_ERAM_V2，按真实端口映射解码所有INIT/INITP，再用原厂物理ROM模型跑两块四口的全部2048地址、单拍更新及CE保持。不会运行综合、布局、布线、bitgen或开发板工具。

result.json关键字段：
- pass: true
- ROM_instances: 2
- unique_addresses_checked: 4096（两块各2048）
- static_port_value_checks: 8192（两块四个读口）
- native_model_checks: 8676（地址值及CE保持）
- source_sha256: 当前冻结全量源码哈希
- style_sha256 / build_input_signature_sha256 / gate_db_sha256 / synthesis_console_sha256
- verifier_sha256 / files_sha256（含实际导出网表、官方模型、TB与日志）

最终导出器应先调用--check-certificate，要求returncode=0，然后绑定result.json本身哈希，核对上述计数。files_sha256同时包含工程相对路径与官方模型绝对路径，均须当前匹配。任何新SYN、源码/冻结/工具/TB/模型/日志变化都会要求刷新证据，不能直接沿用旧结果。

本证据证明当前SYN门级ROM初始化内容与功能读取，不代表最终PHY/STA或实板通过。未知X/Z地址的4态传播不属于已知二值地址等价声明。
