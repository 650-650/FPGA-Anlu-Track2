// Board-clock control remains alive while PLL and video logic are reset.
module fusion_controls #(
    // Board feedback: a physically raised SW1..SW4 drives its FPGA pin low.
    parameter integer SWITCH_ACTIVE_LOW=1,
    parameter integer DEBOUNCE_CYCLES=250000,
    parameter integer BOOT_CYCLES=65536,
    parameter integer RESET_CYCLES=500000,
    parameter integer K3_HOLD_CYCLES=100000000,
    parameter integer K4_HOLD_CYCLES=50000000
)(
    input wire I_clk,
    input wire [3:0] I_keys_n, I_switches,
    output wire O_system_rst_n,
    output wire [7:0] O_control,
    output wire O_osd_enable,
    output reg O_wb_toggle=0,
    output wire [5:0] O_color_control
);
    localparam integer DB=$clog2(DEBOUNCE_CYCLES+1);
    localparam integer PB=$clog2(BOOT_CYCLES+1);
    localparam integer RB=$clog2(RESET_CYCLES+1);
    localparam integer K3B=$clog2(K3_HOLD_CYCLES+1);
    localparam integer K4B=$clog2(K4_HOLD_CYCLES+1);
    reg [PB-1:0] boot_count=0;
    reg [RB-1:0] reset_count=0;
    localparam [7:0] INPUTS_IDLE=SWITCH_ACTIVE_LOW ? 8'hff:8'h0f;
    (* ASYNC_REG="TRUE" *) reg [7:0] inputs_meta=INPUTS_IDLE, inputs_sync=INPUTS_IDLE;
    reg [7:0] stable_inputs=INPUTS_IDLE;
    reg [DB-1:0] debounce_count=0;
    reg [3:0] previous_keys=4'hf;
    reg [K3B-1:0] k3_count=0;
    reg [K4B-1:0] k4_count=0;
    reg k3_sent=0,k4_sent=0;
    reg [2:0] group_id=0;
    reg [1:0] page=0;
    reg muted=0,details=0,help=0;
    reg signed [3:0] temperature=0;reg [1:0] tint=0;
    assign O_color_control={temperature,tint};
    wire [2:0] selected_group;
    wire boot_done=boot_count==BOOT_CYCLES;
    assign O_system_rst_n=boot_done && reset_count==0;
    assign O_control={group_id,page,muted,details,help};
    wire [3:0] keys=stable_inputs[3:0];
    wire [3:0] released=keys & ~previous_keys;
    // Normalize once after synchronization and debounce. SW4 is independent:
    // changing Logo/help visibility never resets a selected page or alarm state.
    wire [3:0] switches_up=stable_inputs[7:4] ^ {4{SWITCH_ACTIVE_LOW != 0}};
    assign O_osd_enable=switches_up[3];
    assign selected_group=switches_up[2:0]==0?3'd0:
        switches_up[2:0]==1?3'd1:switches_up[2:0]==2?3'd2:
        switches_up[2:0]==4?3'd3:3'd7;
    always @(posedge I_clk) begin
        if(!boot_done) boot_count<=boot_count+1'b1;
        inputs_meta<={I_switches,I_keys_n}; inputs_sync<=inputs_meta;
        if(inputs_sync==stable_inputs) debounce_count<=0;
        else if(debounce_count==DEBOUNCE_CYCLES-1) begin
            stable_inputs<=inputs_sync; debounce_count<=0;
        end else debounce_count<=debounce_count+1'b1;
        previous_keys<=keys;
        if(reset_count!=0) reset_count<=reset_count-1'b1;
        if(!boot_done) begin k3_count<=0;k4_count<=0;k3_sent<=0;k4_sent<=0;end
        else begin
            if(keys[2]) begin k3_count<=0;k3_sent<=0;end
            else if(!k3_sent) begin
                if(k3_count==K3_HOLD_CYCLES-1) begin
                    reset_count<=RESET_CYCLES;k3_sent<=1;
                end else k3_count<=k3_count+1'b1;
            end
            if(keys[3]) begin k4_count<=0;k4_sent<=0;end
            else if(!k4_sent) begin
                if(k4_count==K4_HOLD_CYCLES-1) begin
                    k4_sent<=1;
                    O_wb_toggle<=~O_wb_toggle;temperature<=0;tint<=0;
                end else k4_count<=k4_count+1'b1;
            end
        end
        if(!O_system_rst_n || selected_group!=group_id) begin
            group_id<=selected_group; page<=selected_group==1 ? 1:0;
            muted<=0;details<=0;help<=0;
            // The receiving synchronizer resets with the PLL. Clear its event
            // source during that reset to prevent a stale toggle relearning WB.
            if(!O_system_rst_n)begin O_wb_toggle<=0;temperature<=0;tint<=0;end
        end else if(released[0]) begin
            page<=0;
            if(group_id==0)begin temperature<=0;tint<=0;O_wb_toggle<=~O_wb_toggle;end
        end else if(released[1]) begin
            if(group_id==0)begin if(temperature>-4)temperature<=temperature-1'b1;end else page<=1;
        end else if(released[2] && !k3_sent) begin
            if(group_id==0)begin if(temperature<4)temperature<=temperature+1'b1;end
            else if(group_id==2)begin
                if(page==2)muted<=~muted;
                else begin page<=2;muted<=0;end
            end else if(group_id!=7)page<=2;
        end else if(released[3] && !k4_sent) begin
            case(group_id)
                0:tint<=tint==2?0:tint+1'b1;
                1:page<=3;
                2:begin page<=3;muted<=0;end
                3:page<=3;
                default:begin end
            endcase
        end
    end
endmodule

// Bundled-data request/acknowledge CDC. Payload is held until destination
// commits it at a frame boundary; individual bits cannot mix between commands.
module fusion_control_cdc #(parameter WIDTH=8)(
    input wire I_source_clk,I_dest_clk,I_rst_n,I_commit,
    input wire [WIDTH-1:0] I_data,
    output reg [WIDTH-1:0] O_data
);
    reg [WIDTH-1:0] held_data;
    reg request,ack;
    (* ASYNC_REG="TRUE" *) reg [1:0] ack_sync;
    (* ASYNC_REG="TRUE" *) reg [2:0] request_sync;
    always @(posedge I_source_clk or negedge I_rst_n) begin
        if(!I_rst_n) begin held_data<=0;request<=0;ack_sync<=0;end
        else begin
            ack_sync<={ack_sync[0],ack};
            if(ack_sync[1]==request && I_data!=held_data) begin
                held_data<=I_data;request<=~request;
            end
        end
    end
    always @(posedge I_dest_clk or negedge I_rst_n) begin
        if(!I_rst_n) begin request_sync<=0;ack<=0;O_data<=0;end
        else begin
            request_sync<={request_sync[1:0],request};
            if(I_commit && request_sync[2]!=ack) begin
                O_data<=held_data;ack<=request_sync[2];
            end
        end
    end
endmodule
