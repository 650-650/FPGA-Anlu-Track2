"""Strict transparent50 -> selector1b27 -> folded8abf quality evidence chain.

Numerical quality metrics are preserved, not recomputed. Every retained model
and fixture hash, actual source snapshot, fresh real-RTL proof and structural
change boundary is checked before the compact production binding is written.
"""
from pathlib import Path
import hashlib,json,re
R=Path(__file__).resolve().parents[1];V=R/'validation/cartoon_v9'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
S=R/'user_source/hdl_source/isp/stylize_v5_96.v';A=V/'style_before_area_v9.v';F=V/'style_before_fold_v9.v'
expected=[(A,'50e758f0c6b326f8a4e7d11aeb33c3e32a56b71a672d1f5f25af9f81c4177001'),(F,'1b2741d42dd9bf41180f9e81d769a076b8af63b540b68602f36adc0dc156dbc7'),(S,'8abf903b9e62fc18618da80fbdace6179e692d06d786dd9852a985e952f723fe')]
for p,h in expected:assert sha(p)==h,(str(p),'unexpected source')
reports={name:V/path for name,path in [('model_rtl','result.json'),('selector','area_equivalence/result.json'),('fold','fold_equivalence/result.json')]}
data={}
for name,p in reports.items():
 d=read(p);assert all(t['pass'] for t in d['tests'].values()),(name,'failed RTL evidence')
 assert all(sha(R/f)==h for f,h in d['source_sha256'].items()),(name,'stale source')
 assert all(sha(R/f)==h for f,h in d['oracle_sha256'].items()),(name,'stale oracle')
 data[name]=d
# The first change is restricted to the selector. Current8abf retains the
# exact selector of before-fold1b27, so its fresh selector-vs50 proof covers it.
texts=[p.read_text(encoding='utf-8') for p in [A,F,S]]
selector=lambda s:re.search(r'(?ms)^module style_cartoon_select_v9\b.*?^endmodule',s).group(0)
without=lambda s:re.sub(r'(?ms)^module style_cartoon_select_v9\b.*?^endmodule\s*','',s)
assert without(texts[0])==without(texts[1]),'unexpected pre-fold changes outside selector'
assert selector(texts[1])==selector(texts[2]),'fold changed selector'
# Restore only the row-sum retiming and its three data declarations/uses. This
# excludes any hidden change to frame control, guide, sketch, edge or ink.
old_function=re.search(r'(?ms)^function \[23:0\] cartoon_gaussian;.*?^endfunction',texts[1]).group(0)
restored,n=re.subn(r'(?ms)^function \[89:0\] cartoon_rows;.*?^endfunction\s*function \[23:0\] cartoon_gaussian_rows;.*?^endfunction',lambda m:old_function,texts[2]);assert n==1
for a,b in [
 ('reg[359:0]c1_rows;reg[3:0]c1_protect;','reg[863:0]c1_neighbours;reg[3:0]c1_protect;'),
 ('c1_rows[359-90*k-:90]<=cartoon_rows(cartoon_selected[863-216*k-:216]);c1_protect[3-k]<=cartoon_protected[3-k];','c1_neighbours[863-216*k-:216]<=cartoon_selected[863-216*k-:216];c1_protect[3-k]<=cartoon_protected[3-k];'),
 ('default:c2_px[95-24*k-:24]<=cartoon_gaussian_rows(c1_rows[359-90*k-:90]);','default:c2_px[95-24*k-:24]<=cartoon_gaussian(c1_neighbours[863-216*k-:216]);')]:
 assert restored.count(a)==1,a;restored=restored.replace(a,b)
assert restored==texts[1],'fold changes extend beyond row-sum retiming'
original=V/'quality_before_area_result.json';q=read(original);key=S.relative_to(R).as_posix()
assert q['source_sha256'][key]==sha(A),'quality base is not the actual50 snapshot'
assert all(t['pass'] for t in q['tests'].values()),'original quality tests failed'
assert all(sha(R/f)==h for f,h in q['source_sha256'].items() if f!=key),'other quality source changed'
assert all(sha(R/f)==h for f,h in q['oracle_sha256'].items()),'quality model/fixture changed'
q['source_sha256'][key]=sha(S)
q['source_sha256'][A.relative_to(R).as_posix()]=sha(A)
q['source_sha256'][F.relative_to(R).as_posix()]=sha(F)
q['oracle_sha256'][Path(__file__).relative_to(R).as_posix()]=sha(Path(__file__))
q['compact_equivalence_rebind']={'quality_metrics_recomputed':False,'original_quality_result':original.relative_to(R).as_posix(),'original_quality_result_sha256':sha(original),'reason':'The independent numerical model and original quality fixtures are byte-for-byte unchanged. Actual source snapshots show selector-only50->1b27 and row-retiming-only1b27->8abf changes. Fresh real selector RTL, real all-mode/full-width fold RTL and full production RTL-vs-model tests pass.','stages':[{'from':sha(A),'to':sha(F),'kind':'exact selector arithmetic reformulation; code outside selector identical','evidence':reports['selector'].relative_to(R).as_posix(),'evidence_sha256':sha(reports['selector']),'windows':data['selector']['tests']['selector_equivalence']['windows']},{'from':sha(F),'to':sha(S),'kind':'full-precision Gaussian row sums moved across existing registers, no rounding or latency change','evidence':reports['fold'].relative_to(R).as_posix(),'evidence_sha256':sha(reports['fold']),'pixels':sum(t['pixels'] for t in data['fold']['tests'].values())}],'current_real_rtl_model_result':reports['model_rtl'].relative_to(R).as_posix(),'current_real_rtl_model_result_sha256':sha(reports['model_rtl']),'current_real_rtl_model_pixels':sum(t['pixels'] for t in data['model_rtl']['tests'].values()),'superseded_inherited_candidate_result':'fold_candidate/result.json retains old production-path binding and is not active compact evidence; use fold_equivalence/result.json.'}
q['scope']='Numerical metrics originally computed on style50 and transparently retained through the exact compact source/RTL equivalence chain; not numerically recomputed on compact. '+q['scope']
(V/'quality_result.json').write_text(json.dumps(q,indent=2),encoding='utf-8')
print('CARTOON_V9_COMPACT_QUALITY_REBIND_PASS',sha(S))
