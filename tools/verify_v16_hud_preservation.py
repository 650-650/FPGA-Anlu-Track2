"""Re-simulate read-only V15 HUD and compare retained V16 pixels.

V16 may alter only the first row of SW1 panels 4..7. Every other pixel of
the original 51 cases, and rows 2..4 of all 20 new level cases, must match.
Neither the V15 tree nor the teammate tree is written by this verifier.
"""
from pathlib import Path
import hashlib,json,subprocess,time
import verify_chinese_hud as hud

R=Path(__file__).resolve().parents[1]
B=R.with_name('07_stylize_flame_fusion_v15_ddr_latency_final')
N=R/'validation/chinese_hud'
V=R/'validation/v16_hud_preservation'
O=V/'baseline_sim'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def write(p,s):p.write_text(s,encoding='utf-8',newline='\n')
def rows(p):
    values=p.read_text().splitlines()
    assert len(values)==180,(p,len(values))
    return values

def main():
    start=time.time();O.mkdir(parents=True,exist_ok=True)
    files=[B/'user_source/hdl_source'/p.name for p in hud.FILES]
    old_result=json.loads((B/'validation/chinese_hud/result.json').read_text(encoding='utf-8'))
    new_result=json.loads((N/'result.json').read_text(encoding='utf-8'))
    assert new_result['status']=='PASS' and new_result['page_cases']==71
    assert new_result['style_level_cases']==20
    for p in hud.FILES:
        assert sha(p)==new_result['sources'][str(p.relative_to(R))],('V16 sources changed',p)
    for p in files:
        assert sha(p)==old_result['sources'][str(p.relative_to(B))],('V15 sources changed',p)
    baseline_hashes={str(p.relative_to(B)):sha(p) for p in files}
    current_hashes={str(p.relative_to(R)):sha(p) for p in hud.FILES}
    common,cases=hud.make_cases()
    legacy=[c for c in cases if not c['name'].startswith('style_')]
    assert len(legacy)==51
    # Reuse pixel capture timing, with the sole V16-only input disconnected
    # because V15 predates remembered levels. V15 source remains untouched.
    tb=hud.TB_HEAD.replace(' .I_style_levels(style_levels),\n','')
    assert '.I_style_levels' not in tb
    for case in legacy:
        tb+='@(negedge clk);'+hud.assignments(case)
        tb+=f'render_page("{(O/(case["name"]+".hex")).as_posix()}");\n'
    tb+='$display("BASELINE_V15_HUD_RTL_PASS");$finish;\nend\nendmodule\n'
    bench=O/'v15_hud_tb.v';binary=O/'v15_hud_tb.vvp';write(bench,tb)
    result=subprocess.run([str(hud.IV),'-g2012','-Wall','-s','chinese_hud_tb',
        '-o',str(binary),str(bench),*[str(p) for p in files]],cwd=R,text=True,capture_output=True,check=True)
    write(O/'compile.log',result.stdout+result.stderr)
    with (O/'simulation.log').open('w',encoding='utf-8') as log:
        subprocess.run([str(hud.VVP),str(binary)],cwd=R,text=True,stdout=log,stderr=subprocess.STDOUT,check=True)
    assert 'BASELINE_V15_HUD_RTL_PASS' in (O/'simulation.log').read_text()
    exact=[];first_row_only=[];level_tails=[];total=0
    # Removing exactly y=552..583 allows the first text row to change while
    # still checking top margins, row gaps, and all remaining text pixels.
    keep=[y for y in range(180) if not 552<=540+y<584]
    for case in legacy:
        name=case['name'];old=rows(O/(name+'.hex'));new=rows(N/(name+'.hex'))
        if hud.panel(case['control']) in (4,5,6,7):
            assert old!=new,('SW1 level/help row did not change',name)
            assert all(old[y]==new[y] for y in keep),('SW1 preserved pixels changed',name)
            first_row_only.append(name);total+=len(keep)*1280
        else:
            assert old==new,('non-SW1 HUD pixel regression',name)
            exact.append(name);total+=180*1280
        # The independently rerun baseline must also equal delivered V15.
        assert rows(B/'validation/chinese_hud'/(name+'.hex'))==old,('V15 delivered pixel mismatch',name)
    for case in cases:
        if not case['name'].startswith('style_'):continue
        mode=hud.panel(case['control'])-4
        old=rows(O/(f'page_{mode+4:02}'+'.hex'));new=rows(N/(case['name']+'.hex'))
        assert all(old[y]==new[y] for y in keep),('level case preserved pixels changed',case['name'])
        level_tails.append(case['name']);total+=len(keep)*1280
    assert len(exact)==47 and len(first_row_only)==4 and len(level_tails)==20
    assert baseline_hashes=={str(p.relative_to(B)):sha(p) for p in files}
    assert current_hashes=={str(p.relative_to(R)):sha(p) for p in hud.FILES}
    result=dict(status='PASS',scope=__doc__,baseline=str(B),
        fresh_baseline_rtl_cases=51,non_sw1_whole_pages_identical=exact,
        sw1_only_first_row_changed=first_row_only,level_case_remaining_pixels_identical=level_tails,
        preserved_pixels_compared=total,allowed_changed_y=[552,583],
        baseline_sources=baseline_hashes,current_sources=current_hashes,
        baseline_result_sha256=sha(B/'validation/chinese_hud/result.json'),
        new_result_sha256=sha(N/'result.json'),verifier_sha256=sha(Path(__file__)),
        elapsed_seconds=round(time.time()-start,2),
        limitation='RTL pixel preservation only; no TD timing or hardware acceptance from this verifier')
    write(V/'result.json',json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('V16_HUD_PRESERVATION_PASS',len(exact),'whole pages;',len(first_row_only)+len(level_tails),
          'SW1 retained regions;',total,'pixels;',result['elapsed_seconds'],'seconds')

if __name__=='__main__':main()
