# Existing clock frequencies and groups remain in camera_to_dsi_display.sdc.
# The following clock pairs cross ONLY through new request/acknowledge bundles
# or explicit two/three-flop single-bit synchronizers. No pixel/serial data
# transfer is excepted. The payload is held until acknowledgement, and capture
# waits for three request synchronizer stages plus the frame-commit condition.
# Bound crossing data to one destination period rather than a fractional PLL
# phase edge. Subsequent synchronizer stages retain ordinary same-clock STA.
set_max_delay -from [get_clocks {sys_clk_50m}] -to [get_clocks {HDMI_PIXEL_CLK}] -datapath_only 13.333
set_max_delay -from [get_clocks {HDMI_PIXEL_CLK}] -to [get_clocks {sys_clk_50m}] -datapath_only 20.000
set_max_delay -from [get_clocks {pll_clk_24m}] -to [get_clocks {HDMI_PIXEL_CLK}] -datapath_only 13.333
set_max_delay -from [get_clocks {HDMI_PIXEL_CLK}] -to [get_clocks {pll_clk_24m}] -datapath_only 42.000
