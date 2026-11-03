`timescale 1ns/1ps
module scene_style_production_width_tb;
 localparam W=1280,H=12;
 reg clk=0,rst=0;
 always #5 clk=~clk;
 reg [1:0] mode=0;
 reg [2:0] request_level=2;
 reg valid=0,user=0,last=0,compare_default=1;
 reg [95:0] pixels=0;
 wire [95:0] rendered[0:4],old;
 wire [4:0] vv,uu,ll,pv,pu,pl;
 wire [95:0] peer_rendered[0:4];
 integer peer_i;
 wire ov,ou,ol;
 genvar n;
 generate for(n=0;n<5;n=n+1)begin: presets
  wire [2:0] requested=n==2?request_level:n;
  stylize_v5_96 #(.IMG_WIDTH(W),.IMG_HEIGHT(H)) dut(
   .I_clk(clk),.I_rst_n(rst),.I_mode(mode),.I_level(requested),
   .I_tvalid(valid),.I_tuser(user),.I_tlast(last),.I_tdata(pixels),
   .I_edge_data(96'd0),.I_tready(1'b1),.O_tdata(rendered[n]),
   .O_tvalid(vv[n]),.O_tuser(uu[n]),.O_tlast(ll[n]),.O_tready());
  teammate_stylize_v5_96 #(.IMG_WIDTH(W),.IMG_HEIGHT(H)) peer(
   .I_clk(clk),.I_rst_n(rst),.I_mode(mode),.I_level(requested),
   .I_tvalid(valid),.I_tuser(user),.I_tlast(last),.I_tdata(pixels),
   .I_edge_data(96'd0),.I_tready(1'b1),.O_tdata(peer_rendered[n]),
   .O_tvalid(pv[n]),.O_tuser(pu[n]),.O_tlast(pl[n]),.O_tready());
 end endgenerate
 reference_stylize_v5_96 #(.IMG_WIDTH(W),.IMG_HEIGHT(H)) reference(
  .I_clk(clk),.I_rst_n(rst),.I_mode(mode),.I_tvalid(valid),.I_tuser(user),.I_tlast(last),
  .I_tdata(pixels),.I_edge_data(96'd0),.I_tready(1'b1),.O_tdata(old),
  .O_tvalid(ov),.O_tuser(ou),.O_tlast(ol),.O_tready());
 integer checks=0,frame_index=-1,out_count=0,preset,p,f,scene,y,g,v;
 integer differences[0:3],absolute_delta[0:3],total_pixels,fd[0:4],metrics;
 integer sample_y,sample_x;
 reg dump=0;
 function [23:0] sample;
  input integer sc,xx,yy;
  integer value,r,green,b;
  begin
   case(sc)
    0:begin value=xx*255/(W-1);r=value;green=value;b=value;end
    1:begin value=12+xx*70/W+((yy/8)%2)*8;r=value;green=value;b=value;end
    2:begin value=160+xx*85/W+((yy/8)%2)*10;r=value;green=value;b=value;end
    3:begin value=36+(xx/16)*22+((yy/12)%2)*6;r=value;green=value;b=value;end
    4:begin value=(xx>32 && xx<96 && yy>10 && yy<38)?200:55;
      r=value;green=(value*3)/4;b=value/2;end
    default:begin value=100+((xx/4+yy/4)%2)*18+(xx%7);
      r=value;green=value+10;b=value-10;end
   endcase
   sample={r[7:0],green[7:0],b[7:0]};
  end
 endfunction
 task check;input condition;input [511:0] reason;
  begin checks=checks+1;if(condition!==1'b1)begin
   $display("FAIL %s mode=%0d scene=%0d frame=%0d beat=%0d",reason,mode,scene,frame_index,out_count);$fatal(1);end end
 endtask
 always @(posedge clk)begin
  #1;
  if(rst)begin
   check(vv=={5{ov}} && uu=={5{ou}} && ll=={5{ol}},"all presets preserve valid/SOF/EOL timing");
   check(vv===pv && uu===pu && ll===pl,"all five levels preserve teammate valid/SOF/EOL on the exact cycle");
   if(ov)begin
    for(peer_i=0;peer_i<5;peer_i=peer_i+1)
     check(rendered[peer_i]===peer_rendered[peer_i],"each integrated level equals corresponding teammate pixel on exact cycle");
    if(compare_default)check(rendered[2]===old,"default matches untouched V15 pixel for pixel");
    if(mode==0)for(preset=0;preset<5;preset=preset+1)
     check(rendered[preset]===old,"clear path remains bit-exact before display stage");
    if(frame_index==1 && compare_default)begin
     sample_y=out_count/(W/4);sample_x=(out_count%(W/4))*4;
     for(p=0;p<4;p=p+1)begin
      if(sample_y>=8 && sample_x>=16)begin
       total_pixels=total_pixels+1;
       for(preset=0;preset<4;preset=preset+1)begin
        if(rendered[preset][95-24*p-:24]!==rendered[preset+1][95-24*p-:24])
         differences[preset]=differences[preset]+1;
        v=$signed({1'b0,rendered[preset][95-24*p-:8]})-$signed({1'b0,rendered[preset+1][95-24*p-:8]});
        absolute_delta[preset]=absolute_delta[preset]+(v<0?-v:v);
        if(mode==2)check(rendered[preset][95-24*p-:8]>=rendered[preset+1][95-24*p-:8],"stronger sketch never lightens ink");
        if(mode==3)check(rendered[preset][95-24*p-:8]<=rendered[preset+1][95-24*p-:8],"more sensitive edge never removes a white edge");
       end
      end
      if(dump)for(preset=0;preset<5;preset=preset+1)
       $fwrite(fd[preset],"%06h\n",rendered[preset][95-24*p-:24]);
     end
    end
    out_count=out_count+1;
   end
  end
 end
 initial begin
  metrics=$fopen("production_style_metrics.csv","w");
  $fwrite(metrics,"mode,scene,pixels,diff12,diff23,diff34,diff45,delta12,delta23,delta34,delta45\n");
  repeat(5)@(negedge clk);rst=1;
  for(f=0;f<4;f=f+1)begin
   mode=f;
   for(scene=0;scene<1;scene=scene+1)begin
    total_pixels=0;
    for(preset=0;preset<4;preset=preset+1)begin differences[preset]=0;absolute_delta[preset]=0;end
    for(frame_index=0;frame_index<2;frame_index=frame_index+1)begin
     out_count=0;dump=(frame_index==1);
     if(dump)for(preset=0;preset<5;preset=preset+1)
      fd[preset]=$fopen($sformatf("production_style_m%0d_s%0d_l%0d.hex",f,scene,preset),"w");
     if(scene%2)begin @(negedge clk);user=1;@(negedge clk);user=0;end
     for(y=0;y<H;y=y+1)begin
      for(g=0;g<W/4;g=g+1)begin
       @(negedge clk);valid=1;user=(scene%2==0 && y==0 && g==0);last=(g==W/4-1);
       for(p=0;p<4;p=p+1)pixels[95-24*p-:24]=sample(scene,g*4+p,y);
      end
      @(negedge clk);valid=0;user=0;last=0;repeat(4)@(negedge clk);
     end
     repeat(30)@(negedge clk);
     check(out_count==W*H/4,"one output per valid four-pixel beat");
     if(dump)for(preset=0;preset<5;preset=preset+1)$fclose(fd[preset]);
     dump=0;
    end
    $fwrite(metrics,"%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d\n",f,scene,total_pixels,
      differences[0],differences[1],differences[2],differences[3],
      absolute_delta[0],absolute_delta[1],absolute_delta[2],absolute_delta[3]);
    if(f==3 && scene==3)
     check(differences[3]>total_pixels/10,"highest edge preset reveals additional weak structure");
    if(f==1 && scene==0)for(preset=0;preset<4;preset=preset+1)
     check(differences[preset]>total_pixels/10 && absolute_delta[preset]>total_pixels*3,
       "adjacent cartoon presets visibly change broad ramp regions");
   end
  end
  $fclose(metrics);
  compare_default=0;mode=2;request_level=2;
  @(negedge clk);valid=1;user=1;last=0;pixels={4{24'h808080}};
  @(negedge clk);user=0;request_level=4;
  repeat(10)@(negedge clk);
  check(presets[2].dut.level_f==2,"parameter held inside frame");
  user=1;@(negedge clk);user=0;
  check(presets[2].dut.level_f==4,"next SOF accepts parameter");
  valid=0;repeat(30)@(negedge clk);
  $display("SCENE_STYLE_PRODUCTION_WIDTH_PASS checks=%0d",checks);$finish;
 end
 initial begin #20000000;$fatal(1,"style timeout");end
endmodule
