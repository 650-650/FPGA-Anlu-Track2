onerror {quit -code 1 -force}
onbreak {resume}
if {![file exists work]} {vlib work}
vlog -sv +define+__ICARUS__ "D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/user_source/hdl_source/isp/stylize_v5_96.v" "D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/user_source/hdl_source/isp/style_guide_v8.v" "D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/user_source/hdl_source/display_contrast.v" "D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/scene_pixel_equivalence/teammate_display_contrast.v" "D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/scene_pixel_equivalence/teammate_style_guide_v8.v" "D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/scene_pixel_equivalence/teammate_stylize_v5_96.v" "D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/scene_pixel_equivalence/reference_display_contrast.v" "D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/scene_pixel_equivalence/reference_style_guide_v8.v" "D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/scene_pixel_equivalence/reference_stylize_v5_96.v" "D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/scene_pixel_equivalence/scene_style_equivalence_tb.sv" "D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/scene_pixel_equivalence/scene_display_equivalence_tb.sv"
vsim -onfinish stop work.scene_style_equivalence_tb
run -all
quit -sim
vsim -onfinish stop work.scene_display_equivalence_tb
run -all
quit -sim
quit -code 0 -force