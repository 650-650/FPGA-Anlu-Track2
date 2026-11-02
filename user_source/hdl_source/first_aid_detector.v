// Three independent green run clusters, cross verification and short tracking
// hysteresis. The published box uses the newest matching green geometry.
module first_aid_detector #(
 parameter FRAME_WIDTH=1280,parameter MIN_RUN=12,parameter MIN_GREEN=96,
 parameter MIN_SIZE=24,parameter HOLD_FRAMES=4
)(
 input clk,rst_n,frame_start,de,enable,input [11:0] x,y,input [23:0] rgb,
 output hit,output [23:0] color,output reg target,output [11:0] center_x,center_y
);
 wire [7:0] r=rgb[23:16],g=rgb[15:8],b=rgb[7:0];
 wire [7:0] maximum=r>g?(r>b?r:b):(g>b?g:b);
 wire [7:0] minimum=r<g?(r<b?r:b):(g<b?g:b);
 wire [8:0] margin=g[7:4]>8?{5'd0,g[7:4]}:9'd8;
 wire green=g>=32 && {1'b0,g}>={1'b0,r}+margin && {1'b0,g}>={1'b0,b}+margin &&
     {1'b0,g}-{1'b0,minimum}>={4'd0,g[7:3]};
 wire white=!green && minimum>=112 && maximum>=144 && maximum-minimum<=40;
 reg [11:0] run_start,run_len;
 wire run_end=de && run_len!=0 && (!green || x==FRAME_WIDTH-1);
 wire [12:0] run_size={1'b0,run_len}+(green?13'd1:13'd0);
 wire [11:0] run_x1=green?x:x-1'b1;
 reg [11:0] gx0[0:2],gx1[0:2],gy0[0:2],gy1[0:2],green_count[0:2];
 reg [11:0] px0[0:2],px1[0:2],py0[0:2],py1[0:2],panel_score[0:2];
 reg [2:0] panel_valid;
 reg [5:0] white_v[0:2],white_h[0:2];reg [3:0] white_c[0:2];
 reg [11:0] bx0,bx1,by0,by1;
 reg [2:0] misses;reg pending;
 reg [11:0] pending_x,pending_y;
 wire [11:0] box_cx=bx0+((bx1-bx0)>>1),box_cy=by0+((by1-by0)>>1);
 integer cs,ci,cj,sq,slot,choice,match_index;
 reg [12:0] width,height,pw,ph,cx,cy,score,best_score;
 reg verified,associated,found;
 reg [11:0] next_x0,next_x1,next_y0,next_y1;
 function geometry;
  input [11:0] x0,x1,y0,y1,count;
  reg [12:0] w,h;
  begin w={1'b0,x1}-{1'b0,x0}+1;h={1'b0,y1}-{1'b0,y0}+1;
   geometry=count>=MIN_GREEN && w>=MIN_SIZE && h>=MIN_SIZE && w<=(h<<1) && h<=(w<<1);
  end
 endfunction
 function near_boxes;
  input [11:0] a0,a1,b0,b1,c0,c1,d0,d1;
  begin near_boxes={1'b0,a0}<={1'b0,c1}+24 && {1'b0,c0}<={1'b0,a1}+24 &&
     {1'b0,b0}<={1'b0,d1}+24 && {1'b0,d0}<={1'b0,b1}+24;end
 endfunction
 function [11:0] stable_edge;
  input [11:0] old_edge,new_edge;
  begin stable_edge=old_edge>new_edge?(old_edge-new_edge<=2?old_edge:new_edge):
       (new_edge-old_edge<=2?old_edge:new_edge);end
 endfunction
 // Match a completed green run to a nearby independent cluster. Small stale
 // fragments can be recycled; a distant green object cannot enlarge this box.
 always @*begin
  slot=-1;
  for(cs=0;cs<3;cs=cs+1)if(slot<0 && green_count[cs]!=0 &&
   {1'b0,y}<={1'b0,gy1[cs]}+24 && {1'b0,run_start}<={1'b0,gx1[cs]}+8 &&
   {1'b0,run_x1}+8>={1'b0,gx0[cs]})slot=cs;
  if(slot<0)for(cs=0;cs<3;cs=cs+1)if(slot<0 && (green_count[cs]==0 ||
    (green_count[cs]<MIN_GREEN && {1'b0,y}>{1'b0,gy1[cs]}+24)))slot=cs;
 end
 // Reuse one verification/association datapath across nine candidate pairs
 // during HDMI vertical blanking; no replicated 3x3 comparator fabric.
 reg scan_active,scan_done;
 reg [1:0] scan_panel,scan_green;
 reg pair_valid;
 always @*begin
  associated=target && near_boxes(bx0,bx1,by0,by1,px0[scan_panel],px1[scan_panel],py0[scan_panel],py1[scan_panel]);
  score={1'b0,panel_score[scan_panel]}+(associated?13'd4096:13'd0);
  pair_valid=panel_valid[scan_panel] && white_v[scan_panel]>=12 && white_h[scan_panel]>=12 && white_c[scan_panel]>=3 &&
   geometry(gx0[scan_green],gx1[scan_green],gy0[scan_green],gy1[scan_green],green_count[scan_green]) &&
   near_boxes(px0[scan_panel],px1[scan_panel],py0[scan_panel],py1[scan_panel],gx0[scan_green],gx1[scan_green],gy0[scan_green],gy1[scan_green]);
 end
 reg [12:0] sum;
 reg [12:0] vpw,vph,vcx,vcy;
 reg same_target;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n || !enable)begin
   run_start<=0;run_len<=0;panel_valid<=0;target<=0;misses<=0;pending<=0;pending_x<=0;pending_y<=0;
   bx0<=0;bx1<=0;by0<=0;by1<=0;scan_active<=0;scan_done<=0;scan_panel<=0;scan_green<=0;found<=0;best_score<=0;next_x0<=0;next_x1<=0;next_y0<=0;next_y1<=0;
   for(sq=0;sq<3;sq=sq+1)begin
    gx0[sq]<=0;gx1[sq]<=0;gy0[sq]<=0;gy1[sq]<=0;green_count[sq]<=0;
    px0[sq]<=0;px1[sq]<=0;py0[sq]<=0;py1[sq]<=0;panel_score[sq]<=0;
    white_v[sq]<=0;white_h[sq]<=0;white_c[sq]<=0;
   end
  end else if(frame_start)begin
   scan_active<=1;scan_done<=0;scan_panel<=0;scan_green<=0;found<=0;best_score<=0;
  end else if(scan_active)begin
   if(pair_valid && (!found || score>best_score))begin
    found<=1;best_score<=score;next_x0<=gx0[scan_green];next_x1<=gx1[scan_green];next_y0<=gy0[scan_green];next_y1<=gy1[scan_green];
   end
   if(scan_green==2)begin
    scan_green<=0;
    if(scan_panel==2)begin scan_active<=0;scan_done<=1;end else scan_panel<=scan_panel+1'b1;
   end else scan_green<=scan_green+1'b1;
  end else if(scan_done)begin
   scan_done<=0;run_len<=0;run_start<=0;
   for(sq=0;sq<3;sq=sq+1)begin
    panel_valid[sq]<=geometry(gx0[sq],gx1[sq],gy0[sq],gy1[sq],green_count[sq]);
    px0[sq]<=gx0[sq];px1[sq]<=gx1[sq];py0[sq]<=gy0[sq];py1[sq]<=gy1[sq];panel_score[sq]<=green_count[sq];
    green_count[sq]<=0;white_v[sq]<=0;white_h[sq]<=0;white_c[sq]<=0;
   end
   if(found)begin
    same_target=target && near_boxes(bx0,bx1,by0,by1,next_x0,next_x1,next_y0,next_y1);
    if(same_target || (pending && {1'b0,next_x0}+32>={1'b0,pending_x} &&
        {1'b0,pending_x}+32>={1'b0,next_x0} && {1'b0,next_y0}+32>={1'b0,pending_y} &&
        {1'b0,pending_y}+32>={1'b0,next_y0}))begin
     target<=1;misses<=0;
     bx0<=same_target?stable_edge(bx0,next_x0):next_x0;bx1<=same_target?stable_edge(bx1,next_x1):next_x1;
     by0<=same_target?stable_edge(by0,next_y0):next_y0;by1<=same_target?stable_edge(by1,next_y1):next_y1;
    end else begin
     if(misses<HOLD_FRAMES)misses<=misses+1'b1;
     if(misses>=HOLD_FRAMES-1)target<=0;
    end
    pending<=1;pending_x<=next_x0;pending_y<=next_y0;
   end else begin
    pending<=0;
    if(misses<HOLD_FRAMES)misses<=misses+1'b1;
    if(misses>=HOLD_FRAMES-1)target<=0;
   end
  end else if(de)begin
   if(green)begin
    if(run_len==0)run_start<=x;
    run_len<=x==FRAME_WIDTH-1?0:run_len+1'b1;
   end else run_len<=0;
   if(run_end && run_size>=MIN_RUN && slot>=0)begin
    sum={1'b0,green_count[slot]}+run_size;
    if(green_count[slot]==0 || ({1'b0,y}>{1'b0,gy1[slot]}+24 && green_count[slot]<MIN_GREEN))begin
     gx0[slot]<=run_start;gx1[slot]<=run_x1;gy0[slot]<=y;gy1[slot]<=y;
     green_count[slot]<=run_size>4095?12'd4095:run_size[11:0];
    end else begin
     if(run_start<gx0[slot])gx0[slot]<=run_start;if(run_x1>gx1[slot])gx1[slot]<=run_x1;
     gy1[slot]<=y;green_count[slot]<=sum>4095?12'd4095:sum[11:0];
    end
   end
   if(white)for(sq=0;sq<3;sq=sq+1)if(panel_valid[sq])begin
    vpw={1'b0,px1[sq]}-{1'b0,px0[sq]};vph={1'b0,py1[sq]}-{1'b0,py0[sq]};
    vcx={1'b0,px0[sq]}+(vpw>>1);vcy={1'b0,py0[sq]}+(vph>>1);
    if({1'b0,x}+(vpw>>3)>=vcx && {1'b0,x}<=vcx+(vpw>>3) &&
       y>=py0[sq]+(vph>>2) && {1'b0,y}+(vph>>2)<={1'b0,py1[sq]} && white_v[sq]<63)white_v[sq]<=white_v[sq]+1'b1;
    if({1'b0,y}+(vph>>3)>=vcy && {1'b0,y}<=vcy+(vph>>3) &&
       x>=px0[sq]+(vpw>>2) && {1'b0,x}+(vpw>>2)<={1'b0,px1[sq]} && white_h[sq]<63)white_h[sq]<=white_h[sq]+1'b1;
    if({1'b0,x}+(vpw>>3)>=vcx && {1'b0,x}<=vcx+(vpw>>3) &&
       {1'b0,y}+(vph>>3)>=vcy && {1'b0,y}<=vcy+(vph>>3) && white_c[sq]<15)white_c[sq]<=white_c[sq]+1'b1;
   end
  end
 end
 assign center_x=target?box_cx:12'd0;assign center_y=target?box_cy:12'd0;
 assign hit=de && target && x>=bx0&&x<=bx1&&y>=by0&&y<=by1 &&
  (x-bx0<3 || bx1-x<3 || y-by0<3 || by1-y<3);
 assign color=24'h00ff40;
endmodule
