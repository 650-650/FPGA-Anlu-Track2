import_device ph1_35p.db -package PH1P35MDG324 -speed 3
open_project camera_to_dsi_display.prj -noanalyze
import_db camera_to_dsi_display_pr.db
foreach pattern {{u_control_hdmi/request_sync[0]} {u_control_hdmi/ack_sync[0]} {u_control_hdmi/held_data*} {u_control_hdmi/O_data*} {u_isp_status/request_sync[0]} {u_isp_status/ack_sync[0]} {u_isp_status/held_data*} {u_isp_status/O_data*} {S_dbg_cam_cfg_seen_sync[0]} {cfg_h[0]} {u_flame_fusion/cfg_sync[0]}} {
    puts "CDC_OBJECT $pattern = [get_regs $pattern]"
}
exit 0
