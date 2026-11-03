onerror {quit -code 1 -force}
onbreak {resume}
vlog -sv scene_style_production_width_tb.sv
vsim -onfinish stop work.scene_style_production_width_tb
run -all
quit -sim
quit -code 0 -force
