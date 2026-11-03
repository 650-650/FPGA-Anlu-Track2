// Test-only PAXI memory controller. Compile the production outer DDR wrapper
// intact, replacing only its encrypted/generated ddr2 child with this module.
`timescale 1ns/1ps
module ddr2(
 input ref_clk,sys_rst_n,apb_pclk,apb_prst_n,
 output dhi_clk,cfg_clk,ddrphy_rst_n,ddrphy_rdy,
 input [24:0] paxi_awaddr,input paxi_awvalid,output paxi_awready,
 input [127:0] paxi_wdata,input [15:0] paxi_wstrb,
 input paxi_wvalid,paxi_wlast,output paxi_wready,
 input [24:0] paxi_araddr,input paxi_arvalid,output paxi_arready,
 output reg [127:0] paxi_rdata,output paxi_rlast,
 output reg paxi_rvalid,input paxi_rready,
 output [12:0] ddr_addr,output [1:0] ddr_ba,
 output ddr_cke,ddr_odt,ddr_cs_n,ddr_ras_n,ddr_cas_n,ddr_we_n,ddr_ck_p,ddr_ck_n,
 inout [1:0] ddr_dm,inout [15:0] ddr_dq,inout [1:0] ddr_dqs_p,ddr_dqs_n
);
 localparam N=1280*`PAXI_VIDEO_LINES*3/16;
 assign dhi_clk=ref_clk;assign cfg_clk=ref_clk;assign ddrphy_rst_n=sys_rst_n;
 integer cycle=0;
 reg [31:0] lfsr=32'h8727cafe;
 assign ddrphy_rdy=sys_rst_n && cycle>=1200;
 assign paxi_awready=ddrphy_rdy && (latency_video_tb.STRONG_STALL ?
  ((lfsr[0]||lfsr[7]) && cycle%113>7) : cycle%37!=11);
 assign paxi_wready=ddrphy_rdy && (latency_video_tb.STRONG_STALL ?
  ((lfsr[5]||lfsr[19]) && cycle%127>11) : cycle%43!=17);
 assign paxi_arready=ddrphy_rdy && (latency_video_tb.STRONG_STALL ?
  ((lfsr[3]||lfsr[13]) && cycle%149>5) : (cycle%29!=7 && cycle%29!=8)) && !hold_response;
 assign paxi_rlast=paxi_rvalid;
 reg [127:0] ram0[0:N+1023],ram1[0:N+1023],ram2[0:N+1023],ram3[0:N+1023];
 reg aw_pending=0,w_pending=0;
 reg [24:0] saved_aw;
 reg [127:0] saved_w;
 wire aw_hs=paxi_awvalid && paxi_awready;
 wire w_hs=paxi_wvalid && paxi_wready;
 wire ar_hs=paxi_arvalid && paxi_arready;
 wire commit_write=(aw_pending||aw_hs) && (w_pending||w_hs);
 wire [24:0] commit_addr=aw_pending?saved_aw:paxi_awaddr;
 wire [127:0] commit_data=w_pending?saved_w:paxi_wdata;
 reg [127:0] response[0:2047];
 integer due[0:2047],qhead=0,qtail=0,qcount=0;
 integer sa,ix,ar_count=0,aw_count=0,w_count=0,write_count=0,return_count=0;
 integer split_aw_first=0,split_w_first=0,ready_mismatch=0;
 reg hold_response=0,fault_injected=0;
 integer release_cycle=-1,fault_old_sequence=-1,fault_new_sequence=-1;
 integer returns_during_fifo_reset=0;
 function integer slot;input [24:0] a;begin slot=a<7000000?0:a<14000000?1:a<21000000?2:3;end endfunction
 function integer index;input [24:0] a;begin
  case(slot(a))0:index=a/8;1:index=(a-7000000)/8;2:index=(a-14000000)/8;3:index=(a-21000000)/8;endcase
 end endfunction
 always @(posedge ref_clk or negedge sys_rst_n)begin
  if(!sys_rst_n)begin
   cycle=0;lfsr<=32'h8727cafe;aw_pending=0;w_pending=0;
   qhead=0;qtail=0;qcount=0;paxi_rvalid<=0;paxi_rdata<=0;
   ar_count=0;aw_count=0;w_count=0;write_count=0;return_count=0;
   split_aw_first=0;split_w_first=0;ready_mismatch=0;
   hold_response=0;fault_injected=0;release_cycle=-1;
   fault_old_sequence=-1;fault_new_sequence=-1;returns_during_fifo_reset=0;
  end else begin
   cycle=cycle+1;lfsr<={lfsr[30:0],lfsr[31]^lfsr[21]^lfsr[1]^lfsr[0]};
   if(paxi_rvalid && latency_video_tb.vo.S_fifo_rst)returns_during_fifo_reset=returns_during_fifo_reset+1;
   if(paxi_arvalid && paxi_awready && !paxi_arready)ready_mismatch=ready_mismatch+1;
   if(aw_hs)begin
    if(aw_pending)$fatal(1,"duplicate AW while prior AW awaits W");
    aw_count=aw_count+1;if(!w_hs && !w_pending)split_aw_first=split_aw_first+1;
   end
   if(w_hs)begin
    if(w_pending)$fatal(1,"duplicate W while prior W awaits AW");
    if(!paxi_wlast || paxi_wstrb!==0)$fatal(1,"bad write LAST/mask");
    w_count=w_count+1;if(!aw_hs && !aw_pending)split_w_first=split_w_first+1;
   end
   if(commit_write)begin
    sa=slot(commit_addr);ix=index(commit_addr);
    if(ix<0 || ix>N+1023)$fatal(1,"write address outside image/prefetch");
    case(sa)0:ram0[ix]<=commit_data;1:ram1[ix]<=commit_data;2:ram2[ix]<=commit_data;3:ram3[ix]<=commit_data;endcase
    aw_pending=0;w_pending=0;write_count=write_count+1;
   end else begin
    if(aw_hs)begin aw_pending=1;saved_aw=paxi_awaddr;end
    if(w_hs)begin w_pending=1;saved_w=paxi_wdata;end
   end
   if(hold_response && latency_video_tb.vo.S_video_frame_start && release_cycle<0)begin
    release_cycle=cycle+3;fault_new_sequence=latency_video_tb.dut.read_sequence+1;
    $display("PAXI_FAULT_NEW_VS old_seq=%0d new_seq=%0d outstanding=%0d",fault_old_sequence,fault_new_sequence,latency_video_tb.dut.outstanding);
   end
   if(hold_response && release_cycle>=0 && cycle>=release_cycle)hold_response=0;
   paxi_rvalid<=0;
   if(qcount!=0 && due[qhead]<=cycle && !hold_response)begin
    if(!paxi_rready)$fatal(1,"production wrapper unexpectedly withdrew RREADY");
    paxi_rvalid<=1;paxi_rdata<=response[qhead];
    qhead=(qhead+1)%2048;qcount=qcount-1;return_count=return_count+1;
   end
   if(ar_hs)begin
    sa=slot(paxi_araddr);ix=index(paxi_araddr);
    if(ix<0 || ix>N+1023)$fatal(1,"read address outside image/prefetch");
    if(qcount>=2047)$fatal(1,"response queue overflow");
    case(sa)0:response[qtail]=ram0[ix];1:response[qtail]=ram1[ix];2:response[qtail]=ram2[ix];3:response[qtail]=ram3[ix];endcase
    due[qtail]=cycle+64+(ar_count%17);qtail=(qtail+1)%2048;qcount=qcount+1;ar_count=ar_count+1;
    // Negative reduced-height fixture: hold frame-end prefetch, stop further
    // AR acceptance, then release that ordered old response inside the next
    // VS-triggered output-FIFO reset. No DUT state is forced or modified.
    if(latency_video_tb.FAULT_VS_RETURN && !fault_injected &&
       latency_video_tb.dut.read_sequence>=7 && latency_video_tb.dut.read_words>=N)begin
     hold_response=1;fault_injected=1;fault_old_sequence=latency_video_tb.dut.read_sequence;
     $display("PAXI_FAULT_HOLD seq=%0d address=%0d",fault_old_sequence,paxi_araddr);
    end
   end
  end
 end
endmodule
