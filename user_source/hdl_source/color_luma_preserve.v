// Three-clock colour-only correction. R+2G+B is EXACTLY invariant for every
// active pixel. No neighbours, temporal blending, resampling or clipping.
// A common power-of-two strength keeps all channels in gamut; if no tested
// strength fits, the original pixel is emitted unchanged.
module color_luma_preserve(
    input clk,rst_n,vs,hs,de,user,last,input [23:0] rgb,
    input [12:0] gain_r,gain_b,input [5:0] trim,input bypass,
    output O_vs,O_hs,O_de,O_user,O_last,output reg [23:0] O_rgb
);
    function [12:0] adjusted;
        input [12:0] base;
        input [5:0] control;
        input blue;
        reg signed [15:0] temperature,tint,value;
        begin
            temperature=$signed(control[5:2]);temperature=temperature<<<7;
            tint=control[1:0]==1?16'sd256:control[1:0]==2?-16'sd256:16'sd0;
            value=$signed({3'd0,base==0?13'd4096:base})+(blue?-temperature:temperature)+tint;
            adjusted=value<2048?13'd2048:value>6144?13'd6144:value[12:0];
        end
    endfunction
    wire [12:0] gr=bypass?13'd4096:adjusted(gain_r,trim,1'b0);
    wire [12:0] gb=bypass?13'd4096:adjusted(gain_b,trim,1'b1);
    reg [20:0] product_r,product_b;
    reg [23:0] rgb1,rgb2;
    reg signed [11:0] delta_r,delta_b;
    wire signed [11:0] raw_r=$signed({3'd0,product_r[20:12]})-$signed({4'd0,rgb1[23:16]});
    wire signed [11:0] raw_b=$signed({3'd0,product_b[20:12]})-$signed({4'd0,rgb1[7:0]});
    function [25:0] corrected_delta;
        input signed [11:0] dr,db;input [1:0] shift;
        reg signed [12:0] rr,bb;
        begin
            rr=dr>>>shift;bb=db>>>shift;
            if(rr[0]!=bb[0])begin
                if(bb>0)bb=bb-1;else if(bb<0)bb=bb+1;
                else if(rr>0)rr=rr-1;else rr=rr+1;
            end
            corrected_delta={rr,bb};
        end
    endfunction
    function [23:0] safe_color;
        input [23:0] original;input signed [11:0] dr,db;
        reg signed [12:0] rr,bb,gg,lo_r,lo_g,lo_b,hi_r,hi_g,hi_b;
        reg [25:0] pair,selected;
        reg found;integer s;
        reg [7:0] nr,ng,nb;
        begin
            lo_r=-$signed({5'd0,original[23:16]});lo_g=-$signed({5'd0,original[15:8]});lo_b=-$signed({5'd0,original[7:0]});
            hi_r=13'sd255+lo_r;hi_g=13'sd255+lo_g;hi_b=13'sd255+lo_b;
            found=0;selected=0;
            for(s=0;s<4;s=s+1)begin
                pair=corrected_delta(dr,db,s);rr=$signed(pair[25:13]);bb=$signed(pair[12:0]);gg=-((rr+bb)>>>1);
                if(!found && rr>=lo_r && rr<=hi_r && gg>=lo_g && gg<=hi_g && bb>=lo_b && bb<=hi_b)begin
                    selected=pair;found=1;
                end
            end
            rr=$signed(selected[25:13]);bb=$signed(selected[12:0]);gg=-((rr+bb)>>>1);
            nr=$signed({5'd0,original[23:16]})+rr;ng=$signed({5'd0,original[15:8]})+gg;nb=$signed({5'd0,original[7:0]})+bb;
            safe_color={nr,ng,nb};
        end
    endfunction
    reg [2:0] vs_d,hs_d,de_d,user_d,last_d;
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            product_r<=0;product_b<=0;rgb1<=0;rgb2<=0;delta_r<=0;delta_b<=0;O_rgb<=0;
            vs_d<=0;hs_d<=0;de_d<=0;user_d<=0;last_d<=0;
        end else begin
            product_r<=rgb[23:16]*gr+21'd2048;product_b<=rgb[7:0]*gb+21'd2048;
            rgb1<=rgb;rgb2<=rgb1;
            delta_r<=((raw_r<<<1)+raw_r-raw_b)>>>2;
            delta_b<=((raw_b<<<1)+raw_b-raw_r)>>>2;
            O_rgb<=safe_color(rgb2,delta_r,delta_b);
            vs_d<={vs_d[1:0],vs};hs_d<={hs_d[1:0],hs};de_d<={de_d[1:0],de};
            user_d<={user_d[1:0],user};last_d<={last_d[1:0],last};
        end
    end
    assign O_vs=vs_d[2];assign O_hs=hs_d[2];assign O_de=de_d[2];
    assign O_user=user_d[2];assign O_last=last_d[2];
endmodule
