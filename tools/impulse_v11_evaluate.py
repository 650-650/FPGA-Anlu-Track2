"""Known-truth proposal tests; no production writes and no defect-site claim."""
from pathlib import Path
import hashlib,json
import numpy as np
from impulse_v11_model import repair
from display_v9_model import filter_rgb
R=Path(__file__).resolve().parents[1];V=R/'validation/impulse_v11';V.mkdir(exist_ok=True)
W,H,HT,VT=128,96,160,128;y,x=np.indices((VT,HT));de=(x<W)&(y<H)
overlay=np.zeros_like(de);control=np.zeros(de.shape,np.uint8);cx,cy=64,48
roi=(x>=cx-10)&(x<=cx+10)&(y>=cy-8)&(y<=cy+8)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(im,ctrl=None,over=None,**kw):
    cc=control if ctrl is None else ctrl;oo=overlay if over is None else over
    q,e,d=repair(im.reshape(-1,3),de.ravel(),oo.ravel(),cc.ravel(),HT,**kw)
    return q.reshape(*de.shape,3),e.reshape(de.shape),d
profiles={'global_colour':dict(policy='colour'),'global_bright_or_colour':dict(policy='both'),
          'roi_colour':dict(policy='colour',roi=roi.ravel()),
          'roi_relative_bright_colour':dict(policy='both',roi=roi.ravel(),coherence=16,
             min_distance=64,min_peak=160,min_colour=48,min_colour_y=64,min_white_y=160,min_white_delta=64)}
cases=[]
for shape in [(1,1),(1,2),(2,1),(2,2),(2,4),(3,3)]:
    dh,dw=shape;mask=(x>=cx)&(x<cx+dw)&(y>=cy)&(y<cy+dh)
    for background in [[64,64,64],[200,200,200],[112,82,62]]:
        for hot in [[255,255,0],[255,255,255]]:
            truth=np.zeros((*de.shape,3),np.uint8);truth[:]=background
            im=truth.copy();im[mask]=hot
            row={'kind':'injected_defect','shape':list(shape),'background':background,'hot_rgb':hot,'bad_pixels':int(mask.sum()),'profiles':{}}
            all_profiles={**profiles,'exact_mask_support2':dict(bad_mask=mask.ravel(),min_known_support=2),
                          'exact_mask_support1':dict(bad_mask=mask.ravel(),min_known_support=1)}
            for name,kw in all_profiles.items():
                q,e,d=run(im,**kw)
                row['profiles'][name]={'repaired_bad_pixels':int((e&mask).sum()),
                    'changed_outside_bad_mask':int((e&~mask).sum()),
                    'bad_max_remaining_error':int(np.abs(q.astype(int)-truth.astype(int))[mask].max()),
                    'bad_mean_remaining_error':float(np.abs(q.astype(int)-truth.astype(int))[mask].mean()),
                    'no_external_support_pixels':int((np.asarray(d['support']).reshape(de.shape)[mask]==0).sum())}
            cases.append(row)
features=[]
for name in ['yellow_point','white_point','yellow_horizontal_1','yellow_vertical_1','yellow_diag_1','yellow_diag_2','yellow_edge','gray_ramp']:
    for location in ['inside_gate','outside_gate']:
        xx=cx if location=='inside_gate' else cx+30
        im=np.full((*de.shape,3),64,np.uint8);mask=np.zeros_like(de)
        if name.endswith('point'):mask=(x==xx)&(y==cy)
        elif name=='yellow_horizontal_1':mask=(y==cy)&(np.abs(x-xx)<=8)
        elif name=='yellow_vertical_1':mask=(x==xx)&(np.abs(y-cy)<=8)
        elif name=='yellow_diag_1':mask=(x-xx==y-cy)&(np.abs(x-xx)<=8)
        elif name=='yellow_diag_2':mask=((x-xx-y+cy==0)|(x-xx-y+cy==1))&(np.abs(y-cy)<=8)
        elif name=='yellow_edge':mask=x>=xx
        elif name=='gray_ramp':im[:]=np.repeat((32+(x%96))[:,:,None],3,axis=2)
        if name!='gray_ramp':im[mask]=[255,255,255] if name=='white_point' else [255,255,0]
        baseline=filter_rgb(im.reshape(-1,3),de.ravel(),overlay.ravel(),control.ravel(),HT).reshape(*de.shape,3)
        row={'kind':'legitimate_feature','name':name,'location':location,'profiles':{}}
        for profile,kw in profiles.items():
            q,e,d=run(im,**kw)
            row['profiles'][profile]={'false_repair_pixels':int((e&de).sum()),
                'different_from_unchanged_v9_pixels':int((np.any(q!=baseline,axis=2)&de).sum())}
        features.append(row)
# Every protected page and overlay must remain exact, even for a matching spike.
protected=[]
hotmask=(x==cx)&(y==cy);im=np.full((*de.shape,3),64,np.uint8);im[hotmask]=[255,255,0]
for ctl in [0x28,0x30,0x38,0x40,0x48,0x50,0x58,0x60,0xe0]:
    cc=np.full(de.shape,ctl,np.uint8)
    q,e,_=run(im,ctrl=cc,policy='both',roi=roi.ravel())
    must_bypass=ctl!=0x28
    if must_bypass:assert np.array_equal(q,im) and not e.any()
    protected.append({'control':hex(ctl),'must_bypass':must_bypass,'events':int(e.sum()),'exact_input_rgb':bool(np.array_equal(q,im))})
