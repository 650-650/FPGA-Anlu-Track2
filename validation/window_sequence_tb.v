`timescale 1ns/1ns
module tb;
reg clk=0;always #5 clk=~clk;
reg rst=0;wire scl;tri1 sda;wire done,aedone;
uicfgcs500_720p dut(.I_clk(clk),.I_rst_n(rst),.I_ae_req(1'b0),.I_ae(16'd640),.I_ag(16'd16),
 .O_cam_scl(scl),.IO_cam_sda(sda),.O_cfg_done(done),.O_ae_cfg_done(aedone));
integer cycles=0;
always @(posedge clk)cycles=cycles+1;
initial begin
 repeat(20)@(negedge clk);rst=1;
 wait(done);repeat(20)@(negedge clk);
 if(dut.u_i2c.n!=118 || !aedone)$fatal(1,"wrong init count");
 if(dut.u_i2c.release_cycle-dut.u_i2c.stream_cycle<240000)$fatal(1,"stream delay shortened");
 $display("SENSOR_WINDOW_SEQUENCE_PASS writes=%0d normal_live_before_stream=1 window_shift_sensor_rows=64 delay_cycles=%0d",
 dut.u_i2c.n,dut.u_i2c.release_cycle-dut.u_i2c.stream_cycle);$finish;
end
initial begin #5000000;$fatal(1,"timeout");end
endmodule
// Transport handshake model only: validates the real config FSM/table.
// It does not simulate physical I2C ACK, sensor silicon or image output.
module uii2c #(parameter WMEN_LEN=4,RMEN_LEN=1,CLK_DIV=239)(
input I_clk,I_rstn,input[31:0]I_wr_data,input[7:0]I_wr_cnt,I_rd_cnt,
input I_iic_mode,I_iic_req,output O_iic_scl,inout IO_iic_sda,
output[7:0]O_rd_data,output reg O_iic_busy=0);
reg[23:0]expected[0:117];integer n=0,timer=0,stream_cycle=-1,release_cycle=-1;
reg seen_req=0;wire[23:0]word={I_wr_data[15:8],I_wr_data[23:16],I_wr_data[31:24]};
initial $readmemh("expected_init.hex",expected);
assign O_iic_scl=1;assign IO_iic_sda=1'bz;assign O_rd_data=0;
always @(posedge I_clk)begin
 if(!I_rstn)begin O_iic_busy<=0;timer<=0;seen_req<=0;end
 else begin
  if(!I_iic_req)seen_req<=0;
  if(I_iic_req && !seen_req && !O_iic_busy)begin
   if(n>=118)$fatal(1,"extra transaction");
   if(word!==expected[n] || I_wr_data[7:0]!==8'h6c || I_wr_cnt!=4 || I_rd_cnt!=0)
    $fatal(1,"transaction %0d mismatch got=%h expected=%h",n,word,expected[n]);
   if(word==24'h010001)stream_cycle=tb.cycles;
   if(word==24'h302d00)release_cycle=tb.cycles;
   n=n+1;seen_req<=1;O_iic_busy<=1;timer<=4;
  end else if(O_iic_busy)begin
   if(timer==0)O_iic_busy<=0;else timer<=timer-1;
  end
 end
end
endmodule
