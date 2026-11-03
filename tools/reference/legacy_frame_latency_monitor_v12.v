// Passive same-frame observer. No output feeds a pixel, FIFO or DDR control.
// t0: first valid RAW group at the FPGA stream input.
// t1: first active pixel at the final HDMI transmitter input.
// Publish only after the observed output frame has finished and its DDR
// session is retired. Unprovable/partial/overwritten frames are INVALID.
module legacy_frame_latency_monitor_v12 #(
    parameter integer SYS_HZ=50000000,
    parameter integer WIDTH=1280, HEIGHT=720,
    parameter integer MAX_AGE_US=1000000
)(
    input wire sys_clk,cam_clk,ddr_clk,hdmi_clk,rst_n,
    input wire raw_user,raw_valid,raw_error,packed_user,input_overflow,
    input wire write_start,input wire [1:0] write_slot,
    input wire write_en,input wire [24:0] write_address,
    input wire read_start,input wire [1:0] read_slot,
    input wire read_en,input wire [24:0] read_address,
    input wire read_return,read_fifo_reset,
    input wire raw_hdmi_vs,final_hdmi_vs,final_hdmi_de,output_underflow,
    output reg [31:0] O_latency_us,
    output reg [15:0] O_frame_id,
    output reg O_valid,O_repeat,O_skip
);
    localparam integer RAW_GROUPS=WIDTH*HEIGHT/4;
    localparam integer DDR_WORDS=WIDTH*HEIGHT*24/128;
    localparam integer PIXELS=WIDTH*HEIGHT;
    localparam integer UC=$clog2(SYS_HZ/1000000);
    reg [UC-1:0] us_divider;
    reg [31:0] microseconds,time_gray;
    wire [31:0] next_us=microseconds+32'd1;
    always @(posedge sys_clk or negedge rst_n)begin
        if(!rst_n)begin us_divider<=0;microseconds<=0;time_gray<=0;end
        else if(us_divider==SYS_HZ/1000000-1)begin
            us_divider<=0;microseconds<=next_us;time_gray<=(next_us>>1)^next_us;
        end else us_divider<=us_divider+1'b1;
    end
    (* ASYNC_REG="TRUE" *) reg [31:0] cam_time_meta,cam_time_sync;
    (* ASYNC_REG="TRUE" *) reg [31:0] hdmi_time_meta,hdmi_time_sync;
    always @(posedge cam_clk or negedge rst_n)
        if(!rst_n)begin cam_time_meta<=0;cam_time_sync<=0;end
        else begin cam_time_meta<=time_gray;cam_time_sync<=cam_time_meta;end
    always @(posedge hdmi_clk or negedge rst_n)
        if(!rst_n)begin hdmi_time_meta<=0;hdmi_time_sync<=0;end
        else begin hdmi_time_meta<=time_gray;hdmi_time_sync<=hdmi_time_meta;end
    function [31:0] from_gray;
        input [31:0] value;integer b;
        begin from_gray[31]=value[31];for(b=30;b>=0;b=b-1)from_gray[b]=from_gray[b+1]^value[b];end
    endfunction
    wire [31:0] cam_now=from_gray(cam_time_sync),hdmi_now=from_gray(hdmi_time_sync);

    // Queue RAW provenance until the corresponding packed SOF. A short/empty
    // stream is never allowed to borrow the newest RAW timestamp by accident.
    reg raw_user_d,raw_pending,packed_user_d,raw_active,raw_bad,queue_fault;
    reg [17:0] raw_count;
    reg [15:0] raw_id,qid0,qid1;
    reg [31:0] qt0,qt1;
    reg [1:0] qcount;
    reg [15:0] pack_sequence,pack_id,done_id,raw_fault_id,overflow_id;
    reg [31:0] pack_time;
    reg pack_good,done_good,raw_fault_seen,overflow_seen;
    wire new_raw=raw_valid && (raw_pending || (raw_user && !raw_user_d));
    wire new_pack=packed_user && !packed_user_d;
    wire [15:0] next_raw_id=raw_id+16'd1;
    always @(posedge cam_clk or negedge rst_n)begin
        if(!rst_n)begin
            raw_user_d<=0;raw_pending<=0;packed_user_d<=0;raw_active<=0;raw_bad<=0;
            raw_count<=0;raw_id<=0;qid0<=0;qid1<=0;qt0<=0;qt1<=0;qcount<=0;queue_fault<=0;
            pack_sequence<=0;pack_id<=0;pack_time<=0;pack_good<=0;done_id<=0;done_good<=0;
            raw_fault_id<=0;raw_fault_seen<=0;overflow_id<=0;overflow_seen<=0;
        end else begin
            raw_user_d<=raw_user;packed_user_d<=packed_user;
            if(raw_user && !raw_user_d)raw_pending<=1;
            if(new_raw)begin
                raw_pending<=0;raw_active<=1;raw_id<=next_raw_id;raw_count<=1;raw_bad<=raw_error;
                if(raw_active && raw_count!=RAW_GROUPS)begin
                    done_id<=raw_id;done_good<=0;raw_fault_id<=raw_id;raw_fault_seen<=1;
                end
            end else if(raw_valid && raw_active)begin
                if(raw_count<RAW_GROUPS)raw_count<=raw_count+1'b1;
                else begin raw_bad<=1;raw_fault_id<=raw_id;raw_fault_seen<=1;end
                if(raw_count==RAW_GROUPS-1)begin done_id<=raw_id;done_good<=!raw_bad && !raw_error;end
            end
            if(raw_error && raw_active)begin raw_bad<=1;raw_fault_id<=raw_id;raw_fault_seen<=1;end
            if(input_overflow)begin
                overflow_seen<=1;overflow_id<=new_pack && qcount!=0?qid0:pack_id;
            end
            if(new_pack)begin
                pack_sequence<=pack_sequence+16'd1;
                pack_id<=qcount!=0?qid0:16'd0;pack_time<=qcount!=0?qt0:32'd0;
                pack_good<=qcount!=0 && !queue_fault;
            end
            case({new_raw,new_pack})
                2'b10:begin
                    if(qcount==0)begin qid0<=next_raw_id;qt0<=cam_now;qcount<=1;end
                    else if(qcount==1)begin qid1<=next_raw_id;qt1<=cam_now;qcount<=2;end
                    else queue_fault<=1;
                end
                2'b01:begin
                    if(qcount!=0)begin qid0<=qid1;qt0<=qt1;qcount<=qcount-1'b1;end
                    if(qcount<=1)queue_fault<=0;
                end
                2'b11:begin
                    if(qcount==2)begin qid0<=qid1;qt0<=qt1;qid1<=next_raw_id;qt1<=cam_now;end
                    else begin qid0<=next_raw_id;qt0<=cam_now;qcount<=1;end
                end
                default:begin end
            endcase
        end
    end
    localparam CW=116;
    wire [CW-1:0] camera_state={pack_sequence,pack_id,pack_time,pack_good,done_id,done_good,
        raw_fault_id,raw_fault_seen,overflow_id,overflow_seen};
    wire [CW-1:0] camera_ddr;
    fusion_control_cdc #(.WIDTH(CW)) camera_metadata(
        .I_source_clk(cam_clk),.I_dest_clk(ddr_clk),.I_rst_n(rst_n),.I_commit(1'b1),
        .I_data(camera_state),.O_data(camera_ddr));
    wire [15:0] cp_sequence,cp_id,cd_id,cf_id,co_id;
    wire [31:0] cp_time;
    wire cp_good,cd_good,cf_seen,co_seen;
    assign {cp_sequence,cp_id,cp_time,cp_good,cd_id,cd_good,cf_id,cf_seen,co_id,co_seen}=camera_ddr;

    function [24:0] base_address;
        input [1:0] slot;
        begin case(slot)
            0:base_address=25'd0;1:base_address=25'd7000000;
            2:base_address=25'd14000000;default:base_address=25'd21000000;
        endcase end
    endfunction
    wire [1:0] address_slot=write_address<7000000?2'd0:write_address<14000000?2'd1:
        write_address<21000000?2'd2:2'd3;
    reg [15:0] claim_sequence,slot_claim[0:3],slot_id[0:3];
    reg [31:0] slot_time[0:3];
    reg [17:0] words[0:3];
    reg [3:0] claimed,metadata_ready,raw_complete,write_complete,slot_bad;
    integer s;
    always @(posedge ddr_clk or negedge rst_n)begin
        if(!rst_n)begin
            claim_sequence<=0;claimed<=0;metadata_ready<=0;raw_complete<=0;write_complete<=0;slot_bad<=0;
            for(s=0;s<4;s=s+1)begin slot_claim[s]<=0;slot_id[s]<=0;slot_time[s]<=0;words[s]<=0;end
        end else begin
            if(write_start)claim_sequence<=claim_sequence+16'd1;
            for(s=0;s<4;s=s+1)begin
                if(write_start && write_slot==s)begin
                    slot_claim[s]<=claim_sequence+16'd1;claimed[s]<=1;metadata_ready[s]<=0;
                    raw_complete[s]<=0;write_complete[s]<=0;slot_bad[s]<=0;words[s]<=0;
                    // A stale write in the same slot on its new SOF is unsafe.
                    if(write_en && address_slot==s)slot_bad[s]<=1;
                end else begin
                    if(claimed[s] && !metadata_ready[s] && slot_claim[s]==cp_sequence)begin
                        slot_id[s]<=cp_id;slot_time[s]<=cp_time;metadata_ready[s]<=1;
                        raw_complete[s]<=cd_id==cp_id && cd_good;
                        if(!cp_good || (cf_seen && cf_id==cp_id) || (co_seen && co_id==cp_id))slot_bad[s]<=1;
                    end
                    if(metadata_ready[s])begin
                        if(cd_id==slot_id[s])raw_complete[s]<=cd_good;
                        if((cf_seen && cf_id==slot_id[s]) || (co_seen && co_id==slot_id[s]))slot_bad[s]<=1;
                    end
                    if(write_en && address_slot==s)begin
                        if(claimed[s] && words[s]<DDR_WORDS &&
                            write_address==base_address(s)+{4'd0,words[s],3'b000})begin
                            words[s]<=words[s]+1'b1;
                            if(words[s]==DDR_WORDS-1)write_complete[s]<=1;
                        end else slot_bad[s]<=1;
                    end
                end
            end
        end
    end

    // Both read and write commands enter one ordered existing command FIFO.
    // Track all read returns, including harmless frame-end prefetch. Old
    // outstanding returns at a new read generation poison that generation.
    reg [10:0] outstanding;
    reg [15:0] read_sequence,active_claim;
    reg [1:0] active_slot;
    reg session_active,session_bad;
    reg [17:0] read_words;
    reg [15:0] descriptor_sequence,descriptor_id,verdict_sequence;
    reg [31:0] descriptor_time;
    reg descriptor_good,verdict_good;
    wire snapshot_good=claimed[read_slot] && metadata_ready[read_slot] && raw_complete[read_slot] &&
        write_complete[read_slot] && !slot_bad[read_slot] && !(write_start && write_slot==read_slot);
    wire active_fault=(cf_seen && cf_id==slot_id[active_slot]) || (co_seen && co_id==slot_id[active_slot]);
    always @(posedge ddr_clk or negedge rst_n)begin
        if(!rst_n)begin
            outstanding<=0;read_sequence<=0;active_claim<=0;active_slot<=0;
            session_active<=0;session_bad<=1;read_words<=0;
            descriptor_sequence<=0;descriptor_id<=0;descriptor_time<=0;descriptor_good<=0;
            verdict_sequence<=0;verdict_good<=0;
        end else begin
            case({read_en,read_return})
                2'b10:if(outstanding!=2047)outstanding<=outstanding+1'b1;
                2'b01:if(outstanding!=0)outstanding<=outstanding-1'b1;
                default:begin end
            endcase
            if(read_start)begin
                verdict_sequence<=read_sequence;
                verdict_good<=session_active && !session_bad && read_words==DDR_WORDS && outstanding==0 &&
                    slot_claim[active_slot]==active_claim && !slot_bad[active_slot] && !active_fault &&
                    !(write_start && write_slot==active_slot) && !read_en && !read_return;
                read_sequence<=read_sequence+16'd1;active_slot<=read_slot;active_claim<=slot_claim[read_slot];
                session_active<=1;session_bad<=!snapshot_good || outstanding!=0 || read_en || read_return;read_words<=0;
                descriptor_sequence<=read_sequence+16'd1;
                descriptor_id<=slot_id[read_slot];descriptor_time<=slot_time[read_slot];
                descriptor_good<=snapshot_good && outstanding==0 && !read_en && !read_return;
            end else if(session_active)begin
                if((write_start && write_slot==active_slot) || slot_claim[active_slot]!=active_claim ||
                    slot_bad[active_slot] || active_fault)session_bad<=1;
                if((read_return && (read_fifo_reset || outstanding==0)) || (read_en && outstanding==2047))session_bad<=1;
                if(read_en && read_words<DDR_WORDS)begin
                    if(read_address!=base_address(active_slot)+{4'd0,read_words,3'b000})session_bad<=1;
                    read_words<=read_words+1'b1;
                end
            end
        end
    end
    wire [81:0] descriptor_ddr={descriptor_sequence,descriptor_id,descriptor_time,descriptor_good,
        verdict_sequence,verdict_good};
    wire [81:0] descriptor_hdmi;
    fusion_control_cdc #(.WIDTH(82)) display_metadata(
        .I_source_clk(ddr_clk),.I_dest_clk(hdmi_clk),.I_rst_n(rst_n),.I_commit(1'b1),
        .I_data(descriptor_ddr),.O_data(descriptor_hdmi));
    wire [15:0] hd_sequence,hd_id,hv_sequence;
    wire [31:0] hd_time;
    wire hd_good,hv_good;
    assign {hd_sequence,hd_id,hd_time,hd_good,hv_sequence,hv_good}=descriptor_hdmi;

    reg raw_vs_d,final_vs_d,raw_underflow,armed,running;
    reg [15:0] hdmi_sequence,candidate_sequence,candidate_id,pending_sequence,pending_id,last_id;
    reg [31:0] candidate_delay,candidate_t0,pending_delay,pending_t0,last_t0;
    reg candidate_good,pending_good,pending,last_good;
    reg [19:0] pixel_count;
    wire raw_boundary=raw_vs_d && !raw_hdmi_vs;
    wire final_boundary=final_vs_d && !final_hdmi_vs;
    wire completing_frame=final_hdmi_de && running && pixel_count==PIXELS-1;
    wire incomplete_boundary=final_boundary && (running || armed);
    wire [31:0] measured_age=hdmi_now-hd_time;
    wire [15:0] id_distance=pending_id-last_id;
    always @(posedge hdmi_clk or negedge rst_n)begin
        if(!rst_n)begin
            raw_vs_d<=0;final_vs_d<=0;raw_underflow<=0;armed<=0;running<=0;hdmi_sequence<=0;
            candidate_sequence<=0;candidate_id<=0;candidate_delay<=0;candidate_t0<=0;candidate_good<=0;
            pending_sequence<=0;pending_id<=0;pending_delay<=0;pending_t0<=0;pending_good<=0;pending<=0;
            last_id<=0;last_t0<=0;last_good<=0;pixel_count<=0;
            O_latency_us<=0;O_frame_id<=0;O_valid<=0;O_repeat<=0;O_skip<=0;
        end else begin
            raw_vs_d<=raw_hdmi_vs;final_vs_d<=final_hdmi_vs;
            if(raw_boundary)begin hdmi_sequence<=hdmi_sequence+16'd1;raw_underflow<=output_underflow;end
            else if(output_underflow)raw_underflow<=1;
            if(final_boundary)begin
                armed<=1;running<=0;pixel_count<=0;
                if(running || armed)begin
                    O_valid<=0;O_repeat<=0;O_skip<=0;last_good<=0;pending<=0;
                end
            end
            if(final_hdmi_de)begin
                if(armed)begin
                    armed<=0;running<=1;pixel_count<=1;
                    candidate_sequence<=hdmi_sequence;candidate_id<=hd_id;candidate_t0<=hd_time;
                    candidate_delay<=measured_age;
                    candidate_good<=hd_sequence==hdmi_sequence && hd_good && measured_age<MAX_AGE_US &&
                        !raw_underflow && !output_underflow;
                end else if(running)begin
                    pixel_count<=pixel_count+1'b1;
                    if(pixel_count==PIXELS-1)begin
                        running<=0;pending<=1;pending_sequence<=candidate_sequence;
                        pending_id<=candidate_id;pending_t0<=candidate_t0;pending_delay<=candidate_delay;
                        pending_good<=candidate_good && !raw_underflow && !output_underflow;
                        // Waiting for this frame's retirement must never leave
                        // an old successful sample presented as newly valid.
                        O_valid<=0;O_repeat<=0;O_skip<=0;
                    end
                end else if(pixel_count==PIXELS)begin
                    pending_good<=0;O_valid<=0;O_repeat<=0;O_skip<=0;
                end
            end
            // A late old verdict cannot overwrite a newly completed sample
            // or revive success after a short/empty frame was rejected.
            if(pending && hv_sequence==pending_sequence && !completing_frame && !incomplete_boundary)begin
                pending<=0;O_frame_id<=pending_id;
                O_valid<=pending_good && hv_good;
                O_latency_us<=pending_good && hv_good?pending_delay:0;
                O_repeat<=pending_good && hv_good && last_good && pending_id==last_id && pending_t0==last_t0;
                O_skip<=pending_good && hv_good && last_good && id_distance>1;
                last_good<=pending_good && hv_good;
                if(pending_good && hv_good)begin last_id<=pending_id;last_t0<=pending_t0;end
            end
        end
    end
endmodule

