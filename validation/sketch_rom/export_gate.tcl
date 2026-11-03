if {[catch {
 import_device ph1_35p.db -package PH1P35MDG324 -speed 3
 open_project {D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/sketch_rom/camera_to_dsi_display.prj} -noanalyze
 import_db {D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/td_project/camera_to_dsi_display_Runs/syn_1/camera_to_dsi_display_gate.db}
 write_verilog {D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/sketch_rom/gate_export.v}
 puts "SKETCH_ROM_GATE_EXPORT_PASS"
} result options]} {
 puts stderr "SKETCH_ROM_GATE_EXPORT_ERROR: $result"
 if {[dict exists $options -errorinfo]} {puts stderr [dict get $options -errorinfo]}
 exit 1
}
exit 0
