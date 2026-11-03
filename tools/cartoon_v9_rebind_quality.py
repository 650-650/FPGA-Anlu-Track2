"""Retain unchanged model quality metrics only after exact RTL area equivalence.

This is an evidence rebind, not a claimed rerun of the numerical experiments.
It refuses any change outside the selector or any stale/failed RTL evidence.
"""
from pathlib import Path
import hashlib,json,re
R=Path(__file__).resolve().parents[1];V=R/'validation/cartoon_v9'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
style=R/'user_source/hdl_source/isp/stylize_v5_96.v';old=V/'style_before_area_v9.v'
eqp=V/'area_equivalence/result.json';rtlp=V/'result.json';qp=V/'quality_result.json'
eq=json.loads(eqp.read_text());rtl=json.loads(rtlp.read_text());q=json.loads(qp.read_text())
for report in [eq,rtl]:
 assert all(t['pass'] for t in report['tests'].values()),'RTL evidence failed'
 assert all(sha(R/p)==h for p,h in report['source_sha256'].items()),'stale RTL source'
 assert all(sha(R/p)==h for p,h in report['oracle_sha256'].items()),'stale RTL oracle'
without_selector=lambda p:re.sub(r'(?ms)^module style_cartoon_select_v9\b.*?^endmodule\s*','',p.read_text(encoding='utf-8'))
assert without_selector(style)==without_selector(old),'changes beyond equivalent selector'
key=style.relative_to(R).as_posix();old_hash=sha(old);new_hash=sha(style)
assert q['source_sha256'][key]==old_hash,'quality was not generated on saved original V9'
assert all(sha(R/p)==h for p,h in q['source_sha256'].items() if p!=key),'other quality source changed'
assert all(sha(R/p)==h for p,h in q['oracle_sha256'].items()),'quality oracle changed'
original=V/'quality_before_area_result.json'
if not original.exists():original.write_text(qp.read_text(),encoding='utf-8')
q['source_sha256'][key]=new_hash
q['oracle_sha256'][Path(__file__).relative_to(R).as_posix()]=sha(Path(__file__))
q['area_equivalence_rebind']={'quality_metrics_recomputed':False,'reason':'The only RTL change is a selector proven bit-for-bit equal. The independent pixel model and all quality fixtures are unchanged. Real full-pipeline RTL was separately rerun against that model.','original_style_sha256':old_hash,'current_style_sha256':new_hash,'original_quality_result_sha256':sha(original),'selector_equivalence_result_sha256':sha(eqp),'full_pipeline_result_sha256':sha(rtlp),'selector_windows':eq['tests']['selector_equivalence']['windows']}
qp.write_text(json.dumps(q,indent=2),encoding='utf-8');print('CARTOON_V9_QUALITY_REBIND_PASS',new_hash)
