// Values are copied byte-for-byte from the accepted V3 display curve.
// TD uses an explicit dual-read ERAM; Icarus cannot execute the encrypted
// vendor model, so its branch models the same one-clock read interface.
(* keep_hierarchy="true" *) module image_srgb_pair_rom(input wire clk,input wire [7:0] a,b,output wire [7:0] qa,qb);
`ifdef __ICARUS__
reg [7:0] memory[0:255];
reg [7:0] ra,rb;
initial $readmemb("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/user_source/hdl_source/curve_srgb.dat",memory);
always @(posedge clk)begin ra<=memory[a];rb<=memory[b];end
assign qa=ra;assign qb=rb;
`else
PH1P_LOGIC_ERAM #(.DATA_WIDTH_A(8),.DATA_WIDTH_B(8),.ADDR_WIDTH_A(8),.ADDR_WIDTH_B(8),
 .DATA_DEPTH_A(256),.DATA_DEPTH_B(256),.MODE("DP"),.REGMODE_A("NOREG"),.REGMODE_B("NOREG"),
 .WRITEMODE_A("NORMAL"),.WRITEMODE_B("NORMAL"),.CLKMODE("SYNC"),.IMPLEMENT("20K(FAST)"),
 .FORCE_KEEP("ON"),.INIT_FILE("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/user_source/hdl_source/curve_srgb.dat")) u_eram(
 .clka(clk),.clkb(clk),.addra(a),.addrb(b),.dia(8'd0),.dib(8'd0),
 .wea(1'b0),.web(1'b0),.cea(1'b1),.ceb(1'b1),.ocea(1'b1),.oceb(1'b1),
 .bea(1'b0),.beb(1'b0),.rsta(1'b0),.rstb(1'b0),.doa(qa),.dob(qb),
 .ecc_sbiterr(),.ecc_dbiterr(),.ecc_sbiterrinj(1'b0),.ecc_dbiterrinj(1'b0));
`endif
endmodule

// Values are copied byte-for-byte from the accepted V3 display curve.
// TD uses an explicit dual-read ERAM; Icarus cannot execute the encrypted
// vendor model, so its branch models the same one-clock read interface.
(* keep_hierarchy="true" *) module image_gain_pair_rom(input wire clk,input wire [7:0] a,b,output wire [16:0] qa,qb);
`ifdef __ICARUS__
reg [16:0] memory[0:255];
reg [16:0] ra,rb;
initial $readmemb("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/user_source/hdl_source/curve_gain_scaled.dat",memory);
always @(posedge clk)begin ra<=memory[a];rb<=memory[b];end
assign qa=ra;assign qb=rb;
`else
PH1P_LOGIC_ERAM #(.DATA_WIDTH_A(17),.DATA_WIDTH_B(17),.ADDR_WIDTH_A(8),.ADDR_WIDTH_B(8),
 .DATA_DEPTH_A(256),.DATA_DEPTH_B(256),.MODE("DP"),.REGMODE_A("NOREG"),.REGMODE_B("NOREG"),
 .WRITEMODE_A("NORMAL"),.WRITEMODE_B("NORMAL"),.CLKMODE("SYNC"),.IMPLEMENT("20K(FAST)"),
 .FORCE_KEEP("ON"),.INIT_FILE("D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/user_source/hdl_source/curve_gain_scaled.dat")) u_eram(
 .clka(clk),.clkb(clk),.addra(a),.addrb(b),.dia(17'd0),.dib(17'd0),
 .wea(1'b0),.web(1'b0),.cea(1'b1),.ceb(1'b1),.ocea(1'b1),.oceb(1'b1),
 .bea(1'b0),.beb(1'b0),.rsta(1'b0),.rstb(1'b0),.doa(qa),.dob(qb),
 .ecc_sbiterr(),.ecc_dbiterr(),.ecc_sbiterrinj(1'b0),.ecc_dbiterrinj(1'b0));
`endif
endmodule
