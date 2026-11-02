// Unity RGB transport with the exact V4 pixel scheduling. Scene colour is
// estimated after the display curve and applied in the HDMI colour-only branch.
module awb #(parameter IMG_HEIGHT=1080,parameter IMG_WIDTH=1920)(
 input I_wb_allow,I_wb_relearn,output O_wb_locked,input I_clk,I_rst_n,
 input I_tlast,I_tuser,input [95:0] I_tdata,input I_tvalid,output I_tready,
 output O_tlast,O_tuser,output [95:0] O_tdata,output O_tvalid,input O_tready
);
 reg [95:0] data0,data1,stage1,stage2;
 reg v0,v1,stage1_v,stage2_v;
 wire [95:0] delayed;wire delayed_v,unused_user;
 always @(posedge I_clk or negedge I_rst_n)begin
  if(!I_rst_n)begin data0<=0;data1<=0;v0<=0;v1<=0;stage1<=0;stage2<=0;stage1_v<=0;stage2_v<=0;end
  else begin
   data0<=I_tdata;data1<=data0;v0<=I_tvalid;v1<=v0;
   stage1<=delayed;stage1_v<=delayed_v;stage2_v<=stage1_v;
   if(stage1_v)stage2<=stage1;
  end
 end
 signal_delay_compact #(.IMG_HEIGHT(IMG_HEIGHT),.IMG_WIDTH(IMG_WIDTH),.DATA_WIDTH(96),.DELAY_CYCLE(50)) u_delay(
  .I_clk(I_clk),.I_rst_n(I_rst_n),.I_tuser(I_tuser),.I_valid(v1),.I_data(data1),
  .O_valid(delayed_v),.O_data(delayed),.O_tuser(unused_user));
 assign O_tvalid=stage2_v;assign O_tdata=O_tvalid?stage2:96'd0;
 assign O_tlast=!stage1_v && stage2_v;assign O_tuser=I_tuser;
 assign I_tready=O_tready;assign O_wb_locked=1'b1;
endmodule
