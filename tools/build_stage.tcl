if {[catch {source camera_to_dsi_display.tcl} result options]} {
    puts stderr "FUSION_BUILD_ERROR: $result"
    if {[dict exists $options -errorinfo]} {puts stderr [dict get $options -errorinfo]}
    exit 1
}
puts "FUSION_BUILD_STAGE_PASS"
exit 0
