from pathlib import Path
import hashlib,json,re,subprocess,time,sys
sys.stdout.reconfigure(encoding='utf-8')
R=Path(__file__).resolve().parents[1];V=R/'validation/tone_v8';V.mkdir(exist_ok=True);H=R/'user_source/hdl_source'
IV=Path(r'D:\anlu\iverilog\bin\iverilog.exe');MS=Path(r'D:\anlu\altera\14.1S\modelsim_ase\win32aloem');L=Path(r'D:\anlu\TD_6.2.1_Engineer_6.2.168.116\sim_release\ph1p')
b=(R.parent/'07_stylize_flame_fusion_v7_shadow_clean/user_source/hdl_source/display_contrast.v').read_text(encoding='utf-8')
b=re.sub(r'\bdisplay_tone_rom\b','display_tone_rom_v7_ref',b);b=re.sub(r'\bdisplay_contrast\b','display_contrast_v7_ref',b)
(V/'v7_reference.v').write_text(b,encoding='utf-8');start=time.time();tests={}
steps=[('compile',[IV,'-g2012','-s','tone_v8_tb','-o',V/'tone.vvp',R/'validation/tone_v8_tb.v',H/'display_contrast.v',V/'v7_reference.v']),
 ('unit',[IV.with_name('vvp.exe'),V/'tone.vvp']),('vmap_init',[MS/'vmap.exe','-c']),('vlib',[MS/'vlib.exe','work']),('vmap',[MS/'vmap.exe','work','work']),
 ('vlog',[MS/'vlog.exe','-sv','-work','work',L/'ph1p_phy_gsr.v',L/'ph1p_logic_eram.v',R/'validation/tone_native_v8_tb.v',H/'display_contrast.v']),
 ('native',[MS/'vsim.exe','-c','-do','vsim work.PH1P_PHY_GSR work.tone_native_v8_tb; onfinish stop; run -all; quit -f'])]
for name,cmd in steps:
 p=subprocess.run(list(map(str,cmd)),cwd=V,capture_output=True,text=True,timeout=180);log=p.stdout+p.stderr
 (V/(name+'.log')).write_text(log,encoding='utf-8');assert p.returncode==0 and '** Error' not in log and '** Fatal' not in log,(name,log[-2000:])
 if name=='unit':assert 'TONE_V8_PASS' in log;tests[name]={'pass':True};print(log[-1000:],flush=True)
 if name=='native':assert 'TONE_NATIVE_V8_PASS' in log;tests[name]={'pass':True,'native_vendor_model':True};print(log[-1000:],flush=True)
result={'tests':tests,'native_vendor_model':True,'source_sha256':{p.relative_to(R).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in [H/'display_contrast.v',H/'display_tone.dat']},'seconds':round(time.time()-start,2)}
(V/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('TONE_V8_VERIFICATION_PASS',flush=True)
