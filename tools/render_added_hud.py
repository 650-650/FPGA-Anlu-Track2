"""Render the two new HUD pages from RTL; these are not board captures."""
from pathlib import Path
import subprocess
from PIL import Image,ImageDraw

R=Path(__file__).resolve().parents[1]
V=R/'validation'
H=R/'user_source/hdl_source'
IV=Path(r'D:\anlu\iverilog\bin\iverilog.exe')
tb=(V/'fusion_hud_tb.v').read_text(encoding='utf-8')
for name,control,color in [('base_auto','00','00'),('base_cool','00','3c'),('base_warm','00','09'),('edge','38','00'),('aid','58','00')]:
    pixels=V/(name+'_hud_pixels.txt')
    source=tb.replace('module fusion_hud_tb;','module added_hud_render_tb;')
    source=source.replace(".I_control(8'h48)",".I_control(8'h"+control+")")
    source=source.replace(".I_color_control(6'd0)",".I_color_control(6'h"+color+")")
    source=source.replace('.I_debug(4\'b1111)',
        ".I_aid_h_zone(2'd2),.I_aid_v_zone(2'd2),.I_debug(4'b1111)")
    source=source.replace('validation/hud_pixels.txt','validation/'+pixels.name)
    bench=V/(name+'_hud_render_tb.v')
    bench.write_text(source,encoding='ascii')
    binary=bench.with_suffix('.vvp')
    result=subprocess.run([str(IV),'-g2012','-s','added_hud_render_tb','-o',str(binary),
        str(bench),str(H/'fusion_hud.v'),str(H/'fusion_menu_rom.v')],
        cwd=R,text=True,capture_output=True,check=True)
    result=subprocess.run([str(IV.with_name('vvp.exe')),str(binary)],
        cwd=R,text=True,capture_output=True,check=True)
    assert 'FUSION_HUD_PASS' in result.stdout,result.stdout
    img=Image.new('RGB',(1280,130),(32,32,32))
    ImageDraw.Draw(img).text((16,6),
        name.upper()+' HUD - RTL SIMULATION ONLY - NOT A CAMERA OR BOARD CAPTURE',fill='white')
    for line in pixels.read_text().splitlines():
        x,y=map(int,line.split())
        img.putpixel((x,y-600+30),(255,242,0))
    output=V/(name+'_hud_simulation_only.png')
    img.save(output)
    print('HUD_RTL_PREVIEW_PASS',name,output,flush=True)
