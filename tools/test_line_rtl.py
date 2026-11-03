"""Exercise clean weak lines through real RTL over adaptation, without v2 erasure."""
from pathlib import Path
import hashlib,json,subprocess
import numpy as np
from PIL import Image
import model_baseline as old
import model_denoise as new
R=Path(__file__).resolve().parents[1];V=R/'validation/line_rtl';V.mkdir(exist_ok=True)
RTL=R/'user_source/hdl_source/isp/stylize_v5_96.v'
IVER=Path(r'D:\anlu\iverilog\bin\iverilog.exe');VVP=IVER.with_name('vvp.exe')
w,h,n=160,90,45
im=np.full((h,w,3),40,np.uint8)
for x,c in [(30,90),(60,70),(90,56)]:im[12:78,x:x+1]=c
im[25:26,10:150]=180;im[55:56,10:150]=56
old.set_size(w,h);old.save_hex(im,V/'img_in.hex');Image.fromarray(im).save(R/'output/verified_line_input.png')
def run(args,name):
    with (V/name).open('w') as f:
        subprocess.run([str(x) for x in args],cwd=V,stdout=f,stderr=subprocess.STDOUT,timeout=300,check=True)
    return (V/name).read_text(errors='replace')
run([IVER,'-g2005','-s','tb_stylize_v5_96','-P',f'tb_stylize_v5_96.W={w}','-P',f'tb_stylize_v5_96.H={h}',
     '-o','line.vvp',R/'validation/tb_stylize_v5_96.v',RTL],'compile.log')
t=run([VVP,'-n','line.vvp','+mode=2','+lead=52','+gap=1',f'+frames={n}','+out=out.hex'],'run.log')
assert 'TB_PASS' in t and 'ERROR:' not in t
a=old.load_hex(V/'out.hex');assert len(a)==n
B,Y,M=old.core(im);p=dict(old.P0)
for f in range(n):
    expected=new.render(B,Y,M,2,p,im);assert np.array_equal(a[f],expected),f
    prior=old.render(B,Y,M,2,p,im);assert np.all(a[f]>=prior)
    p=old.update(p,B,Y,M)
mask=prior[12:-8,24:-8,0]<220
retained=float((a[-1,12:-8,24:-8,0][mask]<220).mean())
assert retained>.97,retained
Image.fromarray(a[-1]).save(R/'output/verified_weak_lines.png')
result={'frames':n,'pixels':w*h*n,'exact_match':True,'threshold220_line_retention':retained,
        'rtl_sha256':hashlib.sha256(RTL.read_bytes()).hexdigest()}
(R/'validation/line_test_result.json').write_text(json.dumps(result,indent=2))
print('LINE_RTL_PASS',json.dumps(result),flush=True)
