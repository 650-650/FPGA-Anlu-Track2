from pathlib import Path
import json,re,hashlib,shutil
from datetime import datetime
from zoneinfo import ZoneInfo

R=Path(__file__).resolve().parents[1];O=R/'output';V=R/'validation';P=R/'td_project/camera_to_dsi_display_Runs/phy_1'
def read(p):return p.read_text(encoding='utf-8',errors='replace')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
b=json.loads(read(V/'source_baseline.json'));B=Path(b['base'])
for rel,digest in b['original_sha256'].items():assert sha(B/rel)==digest,('original modified',rel)
semantic_changes={'user_source/hdl_source/uics500_cfg/uicfgcs500_720p.v','user_source/hdl_source/uics500_cfg/uics500reg_720p60.v'}
path_only={'user_source/hdl_source/image_curve_rom.v','user_source/hdl_source/isp/stylize_v5_96.v','user_source/hdl_source/display_contrast.v'}
for rel,digest in b['original_sha256'].items():
 if not rel.startswith('user_source/') or rel in semantic_changes:continue
 if rel in path_only:
  assert read(R/rel).replace(R.as_posix(),B.as_posix())==read(B/rel),('unexpected image-pipeline change',rel)
 elif rel=='user_source/hdl_source/design_top_wrapper.v':
  assert read(R/rel)==read(B/rel).replace('display_denoise_v11 #(.H_TOTAL(1650)) u_display_denoise(','display_denoise_v11 #(.H_TOTAL(1650),.ROI_Y0(176),.ROI_Y1(208)) u_display_denoise('),('unexpected top change',rel)
 else:assert sha(R/rel)==digest,('unexpected protected source change',rel)
test=json.loads(read(V/'window_sequence_result.json'));assert test['pass']
for rel,digest in test['dut_sha256'].items():assert sha(R/rel)==digest,('DUT changed after test',rel)
roi=json.loads(read(V/'v11_roi_result.json'));assert roi['pass']
for rel,digest in roi['dut_sha256'].items():assert sha(R/rel)==digest,('ROI DUT changed after test',rel)
syn=read(P.parent/'syn_1/build_console.log');phy=read(P/'build_console.log')
assert 'FUSION_BUILD_STAGE_PASS' in syn and 'FUSION_BUILD_STAGE_PASS' in phy
assert 'finish command "bitgen' in phy
assert not re.search(r'(?mi)\bERROR\s*:|license checkout failed',syn+'\n'+phy)
critical=re.findall(r'^.*CRITICAL-WARNING:.*$',phy,re.M)
baseline_critical=re.findall(r'^.*CRITICAL-WARNING:.*$',read(B/'td_project/camera_to_dsi_display_Runs/phy_1/build_console.log'),re.M)
added_critical=sorted(set(critical)-set(baseline_critical))
assert not added_critical,('new critical warnings require review',added_critical)
t=read(P/'camera_to_dsi_display_phy.ts')
timing={k:float(re.search(rf'{k}:\s*([-\d.]+)ns',t)[1]) for k in ['SWNS','STNS','HWNS','HTNS']}
assert timing['SWNS']>=0 and timing['HWNS']>=0 and timing['STNS']==timing['HTNS']==0,('TIMING_FAILED',timing)
area=read(P/'camera_to_dsi_display_phy.area');resources={}
for key in ['lut6','slice','slice reg','eram','dsp']:
 m=re.search(r'^\s*#'+re.escape(key)+r'\s+(\d+)\s+out of\s+(\d+)',area,re.M);assert m,key
 used,total=map(int,m.groups());assert used<=total
 resources[key]={'used':used,'total':total}
rom_paths=re.findall(r'^SYN-2541[^\r\n]*Reading BRAM[^\r\n]*init file[^\r\n]*',syn,re.M)
assert len(rom_paths)==9 and all('07_stylize_flame_fusion_v11_sensor_window_fix' in line for line in rom_paths),('external ROM path',rom_paths)
bit=P/'camera_to_dsi_display.bit';assert bit.stat().st_size>1000000
assert bit.stat().st_mtime>max(p.stat().st_mtime for p in (R/'user_source').rglob('*') if p.is_file()),'stale bit'
source={p.relative_to(R).as_posix():sha(p) for p in (R/'user_source').rglob('*') if p.is_file()}
dst=O/'stylize_flame_fusion_v11_sensor_window_fix.bit';assert not dst.exists(),'output already exported'
shutil.copy2(bit,dst);assert sha(dst)==sha(bit)
for name in ['camera_to_dsi_display_phy.ts','camera_to_dsi_display_phy.area']:
 shutil.copy2(P/name,O/name)
result={'date':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),'kind':'sensor_window_workaround_candidate_pending_board_acceptance','bit':str(dst),
 'sha256':sha(dst),'bytes':dst.stat().st_size,'timing_ns':timing,'resources':resources,
 'original_unchanged':True,'source_preservation_verified':True,'sequence_test':test,'v11_roi_test':roi,'source_sha256':source,
 'critical_warnings':critical,'baseline_critical_warnings':baseline_critical,'added_critical_warnings':added_critical,
 'programmed':False,'observed_on_board':False,'black_spot_resolved_on_board':False,
 'pending':['Normal live orientation and 1280x720 picture','Black spot absent in clear/cartoon/sketch/edge modes','Accept the slight framing shift and test light changes']}
(O/'fix_manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
(O/'修正版构建记录.md').write_text(f'''# V11 摄像头窗口修正版

构建完成：{result['date']}。

用途：上移采集窗口规避异常底缘。已修改代码，未烧录；尚待实板确认黑斑是否消失。

可下载文件：`stylize_flame_fusion_v11_sensor_window_fix.bit`（{result['bytes']} 字节）。

SHA256：`{result['sha256']}`。

TD 综合、布线、bitgen 完成；布线后 Setup WNS={timing['SWNS']} ns、Hold WNS={timing['HWNS']} ns，两项 TNS 均为 0。

初始化顺序检查通过：118 笔写入，普通图像/正常方向设置早于 stream-on，垂直起止均上移 64 个传感器行，保留 240000 拍以上的原等待。该检查使用传输握手替身，不证明真实摄像头 ACK 或图像输出。

正式 V11 源文件和 bit 哈希检查未改变。芯片/板上和长时间稳定性尚待验证。

V11 的显示黄点修正区域已同步下移 32 行，算法和保护规则保持。

操作入口：上一级 `README_先做这一步.md`。BitWriter 只使用 `PROGRAM_SRAM`，SW1-SW4 全下，下载后等待约 10 秒；确认正常方向实景，观察底部黑斑是否消失，再检查各风格与光照变化。
''',encoding='utf-8')
print(json.dumps({k:result[k] for k in ['bit','sha256','timing_ns','resources','programmed']},ensure_ascii=True))
