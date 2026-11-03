"""Use the installed, encrypted Anlogic ERAM model in ModelSim, including GSR."""
from pathlib import Path
import hashlib,json,subprocess,time,sys
sys.stdout.reconfigure(encoding='utf-8')
R=Path(__file__).resolve().parents[1];H=R/'user_source/hdl_source';V=R/'validation/native_curve_model'
V.mkdir(exist_ok=True)
B=Path(r'D:\anlu\altera\14.1S\modelsim_ase\win32aloem')
L=Path(r'D:\anlu\TD_6.2.1_Engineer_6.2.168.116\sim_release\ph1p')
style=(H/'isp/stylize_v5_96.v').read_text(encoding='utf-8')
# Compile the exact production helper text, without unrelated legacy forward
# declarations that the older ModelSim parser rejects in the whole style core.
(V/'median_rom_sources.v').write_text(style[style.index('module median4_eram'):],encoding='utf-8')
steps=[('vmap_init',[B/'vmap.exe','-c']),('vlib',[B/'vlib.exe','work']),('vmap_work',[B/'vmap.exe','work','work']),
 ('vlog',[B/'vlog.exe','-sv','-work','work',L/'ph1p_phy_gsr.v',L/'ph1p_logic_eram.v',
 R/'validation/image_quality_equivalence_tb.v',R/'validation/image_quality_reference.v',R/'validation/median_eram_equivalence_tb.v',
 H/'isp/isp_top.v',V/'median_rom_sources.v',H/'image_curve_rom.v']),
 ('vsim',[B/'vsim.exe','-c','-do','vsim work.PH1P_PHY_GSR work.image_quality_equivalence_tb; onfinish stop; run -all; quit -f']),
 ('vsim_median',[B/'vsim.exe','-c','-do','vsim work.PH1P_PHY_GSR work.median_eram_equivalence_tb; onfinish stop; run -all; quit -f'])]
result={'native_vendor_model':False};start=time.time()
try:
    for name,command in steps:
        p=subprocess.run(list(map(str,command)),cwd=V,capture_output=True,text=True,timeout=120)
        log=p.stdout+p.stderr;(V/(name+'.log')).write_text(log,encoding='utf-8')
        print(name,'exit',p.returncode,log[-1600:],flush=True)
        assert p.returncode==0 and '** Error' not in log and '** Fatal' not in log,(name,log[-1600:])
        if name=='vsim':assert 'IMAGE_QUALITY_EQUIVALENCE_PASS' in log
        if name=='vsim_median':assert 'MEDIAN_ERAM_EQUIVALENCE_PASS' in log
    result['native_vendor_model']=True
except Exception as ex:
    result['error']=str(ex)
result['seconds']=round(time.time()-start,2)
result['source_sha256']={p.relative_to(R).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (R/'user_source').rglob('*') if p.is_file()}
(V/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('NATIVE_CURVE_MODEL_RESULT',json.dumps({k:v for k,v in result.items() if k!='source_sha256'}),flush=True)
if not result['native_vendor_model']:sys.exit(1)
