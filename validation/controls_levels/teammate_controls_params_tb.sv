`timescale 1ns/1ps
module controls_params_tb;
 reg clk=0,dc=0,rst=0,commit=0;
 always #5 clk=~clk;
 always #7 dc=~dc;
 reg [3:0] keys=15,sw=15;
 wire reset_n,osd,wb;
 wire [7:0] control;
 wire [11:0] levels;
 wire [5:0] colour;
 wire [19:0] received;
 integer checks=0,page,j,expected;
 reg [11:0] saved;
 fusion_controls #(.DEBOUNCE_CYCLES(3),.BOOT_CYCLES(6),.RESET_CYCLES(9),
  .K3_HOLD_CYCLES(100),.K4_HOLD_CYCLES(80)) dut(
  .I_clk(clk),.I_keys_n(keys),.I_switches(sw),.O_system_rst_n(reset_n),
  .O_control(control),.O_osd_enable(osd),.O_wb_toggle(wb),
  .O_color_control(colour),.O_style_levels(levels));
 fusion_control_cdc #(.WIDTH(20)) cdc(.I_source_clk(clk),.I_dest_clk(dc),
  .I_rst_n(rst),.I_commit(commit),.I_data({levels,control}),.O_data(received));
 task check;
  input condition;input [511:0] reason;
  begin checks=checks+1;if(condition!==1'b1)begin $display("FAIL %s",reason);$fatal(1);end end
 endtask
 task tick;input integer n;begin repeat(n)@(negedge clk);end endtask
 task press;input integer key;
  begin keys[key]=0;tick(16);keys[key]=1;tick(16);end
 endtask
 initial begin
  tick(20);rst=1;tick(12);
  check(levels=={4{3'd2}},"all four defaults are original/middle");
  sw=14;tick(16);
  check(control[7:3]==5'b00101,"SW1 enters cartoon");
  for(page=0;page<4;page=page+1)begin
   if(control[4:3]!=page)press(page);
   check(control[4:3]==page && levels[page*3+:3]==2,"mode selection preserves default");
   for(j=0;j<5;j=j+1)begin
    saved=levels;expected=(j+3)%5;press(page);
    check(levels[page*3+:3]==expected,"repeat key cycles all five presets");
    saved[page*3+:3]=expected;
    check(levels==saved,"other mode parameters remain unchanged");
   end
  end
  press(3);check(levels[11:9]==3,"edge preset remembered");
  sw=6;tick(16);saved=levels;
  check(osd && control[4:3]==3,"SW4 preserves selected page");
  sw=15;tick(16);press(1);
  check(colour[5:2]==4'hf && levels==saved,"WB temperature action unchanged");
  sw=13;tick(16);press(2);press(2);
  check(control[4:3]==2 && control[2] && levels==saved,"alarm mute action unchanged");
  check(received==0,"CDC cannot commit outside a frame boundary");
  commit=1;tick(30);commit=0;tick(30);
  check(received=={levels,control},"CDC transfers complete parameter bundle");
  saved=received[19:8];sw=14;tick(16);press(1);
  check(received[19:8]==saved,"new parameter held until commit");
  commit=1;tick(30);commit=0;tick(30);
  check(received=={levels,control},"second coherent transfer");
  keys[3]=0;tick(95);keys[3]=1;tick(16);
  check(wb && colour==0,"K4 hold retains WB relearn");
  check(control[4:3]==1,"K4 hold cannot become a short press");
  keys[2]=0;tick(130);keys[2]=1;tick(20);
  check(levels=={4{3'd2}} && control[4:3]==1,"K3 hold restores all defaults");
  saved=levels;keys[1]=0;tick(1);keys[1]=1;tick(16);
  check(levels==saved,"contact bounce ignored");
  $display("CONTROLS_PARAMS_PASS checks=%0d",checks);$finish;
 end
 initial begin #200000;$fatal(1,"controls timeout");end
endmodule
