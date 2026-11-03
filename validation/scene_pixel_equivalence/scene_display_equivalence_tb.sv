`timescale 1ns/1ps
module scene_display_equivalence_tb;
 reg clk=0,rst=0,overlay=0,bypass=0,cartoon=0,legacy=0;
 always #5 clk=~clk;
 reg [23:0] rgb=0;
 wire [23:0] mapped[0:4],old;
 wire [4:0] de,peer_de;
 wire [23:0] peer_mapped[0:4];
 integer peer_i;
 wire old_de;
 integer checks=0,v,r,g,b,j,changed[0:3],csv;
 reg [7:0] previous[0:4];
 genvar n;
 generate for(n=0;n<5;n=n+1)begin: presets
  localparam [2:0] LEVEL=n;
  display_contrast dut(.clk(clk),.rst_n(rst),.vs(1'b0),.hs(1'b0),.de(1'b1),
   .rgb(rgb),.overlay(overlay),.bypass(bypass),.cartoon(cartoon),.keep_legacy(legacy),.clear_level(LEVEL),
   .stat_vs(1'b0),.stat_de(1'b0),.stat_rgb(24'd0),.stat_enable(1'b0),
   .O_vs(),.O_hs(),.O_de(de[n]),.O_rgb(mapped[n]),.O_offset());
  teammate_display_contrast peer(.clk(clk),.rst_n(rst),.vs(1'b0),.hs(1'b0),.de(1'b1),
   .rgb(rgb),.overlay(overlay),.bypass(bypass),.cartoon(cartoon),.keep_legacy(legacy),.clear_level(LEVEL),
   .stat_vs(1'b0),.stat_de(1'b0),.stat_rgb(24'd0),.stat_enable(1'b0),
   .O_vs(),.O_hs(),.O_de(peer_de[n]),.O_rgb(peer_mapped[n]),.O_offset());
 end endgenerate
 reference_display_contrast reference(.clk(clk),.rst_n(rst),.vs(1'b0),.hs(1'b0),.de(1'b1),
  .rgb(rgb),.overlay(overlay),.bypass(bypass),.cartoon(cartoon),.keep_legacy(legacy),
  .stat_vs(1'b0),.stat_de(1'b0),.stat_rgb(24'd0),.stat_enable(1'b0),
  .O_vs(),.O_hs(),.O_de(old_de),.O_rgb(old),.O_offset());
 task check;input condition;input [511:0] reason;
  begin checks=checks+1;if(condition!==1'b1)begin $display("FAIL %s rgb=%h",reason,rgb);$fatal(1);end end
 endtask
 always @(posedge clk)begin
  #1;
  if(rst && old_de)begin
   check(de===peer_de,"display all five levels preserve teammate output timing");
   for(peer_i=0;peer_i<5;peer_i=peer_i+1)
    check(mapped[peer_i]===peer_mapped[peer_i],"display each level equals teammate exactly");
  end
 end
 initial begin
  csv=$fopen("display_effect_metrics.csv","w");
  $fwrite(csv,"input,level1,level2,level3,level4,level5\n");
  for(j=0;j<4;j=j+1)changed[j]=0;
  repeat(5)@(negedge clk);rst=1;repeat(6)@(negedge clk);
  for(v=0;v<256;v=v+1)begin
   rgb={3{v[7:0]}};repeat(4)@(negedge clk);
   check(mapped[2]===old,"default matches every original grey code");
   check(de=={5{old_de}} && old_de,"display timing unchanged");
   check(mapped[0]>=mapped[1] && mapped[1]>=mapped[2],"shadow lift ordering");
   if(v<128)check(mapped[2]>=mapped[3] && mapped[3]>=mapped[4],"strong contrast darkens shadows");
   if(v>=130)check(mapped[2]<=mapped[3] && mapped[3]<=mapped[4],"strong contrast lifts highlights");
   for(j=0;j<5;j=j+1)begin
    if(v>0)check(mapped[j][7:0]>=previous[j],"all tone responses are monotone");
    if(v==0 || v==255)check(mapped[j]==rgb,"black and white endpoints preserved");
    previous[j]=mapped[j][7:0];
   end
   for(j=0;j<4;j=j+1)if(mapped[j]!=mapped[j+1])changed[j]=changed[j]+1;
   $fwrite(csv,"%0d,%0d,%0d,%0d,%0d,%0d\n",v,mapped[0][7:0],mapped[1][7:0],mapped[2][7:0],mapped[3][7:0],mapped[4][7:0]);
  end
  for(j=0;j<4;j=j+1)check(changed[j]>=90,"adjacent clear presets change many tone codes");
  // Exhaustive 9x9x9 colour grid checks the common RGB delta and clipping.
  for(r=0;r<=256;r=r+32)for(g=0;g<=256;g=g+32)for(b=0;b<=256;b=b+32)begin
   rgb={(r==256?8'd255:r[7:0]),(g==256?8'd255:g[7:0]),(b==256?8'd255:b[7:0])};
   repeat(3)@(negedge clk);
   check(mapped[2]===old,"default preserves original coloured pixels");
   for(j=0;j<5;j=j+1)begin
    check((int'(mapped[j][23:16])-int'(mapped[j][15:8]))==(int'(rgb[23:16])-int'(rgb[15:8])) &&
          (int'(mapped[j][15:8])-int'(mapped[j][7:0]))==(int'(rgb[15:8])-int'(rgb[7:0])),
          "common gamut guard preserves RGB differences without wrap");
   end
  end
  rgb=24'hfff200;overlay=1;repeat(4)@(negedge clk);
  for(j=0;j<5;j=j+1)check(mapped[j]==rgb,"HUD and Logo protected");
  overlay=0;bypass=1;repeat(4)@(negedge clk);
  for(j=0;j<5;j=j+1)check(mapped[j]==rgb,"bypass protected");
  bypass=0;cartoon=1;repeat(4)@(negedge clk);
  for(j=0;j<5;j=j+1)check(mapped[j]==rgb,"cartoon finish protected");
  $fclose(csv);
  $display("SCENE_DISPLAY_EQUIVALENCE_PASS checks=%0d",checks);$finish;
 end
 initial begin #300000;$fatal(1,"display timeout");end
endmodule
