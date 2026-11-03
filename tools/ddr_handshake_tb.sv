`timescale 1ns/1ps
module transport_path #(parameter LEGACY=0)(
 input clk,rst,uw,ur,input [24:0] ua,input [127:0] ud,
 output user_ready,ret_valid,ret_end,output [127:0] ret_data,
 output aw_hs,ar_hs,w_hs,output [24:0] aw_addr,ar_addr,
 output [127:0] w_data,output w_last,
 output cmd_valid,data_valid,output [2:0] cmd,
 output [24:0] cmd_addr,output [127:0] cmd_data,
 output selected_ready,data_ready,head_empty,pop
);
 wire app_en,app_rdy,app_wren,app_wrdy,app_end,rd_valid,rd_end;
 wire [24:0] app_addr;wire [2:0] app_cmd;
 wire [127:0] app_data,rd_data;wire [31:0] app_mask;
 assign cmd_valid=app_en;assign data_valid=app_wren;assign cmd=app_cmd;
 assign cmd_addr=app_addr;assign cmd_data=app_data;
 assign selected_ready=app_rdy;assign data_ready=app_wrdy;
 assign ret_end=rd_end;
 generate if(LEGACY)begin: legacy
  legacy_mc_to_user_interface mc(
   .I_clk(clk),.I_rst_n(rst),.I_ddr_user_wr_en(uw),.I_ddr_user_rd_en(ur),.I_ddr_user_addr(ua),.I_ddr_user_wr_data(ud),
   .O_ddr_user_ready(user_ready),.O_ddr_user_rd_valid(ret_valid),.O_ddr_user_rd_data(ret_data),
   .O_mc_app_en(app_en),.O_mc_app_addr(app_addr),.O_mc_app_cmd(app_cmd),.I_mc_app_rdy(app_rdy),
   .O_mc_app_wdf_wren(app_wren),.O_mc_app_wdf_data(app_data),.O_mc_app_wdf_end(app_end),.O_mc_app_wdf_mask(app_mask),
   .I_mc_app_wdf_rdy(app_wrdy),.I_mc_app_rd_data(rd_data),.I_mc_app_rd_data_end(rd_end),.I_mc_app_rd_data_valid(rd_valid));
  legacy_ph1p35_324_ddr_wrapper wrap(
   .I_sys_clk(clk),.I_sys_rst_n(rst),.O_ddr_clk(),.O_init_calib_complete(),
   .I_mc_app_addr(app_addr),.I_mc_app_cmd(app_cmd),.I_mc_app_en(app_en),.I_mc_app_wdf_data(app_data),
   .I_mc_app_wdf_end(app_end),.I_mc_app_wdf_mask(app_mask[15:0]),.I_mc_app_wdf_wren(app_wren),
   .O_mc_app_rd_data(rd_data),.O_mc_app_rd_data_end(rd_end),.O_mc_app_rd_data_valid(rd_valid),
   .O_mc_app_rdy(app_rdy),.O_mc_app_wdf_rdy(app_wrdy));
  assign aw_hs=wrap.paxi_awvalid && wrap.paxi_awready;
  assign ar_hs=wrap.paxi_arvalid && wrap.paxi_arready;
  assign w_hs=wrap.paxi_wvalid && wrap.paxi_wready;
  assign aw_addr=wrap.paxi_awaddr;assign ar_addr=wrap.paxi_araddr;
  assign w_data=wrap.paxi_wdata;assign w_last=wrap.paxi_wlast;
  assign head_empty=mc.S_fifo_empty;assign pop=mc.S_fifo_rd_en;
 end else begin: fixed_path
  mc_to_user_interface mc(
   .I_clk(clk),.I_rst_n(rst),.I_ddr_user_wr_en(uw),.I_ddr_user_rd_en(ur),.I_ddr_user_addr(ua),.I_ddr_user_wr_data(ud),
   .O_ddr_user_ready(user_ready),.O_ddr_user_rd_valid(ret_valid),.O_ddr_user_rd_data(ret_data),
   .O_mc_app_en(app_en),.O_mc_app_addr(app_addr),.O_mc_app_cmd(app_cmd),.I_mc_app_rdy(app_rdy),
   .O_mc_app_wdf_wren(app_wren),.O_mc_app_wdf_data(app_data),.O_mc_app_wdf_end(app_end),.O_mc_app_wdf_mask(app_mask),
   .I_mc_app_wdf_rdy(app_wrdy),.I_mc_app_rd_data(rd_data),.I_mc_app_rd_data_end(rd_end),.I_mc_app_rd_data_valid(rd_valid));
  ph1p35_324_ddr_wrapper wrap(
   .I_sys_clk(clk),.I_sys_rst_n(rst),.O_ddr_clk(),.O_init_calib_complete(),
   .I_mc_app_addr(app_addr),.I_mc_app_cmd(app_cmd),.I_mc_app_en(app_en),.I_mc_app_wdf_data(app_data),
   .I_mc_app_wdf_end(app_end),.I_mc_app_wdf_mask(app_mask[15:0]),.I_mc_app_wdf_wren(app_wren),
   .O_mc_app_rd_data(rd_data),.O_mc_app_rd_data_end(rd_end),.O_mc_app_rd_data_valid(rd_valid),
   .O_mc_app_rdy(app_rdy),.O_mc_app_wdf_rdy(app_wrdy));
  assign aw_hs=wrap.paxi_awvalid && wrap.paxi_awready;
  assign ar_hs=wrap.paxi_arvalid && wrap.paxi_arready;
  assign w_hs=wrap.paxi_wvalid && wrap.paxi_wready;
  assign aw_addr=wrap.paxi_awaddr;assign ar_addr=wrap.paxi_araddr;
  assign w_data=wrap.paxi_wdata;assign w_last=wrap.paxi_wlast;
  assign head_empty=mc.S_fifo_empty;assign pop=mc.S_fifo_rd_en;
 end endgenerate
endmodule

module handshake_tb;
 reg clk=0;always #7.5 clk=~clk;
 reg rst=0,uw=0,ur=0;reg [24:0] ua=0;reg [127:0] ud=0;
 reg ctl_aw=1,ctl_ar=1,ctl_w=1,cal_ready=1;
 wire nr,nrv,nre,nah,nrh,nwh,nwl,ncv,ndv,ncr,ndr,nempty,npop;
 wire ory,orv,ore,oah,orh,owh,owl,ocv,odv,ocr,odr,oempty,opop;
 wire [127:0] nrd,nwd,ncd,ord,owd,ocd;
 wire [24:0] naa,nra,nca,oaa,ora,oca;
 wire [2:0] nc,oc;
 transport_path np(clk,rst,uw,ur,ua,ud,nr,nrv,nre,nrd,nah,nrh,nwh,naa,nra,nwd,nwl,ncv,ndv,nc,nca,ncd,ncr,ndr,nempty,npop);
 transport_path #(.LEGACY(1)) oldp(clk,rst,uw,ur,ua,ud,ory,orv,ore,ord,oah,orh,owh,oaa,ora,owd,owl,ocv,odv,oc,oca,ocd,ocr,odr,oempty,opop);
 integer exp_count=0,exp_writes=0,exp_reads=0;
 reg exp_write[0:60099];reg [24:0] exp_addr[0:60099];
 reg [127:0] exp_wdata[0:60099],exp_rdata[0:60099];
 integer ncmd=0,nwrite=0,nread=0,ocmd=0,owrite=0,oread=0,npops=0,opops=0;
 reg compare_old=0;integer random_mode=0,cycles=0,common_cycles=0,stable_checks=0;
 reg [31:0] lfsr=32'h1234cafe;
 reg prev_cmd_stall=0,prev_data_stall=0;reg [2:0] prev_cmd;
 reg [24:0] prev_addr;reg [127:0] prev_data;
 reg [10:0] new_outstanding=0,old_outstanding=0;
 integer tested=0;
 always @(negedge clk)begin
  cycles=cycles+1;
  if(random_mode!=0)begin
   lfsr={lfsr[30:0],lfsr[31]^lfsr[21]^lfsr[1]^lfsr[0]};
   if(random_mode==2)begin ctl_aw=lfsr[0]||lfsr[5];ctl_ar=ctl_aw;ctl_w=ctl_aw;end
   else begin
    ctl_aw=(lfsr[0]||lfsr[8]) && cycles%113>17;
    ctl_ar=(lfsr[3]||lfsr[13]) && cycles%149>23;
    ctl_w=(lfsr[7]||lfsr[21]) && cycles%127>31;
   end
  end
 end
 always @(posedge clk or negedge rst)begin
  if(!rst)begin
   ncmd=0;nwrite=0;nread=0;ocmd=0;owrite=0;oread=0;npops=0;opops=0;
   prev_cmd_stall=0;prev_data_stall=0;new_outstanding<=0;old_outstanding<=0;
  end else begin
   // Same arithmetic used by the production observer's outstanding tracker.
   case({ur,nrv})2'b10:if(new_outstanding!=2047)new_outstanding<=new_outstanding+1'b1;
    2'b01:if(new_outstanding!=0)new_outstanding<=new_outstanding-1'b1;default:begin end endcase
   case({ur,orv})2'b10:if(old_outstanding!=2047)old_outstanding<=old_outstanding+1'b1;
    2'b01:if(old_outstanding!=0)old_outstanding<=old_outstanding-1'b1;default:begin end endcase
   if(prev_cmd_stall)begin
    if(!ncv || nc!==prev_cmd || nca!==prev_addr)$fatal(1,"command changed before handshake");
    stable_checks=stable_checks+1;
   end
   if(prev_data_stall)begin
    if(!ndv || ncd!==prev_data)$fatal(1,"write data changed before handshake");
    stable_checks=stable_checks+1;
   end
   prev_cmd_stall=ncv&&!ncr;prev_data_stall=ndv&&!ndr;
   prev_cmd=nc;prev_addr=nca;prev_data=ncd;
   if(nah || nrh)begin
    if(nah && nrh)$fatal(1,"both address channels accepted one head");
    if(ncmd>=exp_count || nah!==exp_write[ncmd] || (nah?naa:nra)!==exp_addr[ncmd])
     $fatal(1,"new command mismatch index=%0d gotwrite=%0b address=%h expected=%h",ncmd,nah,nah?naa:nra,exp_addr[ncmd]);
    ncmd=ncmd+1;
   end
   if(nwh)begin
    if(nwrite>=exp_writes || nwd!==exp_wdata[nwrite] || !nwl)$fatal(1,"new W data mismatch index=%0d",nwrite);
    nwrite=nwrite+1;
   end
   if(nrv)begin
    if(nread>=exp_reads || nrd!==exp_rdata[nread] || nre!==1'b1)$fatal(1,"new read response mismatch index=%0d",nread);
    nread=nread+1;
   end
   if(compare_old)begin
    common_cycles=common_cycles+1;
    if({nah,nrh,nwh}!=={oah,orh,owh})$fatal(1,"common ready changed handshake cycle");
    if(nah && naa!==oaa || nrh && nra!==ora || nwh && nwd!==owd)$fatal(1,"common ready changed accepted payload");
    if(npop!==opop || nr!==ory)$fatal(1,"common ready changed FIFO pop/readiness cycle");
    if(nrv!==orv || nrv && nrd!==ord)$fatal(1,"common ready changed response cycle");
   end
   if(oah || orh)ocmd=ocmd+1;
   if(owh)owrite=owrite+1;
   if(orv)oread=oread+1;
   if(npop)npops=npops+1;
   if(opop)opops=opops+1;
  end
 end
 function [127:0] data_for;input integer i;begin
  data_for={32'(i),32'(i^32'hdeadbeef),32'(i*17+3),32'(~i)};
 end endfunction
 task reset_case;input integer cmp,cal;
  begin
   @(negedge clk);rst=0;uw=0;ur=0;random_mode=0;ctl_aw=1;ctl_ar=1;ctl_w=1;cal_ready=cal;
   compare_old=cmp;exp_count=0;exp_writes=0;exp_reads=0;
   repeat(12)@(negedge clk);rst=1;repeat(5)@(negedge clk);
  end
 endtask
 task send;input integer wr,id;
  begin
   @(negedge clk);
   while(!nr || compare_old && !ory)@(negedge clk);
   ua=25'(id*8);ud=data_for(id);uw=wr;ur=!wr;
   exp_write[exp_count]=wr;exp_addr[exp_count]=ua;exp_count=exp_count+1;
   if(wr)begin exp_wdata[exp_writes]=ud;exp_writes=exp_writes+1;end
   else begin exp_rdata[exp_reads]={4{7'd0,ua}};exp_reads=exp_reads+1;end
   @(negedge clk);uw=0;ur=0;
  end
 endtask
 task drain;
  integer wait_cycles;
  begin
   @(negedge clk);random_mode=0;ctl_aw=1;ctl_ar=1;ctl_w=1;
   wait_cycles=0;
   while((ncmd!=exp_count || nwrite!=exp_writes || nread!=exp_reads || !nempty) && wait_cycles<10000)begin
    @(negedge clk);wait_cycles=wait_cycles+1;
   end
   if(ncmd!=exp_count || nwrite!=exp_writes || nread!=exp_reads || !nempty)
    $fatal(1,"new transport did not drain commands=%0d/%0d W=%0d/%0d R=%0d/%0d",ncmd,exp_count,nwrite,exp_writes,nread,exp_reads);
   repeat(40)@(negedge clk);
   if(ncmd!=exp_count || nwrite!=exp_writes || nread!=exp_reads || !nempty || new_outstanding!=0)
    $fatal(1,"new duplicate/stale transfer after drain");
  end
 endtask
 integer i;
 initial begin
  reset_case(0,1);
  ctl_ar=0;send(0,1);repeat(32)@(negedge clk);
  if(opops!=1 || npops!=0 || ocmd!=0 || ncmd!=0)$fatal(1,"legacy lost-read fixture did not separate paths");
  ctl_ar=1;drain;
  for(i=2;i<=101;i=i+1)send(0,i);
  drain;repeat(4096)@(negedge clk);
  if(old_outstanding!=1 || new_outstanding!=0 || oread!=100 || nread!=101)
   $fatal(1,"lost-read offset did not persist old=%0d new=%0d",old_outstanding,new_outstanding);
  $display("CASE_PASS old_wrapper_loses_one_AR old_outstanding=%0d new_outstanding=%0d observed_idle_clocks=4096",old_outstanding,new_outstanding);tested=tested+1;

  reset_case(0,1);ctl_w=0;send(1,201);repeat(30)@(negedge clk);
  if(ncmd!=1 || nwrite!=0 || npops!=0 || ncv || !ndv)$fatal(1,"AW-first state wrong");
  ctl_w=1;drain;$display("CASE_PASS AW_first_no_duplicate");tested=tested+1;

  reset_case(0,1);ctl_aw=0;send(1,301);repeat(30)@(negedge clk);
  if(ncmd!=0 || nwrite!=1 || npops!=0 || !ncv || ndv)$fatal(1,"W-first state wrong");
  ctl_aw=1;drain;$display("CASE_PASS W_first_no_duplicate");tested=tested+1;

  reset_case(0,1);ctl_aw=0;ctl_w=0;send(0,401);repeat(30)@(negedge clk);
  if(ncmd!=1 || nread!=1 || npops!=1)$fatal(1,"AR incorrectly depends on AW/W ready");
  drain;$display("CASE_PASS AR_independent_of_write_ready");tested=tested+1;

  reset_case(1,1);random_mode=2;
  for(i=0;i<5000;i=i+1)send((i%7)!=0,1000+i);
  drain;if(ocmd!=ncmd || owrite!=nwrite || oread!=nread)$fatal(1,"common ready totals differ");
  $display("CASE_PASS common_ready_cycle_equivalence transactions=%0d compared_clocks=%0d",exp_count,common_cycles);tested=tested+1;

  reset_case(0,0);
  for(i=0;i<256;i=i+1)send(i%2,8000+i);
  repeat(200)@(negedge clk);
  if(ncmd!=0 || nwrite!=0 || nread!=0 || npops!=0)$fatal(1,"transfer before calibration ready");
  cal_ready=1;drain;$display("CASE_PASS delayed_calibration_queued_transactions=%0d",exp_count);tested=tested+1;

  reset_case(0,1);ctl_w=0;send(1,9000);repeat(20)@(negedge clk);
  if(ncmd!=1 || nwrite!=0)$fatal(1,"reset fixture not partially accepted");
  reset_case(0,0);repeat(20)@(negedge clk);cal_ready=1;
  for(i=0;i<64;i=i+1)send(i%2,10000+i);
  drain;$display("CASE_PASS reset_clears_partial_AW_and_fifo");tested=tested+1;

  reset_case(0,1);ctl_aw=0;send(1,11000);repeat(20)@(negedge clk);
  if(ncmd!=0 || nwrite!=1)$fatal(1,"W reset fixture not partially accepted");
  reset_case(0,0);repeat(20)@(negedge clk);cal_ready=1;
  for(i=0;i<64;i=i+1)send(i%2,12000+i);
  drain;$display("CASE_PASS reset_clears_partial_W_and_fifo");tested=tested+1;

  reset_case(0,1);random_mode=1;
  for(i=0;i<50000;i=i+1)send((i*13%17)>5,20000+i);
  drain;
  $display("CASE_PASS random_independent_ready transactions=%0d commands=%0d writes=%0d reads=%0d stable_checks=%0d",exp_count,ncmd,nwrite,nread,stable_checks);tested=tested+1;
  $display("DDR_HANDSHAKE_PASS cases=%0d",tested);$finish;
 end
 initial begin #30000000;$fatal(1,"watchdog");end
endmodule
