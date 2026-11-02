// The unchanged line controller wraps at IMG_WIDTH/4=320. Upper address bits
// are always zero. This allocation preserves the original one-clock read.
(* keep_hierarchy="true" *)
module awb_line_memory(input clka,wea,input [10:0] addra,input [95:0] dia,
 input clkb,input [10:0] addrb,output wire [95:0] dob);
`ifdef __ICARUS__
 reg [95:0] memory[0:511];reg [95:0] q;
 always @(posedge clka)if(wea)memory[addra[8:0]]<=dia;
 always @(posedge clkb)q<=memory[addrb[8:0]];
 assign dob=q;
`else
 PH1P_LOGIC_ERAM #(.DATA_WIDTH_A(96),.DATA_WIDTH_B(96),.ADDR_WIDTH_A(9),.ADDR_WIDTH_B(9),
  .DATA_DEPTH_A(512),.DATA_DEPTH_B(512),.MODE("DP"),.REGMODE_A("NOREG"),.REGMODE_B("NOREG"),
  .WRITEMODE_A("NORMAL"),.WRITEMODE_B("READBEFOREWRITE"),.CLKMODE("ASYNC"),.IMPLEMENT("20K(FAST)"),
  .ECC_ENCODE("DISABLE"),.ECC_DECODE("DISABLE"),.SSROVERCE("DISABLE"),
  .OREGSET_A("RESET"),.OREGSET_B("RESET"),.RESETMODE_A("ASYNC"),.RESETMODE_B("ASYNC"),
  .ASYNC_RESET_RELEASE_A("ASYNC"),.ASYNC_RESET_RELEASE_B("ASYNC"),.INIT_FILE("NONE"),.FILL_ALL("NONE"),.FORCE_KEEP("ON")) u_eram(
  .clka(clka),.clkb(clkb),.addra(addra[8:0]),.addrb(addrb[8:0]),.dia(dia),.dib(96'd0),
  .wea(wea),.web(1'b0),.cea(1'b1),.ceb(1'b1),.ocea(1'b0),.oceb(1'b0),
  .bea(1'b0),.beb(1'b0),.rsta(1'b0),.rstb(1'b0),.doa(),.dob(dob),
  .ecc_sbiterr(),.ecc_dbiterr(),.ecc_sbiterrinj(1'b0),.ecc_dbiterrinj(1'b0));
`endif
endmodule
