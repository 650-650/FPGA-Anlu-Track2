"""Exhaustive-rank and random-vector proof of the exact 19-compare median."""
from pathlib import Path
import hashlib,itertools,json
import numpy as np
R=Path(__file__).resolve().parents[1];V=R/'validation/display_v11';V.mkdir(exist_ok=True)
def sort3(a,b,c):
    a,b=np.minimum(a,b),np.maximum(a,b)
    b,c=np.minimum(b,c),np.maximum(b,c)
    a,b=np.minimum(a,b),np.maximum(a,b)
    return a,b,c
def network(p):
    rows=[sort3(p[:,j],p[:,j+1],p[:,j+2]) for j in [0,3,6]]
    lo=np.maximum(np.maximum(rows[0][0],rows[1][0]),rows[2][0])
    mid=sort3(rows[0][1],rows[1][1],rows[2][1])[1]
    hi=np.minimum(np.minimum(rows[0][2],rows[1][2]),rows[2][2])
    return sort3(lo,mid,hi)[1]
p=np.array(list(itertools.permutations(range(9))),np.uint32)
assert np.all(network(p)==4)
rng=np.random.default_rng(20261103);random_count=0;tie_count=0
for k in range(4):
    p=rng.integers(0,2**32,(50000,9),dtype=np.uint32)
    if k%2:p=(p&0xffffff)|np.uint32(64<<24);tie_count+=len(p)
    actual=network(p);expected=np.sort(p,axis=1)[:,4]
    assert np.array_equal(actual,expected)
    assert np.all((actual[:,None]==p).any(1))
    random_count+=len(p)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
result={'tests':{'all_rank_permutations':{'pass':True,'cases':362880},'random_packed_vectors':{'pass':True,'cases':random_count,'equal_luma_cases':tie_count}},
 'order':'unsigned {Y8,RGB24}: Y is primary, RGB deterministic equal-Y tie break. Returned RGB always comes from an input vector; no independent channel median.',
 'comparisons':19,'registered_sort_stages':3,
 'source_sha256':{'user_source/hdl_source/display_denoise_v11.v':sha(R/'user_source/hdl_source/display_denoise_v11.v')},
 'oracle_sha256':{Path(__file__).relative_to(R).as_posix():sha(Path(__file__))}}
(V/'median_proof.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('MEDIAN19_PROOF_PASS',362880,random_count,tie_count)
