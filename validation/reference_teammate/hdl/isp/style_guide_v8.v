// Local two-scale line guide. No frame histogram, mode, or brightness escape.
// Inputs are row-major 3x3 B2 luminances / aligned first-scale Sobel magnitudes:
// top-left [71:64], centre [39:32], bottom-right [7:0]. Pure combinational;
// the style core registers its outputs in the existing C1 stage.
module style_guide_v8(
 input [71:0] I_y2,I_fine,
 input [7:0] I_edge_threshold,
 input I_edge_detail,
 output [7:0] O_mag,
 output O_edge,O_support
);
 wire [7:0] y[0:8];
 wire [7:0] m[0:8];
 genvar k;
 generate for(k=0;k<9;k=k+1)begin: unpack
  assign y[k]=I_y2[71-8*k-:8];
  assign m[k]=I_fine[71-8*k-:8];
 end endgenerate

 wire signed [10:0] gx=$signed({3'd0,y[2]})+$signed({2'd0,y[5],1'b0})+$signed({3'd0,y[8]})-
     $signed({3'd0,y[0]})-$signed({2'd0,y[3],1'b0})-$signed({3'd0,y[6]});
 wire signed [10:0] gy=$signed({3'd0,y[6]})+$signed({2'd0,y[7],1'b0})+$signed({3'd0,y[8]})-
     $signed({3'd0,y[0]})-$signed({2'd0,y[1],1'b0})-$signed({3'd0,y[2]});
 wire [10:0] ax=gx[10]?-gx:gx,ay=gy[10]?-gy:gy;
 wire [11:0] coarse_sum={1'b0,ax}+{1'b0,ay};
 wire [7:0] coarse=(|coarse_sum[11:8])?8'd255:coarse_sum[7:0];
 wire vertical={1'b0,ax}>={ay,1'b0};
 wire horizontal={1'b0,ay}>={ax,1'b0};
 wire same_sign=gx[10]==gy[10];
 wire [7:0] center=m[4];
 reg [7:0] tangent0,tangent1,normal0,normal1;
 always @*begin
  if(vertical)begin tangent0=m[1];tangent1=m[7];normal0=m[3];normal1=m[5];end
  else if(horizontal)begin tangent0=m[3];tangent1=m[5];normal0=m[1];normal1=m[7];end
  else if(same_sign)begin tangent0=m[2];tangent1=m[6];normal0=m[0];normal1=m[8];end
  else begin tangent0=m[0];tangent1=m[8];normal0=m[2];normal1=m[6];end
 end
 function [7:0] median3;
  input [7:0] a,b,c;
  begin
   if(a>b)median3=b>c?b:(a>c?c:a);
   else median3=a>c?a:(b>c?c:b);
  end
 endfunction
 function [7:0] difference;
  input [7:0] a,b;
  begin difference=a>b?a-b:b-a;end
 endfunction
 wire [7:0] stable_fine=median3(center,tangent0,tangent1);
 wire [7:0] d0=difference(tangent0,center),d1=difference(tangent1,center);
 wire [7:0] tolerance=8'd2+{3'd0,center[7:3]};
 wire linked=tangent0>={1'b0,center[7:1]} && tangent1>={1'b0,center[7:1]};
 wire coherent=d0<=tolerance && d1<=tolerance;
 wire strict_line=d0<=2 && d1<=2;
 wire weak_edge=d0<=1 && d1<=1;
 wire ridge=center>=normal0 && center>=normal1;
 wire [9:0] scale_limit={2'd0,coarse}+{3'd0,coarse[7:1]}+10'd6;
 wire scale_agrees={2'd0,stable_fine}<=scale_limit;
 wire trusted=linked && ridge && scale_agrees && coarse>=8 && (coherent || coarse>=64);

 // Retain fine amplitude on a locally stable line (including weak H/V/diagonal
 // lines); otherwise combine scales. An isolated first-scale spike cannot use
 // an unconditional fine>=128/bright-pixel bypass as in the inherited guide.
 wire [9:0] mix_sum={2'd0,coarse}+{1'b0,coarse,1'b0}+{2'd0,stable_fine};
 wire [7:0] mixed=mix_sum[9:2];
 wire [7:0] limited=mixed<center?mixed:center;
 wire [7:0] mixed_mag=limited>4?limited-8'd4:8'd0;
 // Unconfirmed broad structure receives faint ink rather than a binary erasure.
 wire [7:0] coarse_above_floor=coarse>24?coarse-8'd24:8'd0;
 wire [7:0] fallback_limit=coarse_above_floor<center?coarse_above_floor:center;
 wire [7:0] faint_mag={2'd0,fallback_limit[7:2]};
 assign O_mag=trusted?(strict_line?center:mixed_mag):faint_mag;
 wire [7:0] weak_threshold=I_edge_threshold>=8?I_edge_threshold-8'd8:8'd0;
 wire binary_edge=trusted && (O_mag>=I_edge_threshold || (weak_edge && O_mag>=weak_threshold));
 // Highest edge preset keeps coherent gradient shoulders as well as ridges.
 // Scale agreement and tangent support still reject isolated fine spikes.
 wire detail_edge=linked && scale_agrees && coarse>=8 && center>=8 && (coherent || coarse>=64);
 assign O_edge=binary_edge || (I_edge_detail && detail_edge);
 assign O_support=trusted;
endmodule
