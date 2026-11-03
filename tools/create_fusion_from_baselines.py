from pathlib import Path
import hashlib, json, re, shutil

P=Path(r'D:\FPGA_Work\AnlogicCup2026')
B=P/'06_stylize_osd_v3_shadow_denoise'
T=Path(r'D:\Project\FPGA_Work\jingjie2\06_flame_tracking_candidate_v1')
R=P/'07_stylize_flame_fusion_v1'
assert not R.exists(), 'Fusion directory already exists; do not overwrite it'
R.mkdir()
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
orig={}
for label,root in [('v3',B),('flame',T)]:
    files=list((root/'user_source').rglob('*'))+list((root/'td_project').glob('*.al'))+list((root/'output').glob('*.bit'))
    orig[label]={'root':str(root),'sha256':{str(p.relative_to(root)).replace('\\','/'):sha(p) for p in files if p.is_file()}}
shutil.copytree(B/'user_source',R/'user_source')
for name in ['output','tools','validation','docs']:(R/name).mkdir()
(R/'validation/originals_manifest.json').write_text(json.dumps(orig,indent=2,ensure_ascii=False),encoding='utf-8')
project=R/'td_project';project.mkdir()
for file in (B/'td_project').iterdir():
    if file.is_file() and file.suffix in ['.al','.sdc']:shutil.copy2(file,project/file.name)
for run in ['syn_1','phy_1']:
    src=B/'td_project/camera_to_dsi_display_Runs'/run
    dst=project/'camera_to_dsi_display_Runs'/run;dst.mkdir(parents=True)
    for f in src.iterdir():
        if f.is_file() and f.suffix in ['.tcl','.cfg']:shutil.copy2(f,dst/f.name)
for name in ['visual_flame_alarm.v','camera_frame_watchdog.v','alarm_board_io.v']:
    shutil.copy2(T/'user_source/hdl_source'/name,R/'user_source/hdl_source'/name)
for name in ['flame_tracking_tb.v','candidate_color_tb.v','flame_full_resolution_tb.v']:
    shutil.copy2(T/'validation'/name,R/'validation'/name)
for name in ['model_baseline.py','model_denoise.py','test_denoise.py','test_full_size.py','test_line_rtl.py']:
    shutil.copy2(B/'tools'/name,R/'tools'/name)
(R/'docs/按键设计依据.md').write_text((P/'docs/control_plan_20261024/拨码与按键规划_待确认.md').read_text(encoding='utf-8'),encoding='utf-8')
print(R)
