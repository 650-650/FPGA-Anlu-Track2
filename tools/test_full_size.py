"""Both changed modes at actual 1280x720 RAM depth, including frame updates."""
from pathlib import Path
import hashlib,json,subprocess,time
import numpy as np
from PIL import Image
import model_baseline as old
import model_denoise as new
R=Path(__file__).resolve().parents[1];V=R/'validation/full_size';V.mkdir(exist_ok=True)
RTL=R/'user_source/hdl_source/isp/stylize_v5_96.v'
IVER=Path(r'D:\anlu\iverilog\bin\iverilog.exe');VVP=IVER.with_name('vvp.exe')
from test_denoise import fixture
im=fixture(1280,720)
assert im.shape==(720,1280,3)
rng=np.random.default_rng(926)
im[360:]=np.clip(im[360:].astype(float)*.35+rng.normal(0,12,im[360:].shape),0,255).astype(np.uint8)
Image.fromarray(im).save(V/'full_size_test_input.png')
old.set_size(1280,720);old.save_hex(im,V/'img_in.hex')
def run(args,name,timeout=1200):
    start=time.monotonic()
    with (V/name).open('w') as f:
        subprocess.run([str(x) for x in args],cwd=V,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=timeout)
    return (V/name).read_text(errors='replace'),time.monotonic()-start
run([IVER,'-g2005','-s','tb_stylize_v5_96','-o','full.vvp',R/'validation/tb_stylize_v5_96.v',RTL],'compile.log')
B,Y,M=old.core(im);cases=[]
for mode in (1,2):
    t,seconds=run([VVP,'-n','full.vvp',f'+mode={mode}','+lead=52','+gap=1','+frames=2',f'+out=m{mode}.hex'],f'm{mode}.log')
    assert 'TB_PASS' in t and 'ERROR:' not in t,t[-1000:]
    a=old.load_hex(V/f'm{mode}.hex');assert len(a)==2
    p=dict(old.P0);changed=0
    for f in range(2):
        expected=new.render(B,Y,M,mode,p,im)
        if not np.array_equal(a[f],expected):
            yy,xx=np.nonzero(np.any(a[f]!=expected,axis=-1));y,x=int(yy[0]),int(xx[0])
            raise AssertionError((mode,f,y,x,a[f,y,x].tolist(),expected[y,x].tolist()))
        prior=old.render(B,Y,M,mode,p,im)
        assert np.all(a[f]>=prior),'Darker output introduced'
        if mode==1:
            mask=np.any(prior!=0,axis=-1);assert np.array_equal(a[f][mask],prior[mask]),'Cartoon fill changed'
        changed+=int(np.any(a[f]!=prior,axis=-1).sum())
        p=old.update(p,B,Y,M)
    Image.fromarray(a[-1]).save(V/f'verified_full_size_mode{mode}.png')
    c={'mode':mode,'width':1280,'height':720,'frames':2,'pixels':1843200,'lead':52,'random_gaps':True,
       'exact_match':True,'never_darker_than_v1':True,'changed_pixels':changed,'seconds':round(seconds,2)}
    cases.append(c);print('FULL_SIZE_MODEL_MATCH',json.dumps(c),flush=True)
result={'cases':cases,'pixels':sum(c['pixels'] for c in cases),'exact_match':True,
        'rtl_sha256':hashlib.sha256(RTL.read_bytes()).hexdigest()}
(R/'validation/full_size_result.json').write_text(json.dumps(result,indent=2))
print('FULL_SIZE_TEST_PASS',result['pixels'],flush=True)
