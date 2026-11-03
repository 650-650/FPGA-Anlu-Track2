from pathlib import Path
R=Path(__file__).resolve().parents[1]
p=R/'user_source/hdl_source/anlogic_logo_rom.v'
new=(R/'validation/logo_resource_probe/hierarchy_split/logo_probe.v').read_text(encoding='utf-8')
new=new.replace('module logo_probe(', 'module anlogic_logo_rom(',1)
p.write_text('// V3 pixel contents and two read clocks preserved; split hierarchy retains block-ROM inference.\n'+new,encoding='utf-8')
print('Lossless two-stage Logo storage applied')
