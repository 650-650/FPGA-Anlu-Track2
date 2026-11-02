// Lab 1.3: sampled linear RGB metering with a single-entry CDC mailbox.
// Source payload is immutable until destination acknowledgement returns.
module ae_stats_cdc #(parameter MIN_SAMPLES=4096)(
 input src_clk,dst_clk,rst_n,
 input [95:0] rgb, input valid,sof,
 output reg stats_valid, output reg [31:0] stats_sum,
 output reg [19:0] stats_count,stats_hot
);
reg [31:0] sum;
reg [19:0] count,hot;
reg [3:0] phase;
reg sof_d;
wire frame_edge=sof && !sof_d;
wire [9:0] weighted={2'b0,rgb[23:16]}+{1'b0,rgb[15:8],1'b0}+{2'b0,rgb[7:0]};
wire [7:0] luminance=weighted[9:2];
wire highlight=(rgb[23:16]>=232)||(rgb[15:8]>=232)||(rgb[7:0]>=232);
reg [71:0] payload_hold;
reg req,ack;
(* ASYNC_REG="TRUE" *) reg [1:0] ack_sync;
(* ASYNC_REG="TRUE" *) reg [3:0] req_sync;
(* ASYNC_REG="TRUE" *) reg [71:0] payload_meta,payload_sync;
always @(posedge src_clk or negedge rst_n) begin
 if(!rst_n) begin
  sum<=0;count<=0;hot<=0;phase<=0;sof_d<=0;payload_hold<=0;req<=0;ack_sync<=0;
 end else begin
  sof_d<=sof; ack_sync<={ack_sync[0],ack};
  if(frame_edge) begin
   if(count>=MIN_SAMPLES && req==ack_sync[1]) begin
    payload_hold<={sum,count,hot}; req<=~req;
   end
   sum<=valid?{24'd0,luminance}:32'd0;
   count<=valid?20'd1:20'd0;
   hot<=valid&&highlight?20'd1:20'd0;
   phase<=valid?4'd1:4'd0;
  end else if(valid) begin
   phase<=phase+1'b1;
   if(phase==0 && !(&count)) begin
    sum<=sum+{24'd0,luminance};count<=count+1'b1;
    if(highlight)hot<=hot+1'b1;
   end
  end
 end
end
always @(posedge dst_clk or negedge rst_n) begin
 if(!rst_n) begin
  req_sync<=0;payload_meta<=0;payload_sync<=0;ack<=0;
  stats_valid<=0;stats_sum<=0;stats_count<=0;stats_hot<=0;
 end else begin
  req_sync<={req_sync[2:0],req};
  payload_meta<=payload_hold;payload_sync<=payload_meta;
  stats_valid<=0;
  if(req_sync[3]!=ack) begin
   {stats_sum,stats_count,stats_hot}<=payload_sync;
   stats_valid<=1;ack<=req_sync[3];
  end
 end
end
endmodule

// SC500CS exposure is measured in half-lines: [3, 2*VTS-10=1990].
// Gain-table index 16=1x, 48=2x, 80=4x. No digital gain is added.
module ae_auto_control #(parameter SETTLE_FRAMES=4, parameter BUTTON_CYCLES=12000000)(
 input clk,rst_n,cam_done,ae_done,
 input stats_valid,input [31:0] stats_sum,input [19:0] stats_count,stats_hot,
 input [1:0] buttons_n,
 output reg request,output reg [15:0] exposure,gain_index,
 output reg wb_allow, output wire wb_relearn
);
localparam BOOT=0,WAIT_BUSY=1,WAIT_DONE=2,SETTLE=3,TRACK=4;
reg [2:0] state;
reg [3:0] frames_left;
(* ASYNC_REG="TRUE" *) reg [1:0] btn_meta,btn_sync;
reg [23:0] button_count;
assign wb_relearn=(button_count>=BUTTON_CYCLES);
wire [31:0] n={12'd0,stats_count};
wire severe=(stats_hot>(stats_count>>3)) || (stats_sum>n*32'd160);
wire too_bright=severe || (stats_hot>(stats_count>>6)) || (stats_sum>n*32'd88);
wire too_dark=(stats_sum<n*32'd56) && (stats_hot<=(stats_count>>8));
wire [15:0] step=(exposure>>3)==0?16'd1:(exposure>>3);
reg [15:0] wanted_exp,wanted_gain;
always @* begin
 wanted_exp=exposure;wanted_gain=gain_index;
 if(too_bright) begin
  if(gain_index>16) begin
   if(severe) wanted_gain=gain_index>32?gain_index-16:16;
   else wanted_gain=gain_index>20?gain_index-4:16;
  end else if(exposure>3) begin
   if(severe) wanted_exp=exposure>6?(exposure>>1):3;
   else wanted_exp=exposure>(step+3)?exposure-step:3;
  end
 end else if(too_dark) begin
  if(exposure<1990) wanted_exp=(exposure+step)>1990?1990:exposure+step;
  else if(gain_index<80) wanted_gain=gain_index>76?80:gain_index+4;
 end
end
always @(posedge clk or negedge rst_n) begin
 if(!rst_n) begin
  btn_meta<=2'b11;btn_sync<=2'b11;button_count<=0;
 end else begin
  btn_meta<=buttons_n;btn_sync<=btn_meta;
  if(btn_sync==0) begin
   if(button_count<BUTTON_CYCLES)button_count<=button_count+1'b1;
  end else button_count<=0;
 end
end
always @(posedge clk or negedge rst_n) begin
 if(!rst_n) begin
  request<=0;exposure<=640;gain_index<=16;state<=BOOT;frames_left<=0;wb_allow<=0;
 end else begin
  request<=0;
  case(state)
   BOOT: if(cam_done && ae_done && stats_valid && stats_count!=0) begin
    request<=1;state<=WAIT_BUSY;wb_allow<=0;
   end
   WAIT_BUSY: if(!ae_done) state<=WAIT_DONE;
   WAIT_DONE: if(ae_done) begin frames_left<=SETTLE_FRAMES;state<=SETTLE; end
   SETTLE: if(stats_valid) begin
    if(frames_left<=1)state<=TRACK;
    else frames_left<=frames_left-1'b1;
   end
   TRACK: if(stats_valid && stats_count!=0 && cam_done && ae_done) begin
    if(wanted_exp!=exposure || wanted_gain!=gain_index) begin
     exposure<=wanted_exp;gain_index<=wanted_gain;request<=1;
     state<=WAIT_BUSY;wb_allow<=0;
    end else wb_allow<=1;
   end
   default:begin state<=BOOT;wb_allow<=0;end
  endcase
 end
end
endmodule
