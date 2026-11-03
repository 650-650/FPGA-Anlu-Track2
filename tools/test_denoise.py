"""Run real RTL against independent frame maths and preserve clear mode."""
from pathlib import Path
import hashlib,json,subprocess,sys,time
import numpy as np
from PIL import Image,ImageDraw
import model_baseline as baseline
import model_denoise as denoise

ROOT=Path(__file__).resolve().parents[1]
V=ROOT/'validation'
PREVIEW=V/'model_predictions';PREVIEW.mkdir(exist_ok=True)
IVER=Path(r'D:\anlu\iverilog\bin\iverilog.exe')
VVP=IVER.with_name('vvp.exe')
RTL=ROOT/'user_source/hdl_source/isp/stylize_v5_96.v'

def run(args,log,timeout=180):
    started=time.monotonic()
    with (V/log).open('w',encoding='utf-8') as f:
        proc=subprocess.run([str(a) for a in args],cwd=V,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
    result=(V/log).read_text(encoding='utf-8',errors='replace')
    if proc.returncode: raise RuntimeError(f'{log}: exit {proc.returncode}\n{result[-1800:]}')
    return result,time.monotonic()-started

def fixture(w,h):
    y,x=np.mgrid[:h,:w]
    image=np.stack([40+x*150//w,60+y*100//h,80+x*100//w],-1).astype(np.uint8)
    im=Image.fromarray(image);d=ImageDraw.Draw(im)
    d.rectangle((w//2,8,w-12,h-10),fill=(184,174,160),outline=(30,35,40),width=3)
    d.line((10,8,w//2-5,h-12),fill=(240,240,240),width=3)
    a=np.asarray(im).astype(np.int16)
    rng=np.random.default_rng(20261024)
    a+=rng.integers(-16,17,a.shape)
    return np.clip(a,0,255).astype(np.uint8)

def main():
    w,h,frames=160,90,45
    baseline.set_size(w,h)
    image=fixture(w,h);baseline.save_hex(image,V/'img_in.hex')
    Image.fromarray(image).save(V/'test_input.png')
    cmd=[IVER,'-g2005','-s','tb_stylize_v5_96','-P',f'tb_stylize_v5_96.W={w}',
         '-P',f'tb_stylize_v5_96.H={h}','-o','denoise_test.vvp','tb_stylize_v5_96.v',RTL]
    run(cmd,'denoise_compile.log')
    B2,Y2,mag=baseline.core(image)
    cases=[]
    for mode,lead,gap in [(0,52,1),(1,52,1),(2,52,1),(2,0,1),(3,0,1)]:
        name=f'm{mode}_l{lead}_g{gap}'
        t,seconds=run([VVP,'-n','denoise_test.vvp',f'+mode={mode}',f'+frames={frames}',
                       f'+lead={lead}',f'+gap={gap}',f'+out={name}.hex'],f'{name}.log')
        assert 'TB_PASS' in t and 'ERROR:' not in t,t[-1500:]
        data=baseline.load_hex(V/f'{name}.hex')
        assert len(data)==frames
        p=dict(baseline.P0)
        for f in range(frames):
            expected=denoise.render(B2,Y2,mag,mode,p,image)
            if not np.array_equal(data[f],expected):
                yy,xx=np.nonzero(np.any(data[f]!=expected,axis=-1));y0,x0=int(yy[0]),int(xx[0])
                raise AssertionError(f'{name} frame={f} bad={len(yy)} first={y0,x0} rtl={data[f,y0,x0]} expected={expected[y0,x0]} p={p}')
            if mode in (0,3):assert np.array_equal(data[f],image), 'Clear mode changed'
            p=baseline.update(p,B2,Y2,mag)
        Image.fromarray(data[-1]).save(PREVIEW/f'verified_mode{mode}.png')
        c={'mode':mode,'lead':lead,'random_gaps':bool(gap),'frames':frames,
           'pixels':frames*w*h,'seconds':round(seconds,2),'exact_match':True}
        cases.append(c);print('MODEL_MATCH',json.dumps(c),flush=True)
    summary={'cases':cases,'total_compared_pixels':sum(c['pixels'] for c in cases),
             'clear_mode_exact':True,'latency_cycles':16,
             'rtl_sha256':hashlib.sha256(RTL.read_bytes()).hexdigest()}
    (V/'denoise_test_result.json').write_text(json.dumps(summary,indent=2))
    print('DENOISE_TEST_PASS',summary['total_compared_pixels'],flush=True)

if __name__=='__main__':main()
