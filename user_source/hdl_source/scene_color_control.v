// Neutral-sample scene estimate. Only completed frames produce ratios; one
// iterative divider is shared by R and B. There is no per-pixel divider.
module color_ratio_divider(
    input clk,rst_n,start,
    input [35:0] numerator,input [23:0] denominator,
    output reg busy,done,output reg [35:0] quotient
);
    reg [35:0] work;
    reg [23:0] divisor;
    reg [24:0] remainder;
    reg [5:0] left;
    wire [24:0] trial={remainder[23:0],work[35]};
    wire subtract=trial>={1'b0,divisor};
    wire [35:0] next_work={work[34:0],subtract};
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin busy<=0;done<=0;quotient<=0;work<=0;divisor<=0;remainder<=0;left<=0;end
        else begin
            done<=0;
            if(start && !busy)begin
                work<=numerator;divisor<=denominator;remainder<=0;left<=36;busy<=1;
            end else if(busy)begin
                remainder<=subtract?trial-{1'b0,divisor}:trial;
                work<=next_work;left<=left-1'b1;
                if(left==1)begin quotient<=divisor==0?36'd0:next_work;busy<=0;done<=1;end
            end
        end
    end
endmodule

module scene_color_control #(
    parameter MIN_SAMPLES=128,parameter FAST_FRAMES=16,
    parameter READY_FRAMES=8,parameter TIMEOUT_FRAMES=300
)(
    input clk,rst_n,valid,sof,allow,relearn,input [95:0] rgb,
    output reg [12:0] gain_r,gain_b,output reg ready
);
    reg sof_d,relearn_d;
    wire frame=sof && !sof_d;
    wire request=relearn && !relearn_d;
    wire [7:0] r=rgb[95:88],g=rgb[87:80],b=rgb[79:72];
    wire [7:0] maximum=r>g?(r>b?r:b):(g>b?g:b);
    wire [7:0] minimum=r<g?(r<b?r:b):(g<b?g:b);
    // Reject clipped, dark, and strongly coloured samples. No attempt is made
    // to turn a whole grass/coloured-wall scene into a grey reference.
    wire neutral=minimum>=24 && maximum>=48 && maximum<240 &&
        {1'b0,maximum-minimum}<=({2'b0,minimum[7:1]}+9'd12);
    reg [3:0] phase;
    wire take=valid && (frame || phase==0) && neutral;
    reg [23:0] sum_r,sum_g,sum_b;
    reg [15:0] count;
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin sof_d<=0;phase<=0;sum_r<=0;sum_g<=0;sum_b<=0;count<=0;end
        else begin
            sof_d<=sof;
            if(frame)begin
                phase<=valid?1:0;sum_r<=take?{16'd0,r}:24'd0;
                sum_g<=take?{16'd0,g}:24'd0;sum_b<=take?{16'd0,b}:24'd0;count<=take?1:0;
            end else if(valid)begin
                phase<=phase+1'b1;
                if(take && !(&count))begin
                    sum_r<=sum_r+r;sum_g<=sum_g+g;sum_b<=sum_b+b;count<=count+1'b1;
                end
            end
        end
    end
    reg div_start;
    reg [35:0] numerator;
    reg [23:0] denominator,held_b;
    wire div_busy,div_done;
    wire [35:0] quotient;
    color_ratio_divider u_ratio(.clk(clk),.rst_n(rst_n && !request),.start(div_start),
        .numerator(numerator),.denominator(denominator),.busy(div_busy),.done(div_done),.quotient(quotient));
    reg [1:0] state;
    reg [12:0] pending_r,pending_b,first_r;
    reg fresh;
    reg [7:0] fast_count,qualified;
    reg [8:0] age;
    function [12:0] bounded;
        input [35:0] value;
        begin bounded=value<3072?13'd3072:value>6144?13'd6144:value[12:0];end
    endfunction
    function [12:0] slew;
        input [12:0] current,target,step;
        begin
            if({1'b0,target}>{1'b0,current}+14'd16)
                slew=target-current>step?current+step:target;
            else if({1'b0,current}>{1'b0,target}+14'd16)
                slew=current-target>step?current-step:target;
            else slew=current;
        end
    endfunction
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            gain_r<=4096;gain_b<=4096;ready<=1;state<=0;fresh<=0;
            pending_r<=4096;pending_b<=4096;first_r<=4096;
            div_start<=0;numerator<=0;denominator<=0;held_b<=0;
            fast_count<=0;qualified<=0;age<=0;relearn_d<=0;
        end else begin
            relearn_d<=relearn;div_start<=0;
            if(request)begin state<=0;fresh<=0;fast_count<=0;qualified<=0;age<=0;ready<=0;end
            else begin
                if(frame)begin
                    fresh<=0;
                    if(fresh && allow)begin
                        gain_r<=slew(gain_r,pending_r,fast_count<FAST_FRAMES?13'd128:13'd8);
                        gain_b<=slew(gain_b,pending_b,fast_count<FAST_FRAMES?13'd128:13'd8);
                        if(fast_count<FAST_FRAMES)fast_count<=fast_count+1'b1;
                        if(!ready)begin
                            if(qualified>=READY_FRAMES-1)ready<=1;
                            else qualified<=qualified+1'b1;
                        end
                    end
                    if(!ready)begin
                        if(age>=TIMEOUT_FRAMES-1)ready<=1;
                        else age<=age+1'b1;
                    end
                    if(state==0 && !div_busy && allow && count>=MIN_SAMPLES && sum_r!=0 && sum_b!=0)begin
                        numerator<={sum_g,12'd0};denominator<=sum_r;held_b<=sum_b;
                        div_start<=1;state<=1;
                    end
                end
                if(div_done && state==1)begin
                    first_r<=bounded(quotient);denominator<=held_b;div_start<=1;state<=2;
                end else if(div_done && state==2)begin
                    pending_r<=first_r;pending_b<=bounded(quotient);fresh<=1;state<=0;
                end
            end
        end
    end
endmodule
