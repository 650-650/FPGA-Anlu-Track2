onerror {quit -code 1 -force}
onbreak {resume}
if {![file exists work]} {vlib work}
vlog -sv "D:/anlu/TD_6.2.1_Engineer_6.2.168.116/sim_release/ph1p/ph1p_phy_eram_v2.v" "D:/anlu/TD_6.2.1_Engineer_6.2.168.116/sim_release/ph1p/ph1p_phy_gsr.v" "D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/sketch_rom/gate_rom_pair_models.v" "D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/validation/sketch_rom/sketch_rom_gate_tb.sv"
vsim -onfinish stop work.sketch_rom_gate_tb work.PH1P_PHY_GSR
run -all
quit -sim
quit -code 0 -force
