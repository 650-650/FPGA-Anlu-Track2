// Display-only illumination adaptation. Never feeds exposure/colour/detectors.
// Black-anchored shadow curves replace the fixed V6 low-light compression.
module teammate_display_contrast #(parameter WIDTH=1280,HEIGHT=720)(
 input clk,rst_n,vs,hs,de,input [23:0] rgb,input overlay,bypass,cartoon,keep_legacy,
 input stat_vs,stat_de,input [23:0] stat_rgb,input stat_enable,
 input [2:0] clear_level,
 output O_vs,O_hs,O_de,output reg [23:0] O_rgb,output reg [5:0] O_offset
);
 reg stat_vs_d;
 wire frame=stat_vs && !stat_vs_d;
 reg [11:0] x,y;
 wire [9:0] lsum={2'd0,stat_rgb[23:16]}+{1'b0,stat_rgb[15:8],1'b0}+{2'd0,stat_rgb[7:0]};
 wire [1:0] tile={y>=HEIGHT/2,x>=WIDTH/2};
 wire [5:0] sample_addr={tile,lsum[9:6]};
 // A synchronous address and one shared writer permit a small block RAM.
 (* ram_style="bram" *) reg [15:0] histogram[0:63];
 reg [5:0] read_addr,write_addr,scan_index,held_addr;
 reg [15:0] write_data;
 reg write_en;
 wire [15:0] count_data=histogram[read_addr];
 always @(posedge clk)if(write_en)histogram[write_addr]<=write_data;
 reg [15:0] total[0:3];
 reg [7:0] floor[0:3];
 reg [7:0] midpoint[0:3];
 reg [3:0] valid_tiles;
 reg [2:0] shadow_level;
 reg [16:0] cumulative;
 reg tile_found,mid_found,boot_clear;
 localparam SCAN_READ=0,SCAN_VALUE=1,SCAN_ADVANCE=2,APPLY=3,IDLE=4,INCREMENT=5,WRITEBACK=6,LIGHT=7;
 reg [2:0] state;
 integer k;
 reg [16:0] next_count;
 reg [5:0] target_offset;
 reg [2:0] target_shadow;
 function [7:0] median4;
  input [7:0] a,b,c,d;
  reg [7:0] lo0,hi0,lo1,hi1,mid0,mid1;
  reg [8:0] sum;
  begin
   lo0=a<b?a:b;hi0=a>b?a:b;lo1=c<d?c:d;hi1=c>d?c:d;
   mid0=lo0>lo1?lo0:lo1;mid1=hi0<hi1?hi0:hi1;
   sum={1'b0,mid0}+{1'b0,mid1};median4=sum[8:1];
  end
 endfunction
 wire [7:0] summary=median4(LIGHT==state?midpoint[0]:floor[0],LIGHT==state?midpoint[1]:floor[1],
  LIGHT==state?midpoint[2]:floor[2],LIGHT==state?midpoint[3]:floor[3]);
 wire [2:0] valid_count={2'd0,valid_tiles[0]}+{2'd0,valid_tiles[1]}+{2'd0,valid_tiles[2]}+{2'd0,valid_tiles[3]};
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   stat_vs_d<=0;x<=0;y<=0;read_addr<=0;write_addr<=0;scan_index<=0;held_addr<=0;
   write_data<=0;write_en<=0;cumulative<=0;tile_found<=0;mid_found<=0;boot_clear<=1;state<=SCAN_READ;O_offset<=0;
   valid_tiles<=0;shadow_level<=7;
   for(k=0;k<4;k=k+1)begin total[k]<=0;floor[k]<=32;midpoint[k]<=64;end
  end else begin
   stat_vs_d<=stat_vs;write_en<=0;
   if(frame)begin x<=0;y<=0;end
   else if(stat_de)begin
    if(x==WIDTH-1)begin x<=0;y<=y==HEIGHT-1?0:y+1'b1;end else x<=x+1'b1;
   end
   if(frame && state==IDLE)begin scan_index<=0;cumulative<=0;tile_found<=0;mid_found<=0;valid_tiles<=0;state<=SCAN_READ;end
   else case(state)
    SCAN_READ:begin read_addr<=scan_index;state<=SCAN_VALUE;end
    SCAN_VALUE:begin
     write_en<=1;write_addr<=scan_index;write_data<=0;
     if(!boot_clear)begin
      next_count=cumulative+{1'b0,count_data};cumulative<=next_count;
      if(!tile_found && total[scan_index[5:4]]>=128 && next_count>=(total[scan_index[5:4]]>>4))begin
       // A mostly bright tile is content, not evidence for a black pedestal.
       if(scan_index[3:0]<=6)floor[scan_index[5:4]]<={scan_index[3:0],4'd8};
       tile_found<=1;
      end
      if(!mid_found && total[scan_index[5:4]]>=128 && next_count>=(total[scan_index[5:4]]>>1))begin
       midpoint[scan_index[5:4]]<={scan_index[3:0],4'd8};mid_found<=1;
      end
     end
     state<=SCAN_ADVANCE;
    end
    SCAN_ADVANCE:begin
     if(scan_index[3:0]==15)begin
      cumulative<=0;tile_found<=0;mid_found<=0;total[scan_index[5:4]]<=0;
      valid_tiles[scan_index[5:4]]<=total[scan_index[5:4]]>=128;
     end
     if(scan_index==63)state<=APPLY;
     else begin scan_index<=scan_index+1'b1;state<=SCAN_READ;end
    end
    APPLY:begin
     target_offset=summary<=32?0:summary>=56?24:summary-32;
     if(!boot_clear && valid_count>=3)begin
      if(O_offset<target_offset)O_offset<=O_offset+1'b1;
      else if(O_offset>target_offset)O_offset<=O_offset-1'b1;
     end
     state<=LIGHT;
    end
    LIGHT:begin
     target_shadow=summary<=80?7:summary<=96?6:summary<=112?5:summary<=128?4:
       summary<=144?3:summary<=160?2:summary<=176?1:0;
     if(!boot_clear && valid_count>=3)begin
      if(shadow_level<target_shadow)shadow_level<=shadow_level+1'b1;
      else if(shadow_level>target_shadow)shadow_level<=shadow_level-1'b1;
     end
     boot_clear<=0;state<=IDLE;
    end
    IDLE:if(stat_enable && stat_de && x[3:0]==0)begin
     read_addr<=sample_addr;held_addr<=sample_addr;state<=INCREMENT;
     if(!(&total[tile]))total[tile]<=total[tile]+1'b1;
    end
    INCREMENT:begin
     write_addr<=held_addr;write_data<=(&count_data)?count_data:count_data+1'b1;write_en<=1;state<=WRITEBACK;
    end
    WRITEBACK:state<=IDLE;
    default:state<=SCAN_READ;
   endcase
  end
 end
 wire [9:0] rgb_lsum={2'd0,rgb[23:16]}+{1'b0,rgb[15:8],1'b0}+{2'd0,rgb[7:0]};
 wire [7:0] luminance=rgb_lsum[9:2];
 wire [7:0] maximum=rgb[23:16]>rgb[15:8]?(rgb[23:16]>rgb[7:0]?rgb[23:16]:rgb[7:0]):(rgb[15:8]>rgb[7:0]?rgb[15:8]:rgb[7:0]);
 wire [7:0] minimum=rgb[23:16]<rgb[15:8]?(rgb[23:16]<rgb[7:0]?rgb[23:16]:rgb[7:0]):(rgb[15:8]<rgb[7:0]?rgb[15:8]:rgb[7:0]);
 // Recognition/status pages keep the exact V7 display mapping. Visual pages
 // separate suppression of a nonzero grey floor from midtone illumination.
 wire [5:0] legacy_strength=shadow_level==7?6'd0:shadow_level>=5?O_offset>>2:shadow_level>=3?O_offset>>1:O_offset;
 wire [5:0] visual_strength=shadow_level>=5?O_offset>>2:shadow_level>=3?O_offset>>1:O_offset;
 wire [5:0] strength=keep_legacy?legacy_strength:visual_strength;
 wire [7:0] low_room=luminance>>1,high_room=(255-luminance)>>2;
 wire [7:0] room=low_room<high_room?low_room:high_room;
 wire [7:0] pedestal=strength<room?{2'd0,strength}:room;
 wire [7:0] adjusted_luma=luminance-pedestal;
 function [7:0] contrast_input;
  input [7:0] value;input [2:0] level;
  reg signed [10:0] expanded;
  reg [7:0] headroom,lift_room,strong_lift;
  begin
   headroom=8'd255-value;
   lift_room=value<headroom?value:headroom;
   strong_lift=value<(headroom>>1)?value:(headroom>>1);
   expanded=level==4 ? ($signed({3'd0,value})<<<1)-11'sd128:
       $signed({3'd0,value})+$signed({4'd0,value[7:1]})-11'sd64;
   case(level)
    0:contrast_input=value+strong_lift;
    1:contrast_input=value+(lift_room>>1);
    3,4:contrast_input=expanded<0?8'd0:expanded>255?8'd255:expanded[7:0];
    default:contrast_input=value;
   endcase
  end
 endfunction
 wire [7:0] tone_input=contrast_input(adjusted_luma,clear_level);
 wire [7:0] mapped;
 teammate_display_tone_rom u_tone(.clk(clk),.addr({keep_legacy,shadow_level,tone_input}),.data(mapped));
 reg [23:0] rgb_d;
 reg [7:0] min_d,max_d;
 reg [7:0] luma_d;
 reg signed [9:0] delta;
 reg bypass_d;
 reg [1:0] vpipe,hpipe,dpipe;
 reg signed [9:0] safe_delta;
 reg [7:0] nr,ng,nb;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin rgb_d<=0;min_d<=0;max_d<=0;luma_d<=0;bypass_d<=1;vpipe<=0;hpipe<=0;dpipe<=0;O_rgb<=0;end
  else begin
   rgb_d<=rgb;min_d<=minimum;max_d<=maximum;
   luma_d<=luminance;bypass_d<=bypass||overlay||cartoon;
   vpipe<={vpipe[0],vs};hpipe<={hpipe[0],hs};dpipe<={dpipe[0],de};
   delta=$signed({2'd0,mapped})-$signed({2'd0,luma_d});safe_delta=delta;
   if(safe_delta<-$signed({2'd0,min_d}))safe_delta=-$signed({2'd0,min_d});
   if(safe_delta>$signed(10'd255-{2'd0,max_d}))safe_delta=$signed(10'd255-{2'd0,max_d});
   nr=$signed({2'd0,rgb_d[23:16]})+safe_delta;ng=$signed({2'd0,rgb_d[15:8]})+safe_delta;nb=$signed({2'd0,rgb_d[7:0]})+safe_delta;
   O_rgb<=bypass_d?rgb_d:{nr,ng,nb};
  end
 end
 assign O_vs=vpipe[1];assign O_hs=hpipe[1];assign O_de=dpipe[1];
endmodule

// One synchronous ROM read occupies the original first pixel stage; no extra
// video latency. All 8 x 256 table values are generated and exhaustively tested.
module teammate_display_tone_rom(input clk,input [11:0] addr,output [7:0] data);
 localparam INIT_FILE="D:/FPGA_Work/AnlogicCup2026/07_stylize_flame_fusion_v16_scene_levels_latency/user_source/hdl_source/display_tone.dat";
`ifdef __ICARUS__
 reg [7:0] memory[0:4095];reg [7:0] q;
 initial $readmemb(INIT_FILE,memory);
 always @(posedge clk)q<=memory[addr];
 assign data=q;
`else
 PH1P_LOGIC_ERAM #(.DATA_WIDTH_A(8),.DATA_WIDTH_B(8),.ADDR_WIDTH_A(12),.ADDR_WIDTH_B(12),
  .DATA_DEPTH_A(4096),.DATA_DEPTH_B(4096),.MODE("DP"),.REGMODE_A("NOREG"),.REGMODE_B("NOREG"),
  .WRITEMODE_A("NORMAL"),.WRITEMODE_B("NORMAL"),.CLKMODE("SYNC"),.INIT_FILE(INIT_FILE),.FORCE_KEEP("ON")) u_rom(
  .clka(clk),.clkb(clk),.addra(addr),.addrb(12'd0),.dia(8'd0),.dib(8'd0),.doa(data),.dob(),
  .wea(1'b0),.web(1'b0),.cea(1'b1),.ceb(1'b1),.ocea(1'b1),.oceb(1'b1),
  .bea(1'b0),.beb(1'b0),.rsta(1'b0),.rstb(1'b0),.ecc_sbiterr(),.ecc_dbiterr(),.ecc_sbiterrinj(1'b0),.ecc_dbiterrinj(1'b0));
`endif
endmodule
