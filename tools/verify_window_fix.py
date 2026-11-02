from pathlib import Path
import hashlib,json,re,subprocess

R=Path(__file__).resolve().parents[1];V=R/'validation';H=R/'user_source/hdl_source/uics500_cfg'
baseline=json.loads((V/'source_baseline.json').read_text(encoding='utf-8'));B=Path(baseline['base'])
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for rel,digest in baseline['original_sha256'].items():assert sha(B/rel)==digest,('original changed',rel)
changes=[]
for rel,digest in baseline['original_sha256'].items():
 if not rel.startswith('user_source/'):continue
 p=R/rel
 if sha(p)!=digest:
  changes.append(rel)
  if rel in ['user_source/hdl_source/image_curve_rom.v','user_source/hdl_source/isp/stylize_v5_96.v','user_source/hdl_source/display_contrast.v']:
   assert p.read_text(encoding='utf-8').replace(R.as_posix(),B.as_posix())==(B/rel).read_text(encoding='utf-8'),rel
  elif rel=='user_source/hdl_source/design_top_wrapper.v':
   expected_top=(B/rel).read_text(encoding='utf-8').replace('display_denoise_v11 #(.H_TOTAL(1650)) u_display_denoise(','display_denoise_v11 #(.H_TOTAL(1650),.ROI_Y0(176),.ROI_Y1(208)) u_display_denoise(')
   assert p.read_text(encoding='utf-8')==expected_top,rel
  else:assert rel in ['user_source/hdl_source/uics500_cfg/uics500reg_720p60.v','user_source/hdl_source/uics500_cfg/uicfgcs500_720p.v'],rel
old=(B/'user_source/hdl_source/uics500_cfg/uics500reg_720p60.v').read_text(encoding='utf-8')
pattern=r"(\d+):\s*REG_DATA=\{16'h([0-9a-f]+),8'h([0-9a-f]+)\}"
original=[(int(i),int(a,16),int(v,16)) for i,a,v in re.findall(pattern,old,re.I)]
assert [i for i,a,v in original]==list(range(116))
expected=[(a,v) for i,a,v in original]
expected=[(a,{0x3202:0x00,0x3203:0xc0,0x3207:0x67}.get(a,v)) for a,v in expected]
expected[114:114]=[(0x4501,0xb4),(0x3221,0x00)]
old_regs={a:v for i,a,v in original};new_regs=dict(expected)
def pair(regs,a):return (regs[a]<<8)|regs[a+1]
old_start,old_end=pair(old_regs,0x3202),pair(old_regs,0x3206)
new_start,new_end=pair(new_regs,0x3202),pair(new_regs,0x3206)
assert (old_start,old_end)==(256,1703) and (new_start,new_end)==(192,1639)
assert old_start-new_start==old_end-new_end==64
assert new_end-new_start+1==old_end-old_start+1==1448
assert 0<=new_start<new_end<1952 and (old_start-new_start)%4==0
for a in [0x3200,0x3204,0x3208,0x320a,0x320c,0x320e,0x3210,0x3212]:
 assert pair(old_regs,a)==pair(new_regs,a),hex(a)
assert pair(new_regs,0x3208)==1280 and pair(new_regs,0x320a)==720
assert new_regs[0x3215]==old_regs[0x3215] and new_regs[0x3220]==old_regs[0x3220]
assert '.BAYER_MODE          ("BGGR")' in (R/'user_source/hdl_source/isp/isp_top.v').read_text(encoding='utf-8')

