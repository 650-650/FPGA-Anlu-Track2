from pathlib import Path
import hashlib,json,subprocess,time,sys
from PIL import Image,ImageDraw
sys.stdout.reconfigure(encoding='utf-8')
R=Path(__file__).resolve().parents[1];H=R/'user_source/hdl_source';V=R/'validation'
IV=Path(r'D:\anlu\iverilog\bin\iverilog.exe');VVP=IV.with_name('vvp.exe')
reference=(R.parent/'06_stylize_osd_v3_shadow_denoise/user_source/hdl_source/hdmi_mixer.v').read_text(encoding='utf-8')
(V/'hdmi_mixer_reference.v').write_text(reference.replace('module hdmi_mixer #','module hdmi_mixer_reference #',1).replace('anlogic_logo_rom u_anlogic_logo_rom','anlogic_logo_reference u_anlogic_logo_rom'),encoding='utf-8')
logo=(R.parent/'06_stylize_osd_v3_shadow_denoise/user_source/hdl_source/anlogic_logo_rom.v').read_text(encoding='utf-8')
(V/'anlogic_logo_reference.v').write_text(logo.replace('module anlogic_logo_rom(','module anlogic_logo_reference(',1),encoding='utf-8')
tests=[('logo_equivalence_tb',[V/'anlogic_logo_reference.v',H/'anlogic_logo_rom.v']),
       ('fusion_mixer_tb',[V/'hdmi_mixer_reference.v',V/'anlogic_logo_reference.v',H/'hdmi_mixer.v',H/'anlogic_logo_rom.v',H/'osd_char_lib.v']),
       ('fusion_telemetry_tb',[H/'fusion_telemetry.v']),
       ('fusion_hud_tb',[H/'fusion_hud.v',H/'fusion_menu_rom.v']),
       ('aid_hud_tb',[H/'fusion_hud.v',H/'fusion_menu_rom.v'])]
results={}
for name,sources in tests:
    start=time.time();out=V/(name+'.vvp')
    p=subprocess.run([str(IV),'-g2012','-s',name,'-o',str(out),str(V/(name+'.v'))]+list(map(str,sources)),cwd=R,capture_output=True,text=True,timeout=60)
    (V/(name+'_compile.log')).write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0,p.stderr
    p=subprocess.run([str(VVP),str(out)],cwd=R,capture_output=True,text=True,timeout=180)
    (V/(name+'.log')).write_text(p.stdout+p.stderr,encoding='utf-8');print(p.stdout[-600:],flush=True)
    assert p.returncode==0 and 'PASS' in p.stdout,(name,p.stdout)
    results[name]={'pass':True,'seconds':round(time.time()-start,2)}
img=Image.new('RGB',(1280,130),(32,32,32));draw=ImageDraw.Draw(img)
draw.text((16,6),'RTL HUD SIMULATION ONLY - NOT A CAMERA OR BOARD CAPTURE',fill='white')
for line in (V/'hud_pixels.txt').read_text().splitlines():
    x,y=map(int,line.split());img.putpixel((x,y-600+30),(255,242,0))
img.save(V/'hud_simulation_only.png')
(V/'extra_verification_result.json').write_text(json.dumps({'tests':results,'source_sha256':{
    str(p.relative_to(R)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in (R/'user_source').rglob('*') if p.is_file()}},indent=2),encoding='utf-8')
print('EXTRA_VERIFICATION_PASS',flush=True)
