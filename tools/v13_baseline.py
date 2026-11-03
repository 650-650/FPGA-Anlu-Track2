"""Locate the exact accepted crop snapshot even after its folder was moved."""
from pathlib import Path
import hashlib,json,os
EXPECTED_BIT='8204e5493bc964a387e34d74af8ac299718320b935b56fbdd113454d0278ac95'
NAME='07_stylize_flame_fusion_v11_sensor_window_fix'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def resolve_baseline(root):
    candidates=[]
    if os.environ.get('FPGA_V13_BASELINE'):candidates.append(Path(os.environ['FPGA_V13_BASELINE']))
    candidates += [root.with_name(NAME),Path(r'D:\Project\FPGA_Work\zuizhongbanben_wrh')/NAME]
    for base in candidates:
        manifest=base/'output/fix_manifest.json'
        if not manifest.is_file():continue
        m=json.loads(manifest.read_text(encoding='utf-8-sig'))
        assert m['sha256']==EXPECTED_BIT,('Wrong crop baseline manifest',str(base))
        bits=[p for p in (base/'output').glob('*.bit') if sha(p)==EXPECTED_BIT]
        assert len(bits)==1,('Missing exact crop baseline bit',str(base))
        assert len(m['source_sha256'])==223
        for rel,h in m['source_sha256'].items():
            assert (base/rel).is_file() and sha(base/rel)==h,('Crop baseline changed',rel)
        return base.resolve()
    raise FileNotFoundError('Exact V11 crop baseline required; set FPGA_V13_BASELINE to its folder')
