// Test-only controller boundary. Both production wrappers are compiled intact;
// only the generated/encrypted ddr2 controller is replaced by this model.
`timescale 1ns/1ps
module ddr2(
 input ref_clk,sys_rst_n,apb_pclk,apb_prst_n,
 output dhi_clk,cfg_clk,ddrphy_rst_n,ddrphy_rdy,
 input [24:0] paxi_awaddr,input paxi_awvalid,output paxi_awready,
 input [127:0] paxi_wdata,input [15:0] paxi_wstrb,
 input paxi_wvalid,paxi_wlast,output paxi_wready,
 input [24:0] paxi_araddr,input paxi_arvalid,output paxi_arready,
 output [127:0] paxi_rdata,output paxi_rlast,paxi_rvalid,input paxi_rready,
 output [12:0] ddr_addr,output [1:0] ddr_ba,
 output ddr_cke,ddr_odt,ddr_cs_n,ddr_ras_n,ddr_cas_n,ddr_we_n,ddr_ck_p,ddr_ck_n,
 inout [1:0] ddr_dm,inout [15:0] ddr_dq,inout [1:0] ddr_dqs_p,ddr_dqs_n
);
 assign dhi_clk=ref_clk;
 assign cfg_clk=ref_clk;
 assign ddrphy_rst_n=sys_rst_n;
 assign ddrphy_rdy=sys_rst_n && handshake_tb.cal_ready;
 assign paxi_awready=ddrphy_rdy && handshake_tb.ctl_aw;
 assign paxi_arready=ddrphy_rdy && handshake_tb.ctl_ar;
 assign paxi_wready=ddrphy_rdy && handshake_tb.ctl_w;
 // One accepted AR address produces exactly one 128-bit response. The
 // production wrapper ties RREADY high. Response contents encode its address.
 reg [6:0] return_valid;
 reg [127:0] return_data[0:6];
 integer n;
 always @(posedge ref_clk or negedge sys_rst_n) begin
  if(!sys_rst_n) begin
   return_valid<=0;
   for(n=0;n<7;n=n+1) return_data[n]<=0;
  end else begin
   return_valid<={return_valid[5:0],paxi_arvalid && paxi_arready};
   return_data[0]<={4{7'd0,paxi_araddr}};
   for(n=1;n<7;n=n+1) return_data[n]<=return_data[n-1];
  end
 end
 assign paxi_rvalid=return_valid[6];
 assign paxi_rlast=return_valid[6];
 assign paxi_rdata=return_data[6];
endmodule
