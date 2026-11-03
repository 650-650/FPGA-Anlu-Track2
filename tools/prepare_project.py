from pathlib import Path
import re
R=Path(__file__).resolve().parents[1];P=R/'td_project';file=P/'camera_to_dsi_display.al'
# TD and native simulation resolve ERAM initialization paths from different
# working directories. Refresh absolute paths only when this project is moved.
H=R/'user_source/hdl_source'
for name in ['image_curve_rom.v','isp/stylize_v5_96.v','display_contrast.v']:
    target=H/name
    before=target.read_text(encoding='utf-8')
    after=re.sub(r'"[^"\r\n]*/(curve_srgb|curve_gain|curve_gain_scaled|median_majority|display_tone)\.dat"',
        lambda m:'"'+(H/(m[1]+'.dat')).as_posix()+'"',before)
    if after!=before:
        target.write_text(after,encoding='utf-8',newline='\n')
s=file.read_text(encoding='utf-8')
s=re.sub(r'<Project Version="3" Minor="2" Path="[^"]+">',f'<Project Version="3" Minor="2" Path="{P.as_posix()}">',s, count=1)
sources=['fusion_controls.v','fusion_flame_pipeline.v','fusion_hud.v','fusion_telemetry.v','fusion_menu_rom.v','fusion_chinese_font_rom.v',
         'visual_flame_alarm.v','camera_frame_watchdog.v','alarm_board_io.v','wb_gain_control.v',
         'first_aid_detector.v','isp/edge_detect_96.v','image_curve_rom.v','scene_color_control.v','color_luma_preserve.v','display_contrast.v','signal_delay_compact.v','awb_line_memory.v',
         'display_denoise_v8.v','isp/style_guide_v8.v','display_denoise_v9.v','display_cartoon_finish_v9.v','display_denoise_v11.v','frame_latency_monitor.v']
for i,name in enumerate(sources):
    path='../user_source/hdl_source/'+name
    if f'Path="{path}"' not in s:
        entry=f'''            <File Path="{path}"><FileInfo>
                <Attr Name="UsedInSyn" Val="true"/><Attr Name="UsedInP&R" Val="true"/>
                <Attr Name="BelongTo" Val="design_1"/><Attr Name="CompileOrder" Val="{180+i}"/>
            </FileInfo></File>
'''
        s=s.replace('        </Verilog>',entry+'        </Verilog>',1)
cdc='../user_source/constraints_source/fusion_cdc.sdc'
if f'Path="{cdc}"' not in s:
    entry=f'''            <File Path="{cdc}"><FileInfo>
        <Attr Name="UsedInSyn" Val="true"/><Attr Name="UsedInP&R" Val="true"/>
        <Attr Name="BelongTo" Val="constraint_1"/><Attr Name="CompileOrder" Val="3"/>
        </FileInfo></File>
'''
    s=s.replace('        </SDC_FILE>',entry+'        </SDC_FILE>',1)
paths=re.findall(r'<File Path="([^"]+)"',s)
resolved=[]
for path in paths:
    p=(P/path).resolve();assert p.is_relative_to(R) and p.is_file(),p;resolved.append(p)
file.write_text(s,encoding='utf-8',newline='\n')
for name in ['syn_1','phy_1']:
    d=P/'camera_to_dsi_display_Runs'/name
    runtime=re.sub(r' Path="[^"]+"','',s,count=1)
    import os
    runtime=re.sub(r'<File Path="([^"]+)"',lambda m:'<File Path="'+os.path.relpath((P/m[1]).resolve(),d).replace('\\','/')+'"',runtime)
    (d/'camera_to_dsi_display.prj').write_text(runtime,encoding='utf-8',newline='\n')
    config=d/'settings.cfg'
    cfg=config.read_text(encoding='utf-8')
    cfg=re.sub(r'^set SDCList .*$', 'set SDCList {"../../camera_to_dsi_display.sdc" "../../../user_source/constraints_source/fusion_cdc.sdc"}',cfg,flags=re.M)
    config.write_text(cfg,encoding='utf-8',newline='\n')
print('Prepared',len(paths),'internal project references')
