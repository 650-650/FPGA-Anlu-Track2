"""Read-only V13 regression against the accepted V11 sensor-window baseline.

No production files are edited. Fixtures/results are written exclusively to
validation/v13_preservation. Pixel/HUD rendering is verified separately.
"""
from pathlib import Path
import csv,hashlib,importlib.util,json,re,subprocess,time

R=Path(__file__).resolve().parents[1]
from v13_baseline import resolve_baseline
B=resolve_baseline(R)
H=R/'user_source/hdl_source';BH=B/'user_source/hdl_source'
V=R/'validation/v13_preservation'
IV=Path(r'D:\anlu\iverilog\bin\iverilog.exe')

def read(p):return p.read_text(encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def code(s):return re.sub(r'\s+','',re.sub(r'/\*.*?\*/|//[^\n]*','',s,flags=re.S))
def path_norm(s):
    return re.sub(r'"[^"\r\n]*/(curve_srgb|curve_gain|curve_gain_scaled|median_majority|display_tone)\.dat"',
                  lambda m:'"@ROM/'+m[1]+'.dat"',s)
def once(s,old,new):
    assert s.count(old)==1,('Missing or duplicated expected source region',old[:120],s.count(old))
    return s.replace(old,new,1)
def write(p,s):p.write_text(s,encoding='utf-8',newline='\n')

OLD_ALIGN_BODY='''wire [127:0] aligned_camera_data;
wire aligned_camera_valid;
generate if(INPUT_ALIGN_CYCLES>0)begin: input_alignment
reg [127:0] data_pipe[0:INPUT_ALIGN_CYCLES-1];
reg [INPUT_ALIGN_CYCLES-1:0] valid_pipe;
integer n;
always @(posedge I_camera_clk)begin
data_pipe[0]<=I_camera_data;
for(n=1;n<INPUT_ALIGN_CYCLES;n=n+1)data_pipe[n]<=data_pipe[n-1];
end
always @(posedge I_camera_clk or negedge I_rst_n)
if(!I_rst_n)valid_pipe<=0;
else valid_pipe<=(valid_pipe<<1) | {{(INPUT_ALIGN_CYCLES-1){1'b0}},I_camera_valid};
assign aligned_camera_data=data_pipe[INPUT_ALIGN_CYCLES-1];
assign aligned_camera_valid=valid_pipe[INPUT_ALIGN_CYCLES-1];
end else begin: original_input
assign aligned_camera_data=I_camera_data;
assign aligned_camera_valid=I_camera_valid;
end endgenerate
wire S_input_fifo_full;
assign O_observe_frame_start=S_frame_start;
assign O_observe_write_slot=S_video_in_wp;
assign O_observe_overflow=aligned_camera_valid && S_input_fifo_full;'''

VS_NEW='''always @(posedge I_ddr_clk or negedge I_rst_n) begin
if(!I_rst_n)begin
S_video_vsync_1d <= 1'b1;
S_video_vsync_2d <= 1'b1;
S_video_vsync_3d <= 1'b1;
end else begin
S_video_vsync_1d <= I_video_vsync;
S_video_vsync_2d <= S_video_vsync_1d;
S_video_vsync_3d <= S_video_vsync_2d;
end
end'''
VS_OLD='''always @(posedge I_ddr_clk) begin
S_video_vsync_1d <= I_video_vsync;
S_video_vsync_2d <=S_video_vsync_1d;
S_video_vsync_3d <= S_video_vsync_2d;
end'''

def restore_video_in(s):
    s=once(s,'module video_in #(parameter integer INPUT_ALIGN_CYCLES=0)(','module video_in (')
    s=once(s,'    input wire         I_ddr_user_ready,\n    output wire O_observe_frame_start,\n    output wire [1:0] O_observe_write_slot,\n    output wire O_observe_overflow\n','    input wire         I_ddr_user_ready\n')
    a=s.index('    // The complete production ISP');b=s.index('    wire        S_fifo_rst;',a)
    assert code(s[a:b])==code(OLD_ALIGN_BODY),'video_in observer/optional delay block changed'
    s=s[:a]+s[b:]
    s=once(s,'.we         ( aligned_camera_valid ),','.we         ( I_camera_valid     ),')
    s=once(s,'.di         ( aligned_camera_data  ),','.di         ( I_camera_data      ),')
    return once(s,'.full_flag  (S_input_fifo_full),','.full_flag  (),')

def restore_video_out(s,legacy):
    s=legacy.restored_video('video_out.v',s)
    a=s.index('    // The input is the inverse');b=s.index('    assign S_video_frame_start',a)
    assert code(s[a:b])==code(VS_NEW),'Only the specified three-flop reset-to-one change is allowed'
    return s[:a]+VS_OLD+'\n\n'+s[b:]

def restore_telemetry(s):
    s=once(s,'    input wire [31:0] I_latency_us,\n    output reg [19:0] O_latency_bcd,\n','')
    s=once(s,'reg [3:0] field;','reg [2:0] field;')
    s=once(s,'input [3:0] f;','input [2:0] f;')
    s=once(s,'6:value_for={16\'d0,I_exposure};7:value_for={16\'d0,I_gain};default:value_for=I_latency_us;',
               '6:value_for={16\'d0,I_exposure};default:value_for={16\'d0,I_gain};')
    s=once(s,'O_gain_bcd<=0;O_latency_bcd<=0;','O_gain_bcd<=0;')
    s=once(s,'                    8:O_latency_bcd<=next_bcd[23:4];\n','')
    return once(s,'if(field==8)busy<=0;','if(field==7)busy<=0;')

PARAM0_TB=r'''`timescale 1ns/1ps
module preservation_param0_tb;
reg cclk=0,dclk=0;always #5 cclk=~cclk;always #7 dclk=~dclk;
reg rst=0,sof=0,valid=0,ready=1,busy=0,pause=0;reg[127:0]data=0;
wire[156:0]base_state,zero_state,default_state;
video_in ndefault(.I_rst_n(rst),.I_camera_clk(cclk),.I_camera_frame_start(sof),.I_camera_valid(valid),.I_camera_data(data),
 .I_mipi_rx_error(1'b0),.I_ddr_clk(dclk),.I_display_pause(pause),.I_video_out_rd_busy(busy),.I_ddr_user_ready(ready),
 .O_video_in_wr_busy(default_state[156]),.O_video_out_rp(default_state[155:154]),.O_ddr_user_wr_en(default_state[153]),
 .O_ddr_user_addr(default_state[152:128]),.O_ddr_user_wr_data(default_state[127:0]));
video_in #(.INPUT_ALIGN_CYCLES(0)) nzero(.I_rst_n(rst),.I_camera_clk(cclk),.I_camera_frame_start(sof),.I_camera_valid(valid),.I_camera_data(data),
 .I_mipi_rx_error(1'b0),.I_ddr_clk(dclk),.I_display_pause(pause),.I_video_out_rd_busy(busy),.I_ddr_user_ready(ready),
 .O_video_in_wr_busy(zero_state[156]),.O_video_out_rp(zero_state[155:154]),.O_ddr_user_wr_en(zero_state[153]),
 .O_ddr_user_addr(zero_state[152:128]),.O_ddr_user_wr_data(zero_state[127:0]));
reference_video_in old(.I_rst_n(rst),.I_camera_clk(cclk),.I_camera_frame_start(sof),.I_camera_valid(valid),.I_camera_data(data),
 .I_mipi_rx_error(1'b0),.I_ddr_clk(dclk),.I_display_pause(pause),.I_video_out_rd_busy(busy),.I_ddr_user_ready(ready),
 .O_video_in_wr_busy(base_state[156]),.O_video_out_rp(base_state[155:154]),.O_ddr_user_wr_en(base_state[153]),
 .O_ddr_user_addr(base_state[152:128]),.O_ddr_user_wr_data(base_state[127:0]));
integer i,input_checks=0,policy_checks=0;reg[31:0]rng=32'h3196a75c;
always @(posedge cclk)begin #1;
 if(ndefault.U_w128_d512_fifo.we!==valid || ndefault.U_w128_d512_fifo.di!==data ||
    nzero.U_w128_d512_fifo.we!==valid || nzero.U_w128_d512_fifo.di!==data ||
    old.U_w128_d512_fifo.we!==valid || old.U_w128_d512_fifo.di!==data)
    $fatal(1,"default/parameter0 no longer original FIFO input pins");
 input_checks=input_checks+1;
end
always @(posedge dclk)begin #1;
 if(base_state!==zero_state || base_state!==default_state)$fatal(1,"default/parameter0 arbitration/pointers/output changed");
 policy_checks=policy_checks+1;
end
initial begin
 repeat(8)@(negedge cclk);rst=1;
 for(i=0;i<1600;i=i+1)begin
  @(negedge cclk);rng={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};
  data={rng,~rng,rng^32'h5a3c08e1,rng+32'd123};valid=rng[0]||rng[4];sof=i%201==0;
  ready=rng[7]||rng[8];busy=i%89<7;pause=i>800 && i<840;
  if(i==713)rst=0;if(i==719)rst=1;
 end
 @(negedge cclk);valid=0;sof=0;repeat(35)@(negedge cclk);
 $display("V13_PARAM0_PROTECTION_PASS input=%0d policy=%0d",input_checks,policy_checks);$finish;
end
initial begin #100000;$fatal(1,"parameter0 timeout");end
endmodule
// Pin/policy fixture only; generated FIFO/DDR behavior is tested separately.
module w128_d512_fifo(input rst,clkw,clkr,we,re,input[127:0]di,
 output reg[127:0]dout,output valid,full_flag,empty_flag,afull,aempty,output[8:0]wrusedw,rdusedw);
 assign valid=re;assign full_flag=0;assign empty_flag=0;assign afull=0;assign aempty=0;
 assign wrusedw=0;assign rdusedw=300;
 always @(posedge clkr or posedge rst)if(rst)dout<=0;else if(re)dout<=dout+1'b1;
endmodule
'''

VS_TB=r'''`timescale 1ns/1ps
module preservation_vsync_tb;
reg clk=0;always #5 clk=~clk;reg rst=0,vs=1;
wire frame;wire[2:0]syncs;integer events=0,i;
video_out_sync_actual dut(.I_ddr_clk(clk),.I_rst_n(rst),.I_video_vsync(vs),.frame(frame),.syncs(syncs));
always @(posedge clk)begin #1;if(rst && frame)events=events+1;end
initial begin
 repeat(4)@(negedge clk);if(syncs!==3'b111 || frame!==0)$fatal(1,"VS synchronizers must reset to idle one");rst=1;
 repeat(20)@(negedge clk);if(events!=0)$fatal(1,"manufactured startup frame event");
 for(i=0;i<2;i=i+1)begin
  @(negedge clk);vs=0;repeat(6)@(negedge clk);
  vs=1;repeat(6)@(negedge clk);if(events!=i+1)$fatal(1,"real VS pulse lost/duplicated");
 end
 @(negedge clk);rst=0;repeat(3)@(negedge clk);
 if(syncs!==3'b111 || frame!==0)$fatal(1,"subsequent reset not idle one");
 $display("V13_VSYNC_RESET_PROTECTION_PASS real_frame_events=%0d startup_events=0",events);$finish;
end
endmodule
'''

def run_test(name,top,tb,files):
    path=V/(name+'_tb.v');write(path,tb);binary=V/(name+'.vvp');result={}
    for phase,cmd in [('compile',[IV,'-g2012','-s',top,'-o',binary,path,*files]),('run',[IV.with_name('vvp.exe'),binary])]:
        p=subprocess.run(list(map(str,cmd)),cwd=R,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=100,text=True,encoding='utf-8',errors='replace')
        write(V/(name+'_'+phase+'.log'),p.stdout)
        assert p.returncode==0,(name,phase,p.stdout[-4000:])
        if phase=='run':assert '_PROTECTION_PASS' in p.stdout;print(p.stdout.strip(),flush=True)
        result[phase]={'returncode':p.returncode,'log':(V/(name+'_'+phase+'.log')).relative_to(R).as_posix()}
    return result

def verified_timing_exceptions():
    # Exceptions are source-bound proofs, never blanket exemptions.
    reports={}
    style_files=['user_source/hdl_source/isp/stylize_v5_96.v',
                 'user_source/hdl_source/isp/style_guide_v8.v']
    path=R/'validation/style_retiming/structural_result.json';sv=json.loads(read(path))
    assert sv['pass'] is True and len(sv['checks'])>=7
    for rel,h in sv['source_sha256'].items():assert sha(R/rel)==h,('stale structural proof',rel)
    assert sv['tool_sha256']==sha(R/'tools/verify_style_retiming_scope.py')
    reports['style_retiming_scope']={'path':path.relative_to(R).as_posix(),'sha256':sha(path)}
    for label,name in [('style_retiming_quick','quick_result.json'),('style_retiming_full','full_result.json')]:
        path=R/'validation/style_retiming'/name
        v=json.loads(read(path));assert v['pass'] is True
        assert v['tool_sha256']==sha(R/'tools/verify_style_retiming.py')
        for rel,h in v['source_sha256'].items():assert sha(R/rel)==h,('stale style proof',rel)
        assert v['mathematical_identity']['fixed_latency_clocks']==16
        for n,t in v['tests'].items():
            assert t['pass'] is True
            assert t['testbench_sha256']==sha(R/'validation/style_retiming'/n/'tb.sv')
        reports[label]={'path':path.relative_to(R).as_posix(),'sha256':sha(path)}
        if label.endswith('quick'):
            assert {'math','quick_ext0','quick_ext1'}<=set(v['tests'])
        else:
            assert v['tests']['full720p_ext0']['parameters']=={'W':1280,'H':720,'F':4,'EXT':0}
    for rel in style_files:
        ref=R/'validation/reference_v13/isp'/Path(rel).name
        assert path_norm(read(ref))==path_norm(read(B/rel)),('style reference differs from accepted crop',rel)
    path=R/'validation/aid_timing/result.json';v=json.loads(read(path))
    assert v['pass'] is True and v['production_uses_verified_rewrite'] is True
    assert v['current_sha256']==sha(H/'first_aid_detector.v')==v['candidate_sha256']
    assert v['reference_sha256']==sha(BH/'first_aid_detector.v')
    assert v['verifier_sha256']==sha(R/'tools/verify_aid_timing_equivalence.py')
    assert v['exhaustive_rgb_count']==16777216 and v['green_white_bits_compared']==33554432
    assert v['paired_frames']>=32 and v['paired_frame_width']==1280
    for test in v['tests'].values():
        assert test['compile']['returncode']==0 and test['run']['returncode']==0
        log=read(R/test['run']['log']);assert test['output'].strip()==log.strip()
    aid=read(H/'first_aid_detector.v')
    assert aid.count(v['new_expression'])==1
    assert aid.replace(v['new_expression'],v['old_expression'],1)==read(BH/'first_aid_detector.v'), 'aid edits extend beyond the proved expression'
    reports['aid_timing']={'path':path.relative_to(R).as_posix(),'sha256':sha(path)}
    return set(style_files+['user_source/hdl_source/first_aid_detector.v']),reports

def main():
    start=time.time();V.mkdir(parents=True,exist_ok=True)
    import_spec=importlib.util.spec_from_file_location('latency_v12_preservation_fixture',R/'tools/latency_v12_preservation.py')
    legacy=importlib.util.module_from_spec(import_spec);import_spec.loader.exec_module(legacy)
    current={p.relative_to(R).as_posix():sha(p) for p in (R/'user_source').rglob('*') if p.is_file()}
    baseline={p.relative_to(B).as_posix():sha(p) for p in (B/'user_source').rglob('*') if p.is_file()}
    primary_sdc='td_project/camera_to_dsi_display.sdc'
    current[primary_sdc]=sha(R/primary_sdc);baseline[primary_sdc]=sha(B/primary_sdc)
    allowed={'user_source/hdl_source/'+name for name in ['design_top_wrapper.v','video_in.v','video_out.v','fusion_hud.v','fusion_menu_rom.v','fusion_telemetry.v']}
    permitted_path={'user_source/hdl_source/display_contrast.v','user_source/hdl_source/image_curve_rom.v','user_source/hdl_source/isp/stylize_v5_96.v'}
    timing_files,timing_reports=verified_timing_exceptions()
    # Two inherited generated DDR tool logs are not RTL/project inputs. The
    # isolated workcopy intentionally excludes logs; record this explicitly.
    auxiliary={'user_source/hdl_source/ph1p35_ddr/ddr2_drc_check.log',
               'user_source/hdl_source/ph1p35_ddr/ddr2_proc.log'}
    project=read(R/'td_project/camera_to_dsi_display.al')
    assert all(Path(rel).name not in project for rel in auxiliary)
    exact=[];relocated=[];changed=[];equivalent=[];excluded_aux=[]
    for rel,h in baseline.items():
        if rel in auxiliary and rel not in current:excluded_aux.append(rel);continue
        assert rel in current,('Protected baseline file missing',rel)
        if current[rel]==h:exact.append(rel)
        elif rel in allowed:changed.append(rel)
        elif rel in timing_files:equivalent.append(rel)
        else:
            assert rel in permitted_path and path_norm(read(B/rel))==path_norm(read(R/rel)),('Protected source changed',rel)
            relocated.append(rel)
    added=sorted(set(current)-set(baseline))
    assert set(added)=={'user_source/hdl_source/frame_latency_monitor.v','user_source/hdl_source/fusion_chinese_font_rom.v'},('Unexpected production additions',added)
    assert code(restore_video_in(read(H/'video_in.v')))==code(read(BH/'video_in.v'))
    assert code(restore_video_out(read(H/'video_out.v'),legacy))==code(read(BH/'video_out.v'))
    assert code(restore_telemetry(read(H/'fusion_telemetry.v')))==code(read(BH/'fusion_telemetry.v'))
    top=read(H/'design_top_wrapper.v')
    restored=legacy.restored_top(once(top,'        .I_latency_status(latency_hud_status),\n',''))
    assert code(path_norm(restored))==code(path_norm(read(BH/'design_top_wrapper.v'))),'Existing top connections changed'
    suffix='    wire [25:0] color_gains_hdmi;'
    assert code(top[top.index(suffix):])==code(read(BH/'design_top_wrapper.v')[read(BH/'design_top_wrapper.v').index(suffix):]),'Display/ROI/output chain changed'
    # Monitor outputs feed only the atomic UI snapshot, never video/control.
    a=top.index('    wire [31:0] latency_us;');b=top.index('    wire [15:0] xb,yb;',a)
    region=top[a:b];outside=top[:a]+top[b:]
    for wire in ['latency_us','latency_frame_id','latency_valid','latency_repeat','latency_skip','latency_status']:
        assert not re.search(r'\b'+wire+r'\b',outside),('Monitor output escapes UI snapshot',wire)
    assert set(re.findall(r'\b(\w+)\s*<=',region))=={'latency_hud_us','latency_hud_id','latency_hud_flags','latency_hud_status'}
    assert not re.search(r'\bassign\b',re.sub(r'//[^\n]*','',region))
    assert dict(re.findall(r'\.(O_\w+)\(([^)]+)\)',region))=={'O_latency_us':'latency_us','O_frame_id':'latency_frame_id',
        'O_valid':'latency_valid','O_repeat':'latency_repeat','O_skip':'latency_skip','O_status':'latency_status'}
    assert 'video_in u_video_in(' in top and not re.search(r'video_in\s*#',top),'Production overrides direct-input default'
    assert '.ROI_Y0(176),.ROI_Y1(208)' in top and '.I_video_rd_en       ( S_hdmi_window_rd_en  )' in top
    sensor='user_source/hdl_source/uics500_cfg/uics500reg_720p60.v'
    registers={int(a,16):int(v,16) for a,v in re.findall(r"REG_DATA=\{16'h([0-9a-f]+),8'h([0-9a-f]+)\}",read(R/sensor),re.I)}
    pair=lambda a:(registers[a]<<8)|registers[a+1]
    window={'x':[pair(0x3200),pair(0x3204)],'y':[pair(0x3202),pair(0x3206)],
            'output':[pair(0x3208),pair(0x320a)],'hts':pair(0x320c),'vts':pair(0x320e)}
    assert window=={'x':[20,2587],'y':[192,1639],'output':[1280,720],'hts':1600,'vts':1000},window
    # Paired actual telemetry preserves every legacy output; no old HUD test.
    reference=V/'reference_telemetry.v';write(reference,re.sub(r'\bfusion_telemetry\b','reference_telemetry',read(BH/'fusion_telemetry.v')))
    tests={'telemetry':run_test('telemetry','preservation_telemetry_tb',legacy.TELEM_TB.replace('V12_','V13_'),[H/'fusion_telemetry.v',reference])}
    reference=V/'reference_video_in.v';write(reference,re.sub(r'\bvideo_in\b','reference_video_in',read(BH/'video_in.v')))
    tests['default_and_parameter0']=run_test('param0','preservation_param0_tb',PARAM0_TB,[H/'video_in.v',reference])
    # Extract the actual production block, including the new status snapshot.
    a=top.index('    reg [31:0] latency_hud_us;');b=top.index('    frame_latency_monitor u_frame_latency(',a)
    snapshot='''module snapshot_actual(input S_hdmi_pixel_clk,S_hdmi_rst_n,S_hdmi_user,
input [31:0] latency_us,input [15:0] latency_frame_id,input latency_valid,latency_repeat,latency_skip,
input [7:0] latency_status,output [31:0] O_us,output [15:0] O_id,output [2:0] O_flags,output [7:0] O_status);
'''+top[a:b]+'''assign O_us=latency_hud_us;assign O_id=latency_hud_id;assign O_flags=latency_hud_flags;assign O_status=latency_hud_status;
endmodule
'''
    write(V/'snapshot_actual.v',snapshot)
    tb=legacy.SNAPSHOT_TB.replace('V12_','V13_')
    tb=tb.replace('wire[31:0]frozen_us;','reg[7:0]status=0;wire[7:0]frozen_status;wire[31:0]frozen_us;')
    tb=tb.replace('.O_us(frozen_us),','.latency_status(status),.O_status(frozen_status),.O_us(frozen_us),')
    tb=tb.replace('reg[50:0]expected;','reg[58:0]expected;')
    tb=tb.replace('if(!rst)expected=0;else if(frame)expected={latency_us,fid,valid,rep,skip};',
                  "if(!rst)expected=59'h80;else if(frame)expected={latency_us,fid,valid,rep,skip,status};")
    tb=tb.replace('{frozen_us,frozen_id,frozen_flags}!==expected','{frozen_us,frozen_id,frozen_flags,frozen_status}!==expected')
    tb=tb.replace('skip=i[2];frame=1;','skip=i[2];status=8\'h13^i;frame=1;')
    tb=tb.replace('skip=!j[0];','skip=!j[0];status=j;')
    tests['snapshot_with_status']=run_test('snapshot','preservation_snapshot_tb',tb,[V/'snapshot_actual.v',H/'fusion_telemetry.v'])
    vout=read(H/'video_out.v');a=vout.index('    // The input is the inverse');b=vout.index('    assign S_video_frame_start',a)
    sync='''module video_out_sync_actual(input I_ddr_clk,I_rst_n,I_video_vsync,output frame,output [2:0] syncs);
reg S_video_vsync_1d,S_video_vsync_2d,S_video_vsync_3d;
'''+vout[a:b]+'''assign frame=~S_video_vsync_3d & S_video_vsync_2d;
assign syncs={S_video_vsync_3d,S_video_vsync_2d,S_video_vsync_1d};endmodule
'''
    write(V/'video_out_sync_actual.v',sync)
    tests['video_out_sync_reset1']=run_test('vsync','preservation_vsync_tb',VS_TB,[V/'video_out_sync_actual.v'])
    for rel,h in current.items():assert sha(R/rel)==h,('Production mutated during verification',rel)
    for rel,h in baseline.items():assert sha(B/rel)==h,('Baseline mutated during verification',rel)
    algorithms={rel:current[rel] for rel in exact if rel.startswith('user_source/hdl_source/') and
                (rel.endswith('.v') or rel.endswith('.dat')) and not '/ph1p35_ddr/' in rel}
    detection={rel:current[rel] for rel in exact if any(k in rel for k in ['first_aid_detector','visual_flame_alarm','fusion_flame_pipeline','alarm_board_io','camera_frame_watchdog'])}
    result={'pass':True,'baseline':str(B),'scope':'Read-only source protection and scoped RTL regressions; no board acceptance or universal full-pixel-stream equivalence claim.',
            'exact_protected_source_count':len(exact),'rom_path_only_changes':relocated,'allowed_observer_ui_changes':changed,
            'timing_equivalent_sources':equivalent,'timing_equivalence_reports':timing_reports,
            'added_sources':added,'all_baseline_files_present':not excluded_aux,
            'all_baseline_design_inputs_present':True,'excluded_generated_non_input_logs':excluded_aux,'source_readonly_verified':True,
            'all_other_top_connections_restored_exact':True,'display_rgb_style_detector_control_roi_chain_preserved':True,
            'sensor_config_byte_exact':True,'sensor_window':window,'roi':{'y0':176,'y1':208,'read_enable':'S_hdmi_window_rd_en'},
            'video_in_default_alignment_cycles':0,'production_overrides_alignment':False,
            'video_in_original_pins_policy_equal_with_stub':True,
            'video_out_exception':'Only passive observer outputs and asynchronous reset of the three existing VS synchronizer FFs to idle one; startup event behavior intentionally corrected.',
            'monitor_outputs_only_atomic_hud_snapshot':True,'snapshot_includes_status':True,
            'telemetry_original_outputs_equal':True,'sdc_byte_exact':all(current[r]==baseline[r] for r in baseline if r.endswith('.sdc')),
            'detection_alarm_byte_exact_sha256':detection,'protected_algorithm_sha256':algorithms,
            'tests':tests,'source_sha256':current,'baseline_source_sha256':baseline,
            'verifier_sha256':sha(Path(__file__)),'seconds':round(time.time()-start,2),
            'limitations':['Input default/parameter0 paired regression uses a pin/policy FIFO stub, not DDR or generated FIFO simulation.',
                           'The intentional video_out reset1 startup correction is not a claim of cycle-identical startup behavior.',
                           'Chinese HUD has independent production-RTL pixel verification under validation/chinese_hud.',
                           'Actual final timing, resource report and hardware behavior are separate evidence.']}
    write(V/'result.json',json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    with (V/'source_hashes.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f);writer.writerow(['relative_path','classification','baseline_sha256','v13_sha256'])
        for rel in sorted(current):writer.writerow([rel,'ADDED' if rel in added else 'BYTE_IDENTICAL' if rel in exact else 'ROM_PATH_ONLY' if rel in relocated else 'TIMING_EQUIVALENT_VERIFIED' if rel in equivalent else 'ALLOWED_OBSERVER_UI_CHANGE',baseline.get(rel,''),current[rel]])
    print('V13_PRESERVATION_ALL_PASS',json.dumps({'exact':len(exact),'path_only':len(relocated),'allowed_changed':len(changed),'added':len(added),'timing_equivalent':len(equivalent),'seconds':result['seconds']}),flush=True)

if __name__=='__main__':main()