(V/'expected_init.hex').write_text('\n'.join(f'{a:04x}{v:02x}' for a,v in expected)+'\n',encoding='ascii')
tb='''`timescale 1ns/1ns
module tb;
reg clk=0;always #5 clk=~clk;
reg rst=0;wire scl;tri1 sda;wire done,aedone;
uicfgcs500_720p dut(.I_clk(clk),.I_rst_n(rst),.I_ae_req(1'b0),.I_ae(16'd640),.I_ag(16'd16),
 .O_cam_scl(scl),.IO_cam_sda(sda),.O_cfg_done(done),.O_ae_cfg_done(aedone));
integer cycles=0;
always @(posedge clk)cycles=cycles+1;
initial begin
 repeat(20)@(negedge clk);rst=1;
 wait(done);repeat(20)@(negedge clk);
 if(dut.u_i2c.n!=118 || !aedone)$fatal(1,"wrong init count");
 if(dut.u_i2c.release_cycle-dut.u_i2c.stream_cycle<240000)$fatal(1,"stream delay shortened");
 $display("SENSOR_WINDOW_SEQUENCE_PASS writes=%0d normal_live_before_stream=1 window_shift_sensor_rows=64 delay_cycles=%0d",
 dut.u_i2c.n,dut.u_i2c.release_cycle-dut.u_i2c.stream_cycle);$finish;
end
initial begin #5000000;$fatal(1,"timeout");end
endmodule
// Transport handshake model only: validates the real config FSM/table.
// It does not simulate physical I2C ACK, sensor silicon or image output.
module uii2c #(parameter WMEN_LEN=4,RMEN_LEN=1,CLK_DIV=239)(
input I_clk,I_rstn,input[31:0]I_wr_data,input[7:0]I_wr_cnt,I_rd_cnt,
input I_iic_mode,I_iic_req,output O_iic_scl,inout IO_iic_sda,
output[7:0]O_rd_data,output reg O_iic_busy=0);
reg[23:0]expected[0:117];integer n=0,timer=0,stream_cycle=-1,release_cycle=-1;
reg seen_req=0;wire[23:0]word={I_wr_data[15:8],I_wr_data[23:16],I_wr_data[31:24]};
initial $readmemh("expected_init.hex",expected);
assign O_iic_scl=1;assign IO_iic_sda=1'bz;assign O_rd_data=0;
always @(posedge I_clk)begin
 if(!I_rstn)begin O_iic_busy<=0;timer<=0;seen_req<=0;end
 else begin
  if(!I_iic_req)seen_req<=0;
  if(I_iic_req && !seen_req && !O_iic_busy)begin
   if(n>=118)$fatal(1,"extra transaction");
   if(word!==expected[n] || I_wr_data[7:0]!==8'h6c || I_wr_cnt!=4 || I_rd_cnt!=0)
    $fatal(1,"transaction %0d mismatch got=%h expected=%h",n,word,expected[n]);
   if(word==24'h010001)stream_cycle=tb.cycles;
   if(word==24'h302d00)release_cycle=tb.cycles;
   n=n+1;seen_req<=1;O_iic_busy<=1;timer<=4;
  end else if(O_iic_busy)begin
   if(timer==0)O_iic_busy<=0;else timer<=timer-1;
  end
 end
end
endmodule
'''
(V/'window_sequence_tb.v').write_text(tb,encoding='utf-8')
iv=Path(r'D:\anlu\iverilog\bin\iverilog.exe')
for phase,cmd in [('compile',[iv,'-g2012','-s','tb','-o',V/'window_sequence.vvp',V/'window_sequence_tb.v',H/'uicfgcs500_720p.v',H/'uics500reg_720p60.v',H/'uics500regAE.v',H/'SC500GainTbl.v']),('run',[iv.with_name('vvp.exe'),V/'window_sequence.vvp'])]:
 a=subprocess.run(list(map(str,cmd)),cwd=V,capture_output=True,text=True,timeout=30)
 log=a.stdout+a.stderr;(V/f'window_sequence_{phase}.log').write_text(log,encoding='utf-8')
 assert a.returncode==0,(phase,log)
 if phase=='run':assert 'SENSOR_WINDOW_SEQUENCE_PASS' in log;print(log.strip())
result={'pass':True,'transactions':len(expected),'source_changes':changes,
 'original_unchanged':True,'sensor_window':{'old_y':[old_start,old_end],'new_y':[new_start,new_end],'height':1448,'shift_sensor_rows':64,'shift_output_rows':32,'output':[1280,720],'bayer':'BGGR'},'handshake_stub':True,'physical_i2c_sensor_or_video_simulated':False,
 'scope':'Actual initialization FSM/table transaction sequence and preserved 240000-cycle post-stream delay.',
 'dut_sha256':{p.relative_to(R).as_posix():sha(p) for p in [H/'uicfgcs500_720p.v',H/'uics500reg_720p60.v']}}
(V/'window_sequence_result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