oo=hotmask.copy();q,e,_=run(im,over=oo,policy='both');assert np.array_equal(q[hotmask],im[hotmask]) and not e[hotmask].any()
# In real noisy flat fields, non-event pixels must still be exact original V9.
rng=np.random.default_rng(20261101);noise_checks=[]
for mean in [32,64,128,208]:
    a=np.clip(mean+rng.normal(0,8,(*de.shape,1))+rng.normal(0,2,(*de.shape,3)),0,255).round().astype(np.uint8)
    old=filter_rgb(a.reshape(-1,3),de.ravel(),overlay.ravel(),control.ravel(),HT).reshape(*de.shape,3)
    for profile,kw in profiles.items():
        q,e,_=run(a,**kw);assert np.array_equal(q[~e],old[~e])
        noise_checks.append({'mean':mean,'profile':profile,'events':int(e.sum()),'non_event_exact_v9':True})
result={'scope':'Proposal-only synthetic truth. Global blind repair is not identifiable from a same-RGB legitimate point. Exact-mask interpolation presumes coordinates/extent which are NOT established on hardware.',
 'coordinate_hypothesis_from_auditor':{'center_approx':[696,159],'uncertainty_xy':[20,12],
  'diagnostic_gate_only':[672,720,144,176],'cannot_use_as_unconditional_bad_mask':True},
 'cases':cases,'legitimate_features':features,'protected_modes':protected,'overlay_exact':True,'flat_noise_non_event_checks':noise_checks,
 'source_sha256':{p.relative_to(R).as_posix():sha(p) for p in [R/'user_source/hdl_source/display_denoise_v9.v']},
 'oracle_sha256':{p.relative_to(R).as_posix():sha(p) for p in [Path(__file__),R/'tools/impulse_v11_model.py',R/'tools/display_v9_model.py']}}
(V/'proposal_result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
lines=['# Display-only impulse proposal: measured limits','',result['scope'],'',
       '| Yellow hot patch on gray64 | Global colour events / bad pixels | Exact mask, support>=2 | Exact mask, support>=1 |', '|---|---:|---:|---:|']
for row in cases:
    if row['background']!=[64,64,64] or row['hot_rgb']!=[255,255,0]:continue
    pp=row['profiles'];lines.append(f"|{row['shape'][0]}x{row['shape'][1]}|{pp['global_colour']['repaired_bad_pixels']}/{row['bad_pixels']}|{pp['exact_mask_support2']['repaired_bad_pixels']}/{row['bad_pixels']}|{pp['exact_mask_support1']['repaired_bad_pixels']}/{row['bad_pixels']}|")
lines+=['', 'All profiles retain the exact existing V9 output outside detected events. SW2/SW3/sketch/edge are exact bypasses in the blind policy; overlay centers are protected. No temporal averaging, no added RAM or changed latency is modeled.', '',
        'The yellow singleton that is correctly repaired as a defect is also removed when labeled as a legitimate yellow punctuation point. A one-pixel diagonal yellow line also produces local blind events; horizontal/vertical continuity protects those orientations. A broad coordinate gate only prevents changes outside that gate; it does not resolve ambiguity inside it.', '',
        'At present the observed approximate center/ROI is not an established bad-pixel map. Do not interpolate the whole 48x32 diagnostic ROI. With an exact 2x4 bad mask, one-support copying can repair all flat-background sites, but strict two-support repair misses interior columns. A 3x3 bad mask has a center with no external cross support and cannot be fully inpainted in one pass.', '',
        'Colour-only blind repair deliberately leaves white/gray bright points and protected sketch/edge paths alone. Thus it cannot promise removal of the same source defect after grayscale/style rendering. A known-site mode-aware repair would need separately validated coordinates and conditional interpolation, including tests on genuine features crossing that site.', '',
        'Practical bounded candidate while only a broad ROI is established: relative-bright/colour impulse with opposing-pair coherence16, max RGB difference64, white Y>=160 and Y-background>=64, or colour peak>=160 and chroma residual>=48. It changes no pixel without a high-contrast event. This permits an attenuated bright core rather than demanding a pure255 yellow template. It also removes a legitimate white/yellow singleton inside the gate, which cannot be distinguished locally.', '',
        'Independent noise_probe.json records strict vs relative decision rates: at background sigma4/8, coherence8 repairs about59.8%/14.6% of injected yellow singletons; coherence16 repairs98.4%/64.6%. Without temporal state this means some frames can retain a noisy-neighbour defect. No total-removal or stable all-frame claim is justified.', '',
        'Before production changes obtain the uniform-pattern and HUD-template audit. Use the approximate ROI only as an event gate, never a fill mask. Preserve the V9 clear filter for every non-event and keep OSD exact. The default model leaves SW2 RGB exact; allow_sw2_display is a separate optional experiment strictly downstream of the detector and must be explicitly selected by the integration owner.']
(V/'proposal_report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8');print('\n'.join(lines))
