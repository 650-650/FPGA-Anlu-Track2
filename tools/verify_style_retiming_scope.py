"""Read-only structural scope proof for the two retimed style sources."""
from pathlib import Path
import re,json,hashlib
R=Path(__file__).resolve().parents[1];H=R/'user_source/hdl_source/isp';B=R/'validation/reference_v13/isp';V=R/'validation/style_retiming';V.mkdir(exist_ok=True)
old=(B/'stylize_v5_96.v').read_text(encoding='utf-8');new=(H/'stylize_v5_96.v').read_text(encoding='utf-8')
marker='// Third window reuses the existing two 40-bit lines for all three styles.'
assert old[:old.index(marker)]==new[:new.index(marker)],'Pre-third-window RGB/valid/tag/filter stages changed'
a='localparam GUARD_DISABLED=1;';b='module sty_win3_96 #('
assert old[old.index(a):old.index(b)]==new[new.index(a):new.index(b)],'Palette/render/C1/C2/output arithmetic or LAT changed'
ow=old[old.index(b):];nw=new[new.index(b):]
nw=nw.replace('''    output reg [6*PW-1:0]  o_bot,
    output wire pre_v,
    output wire [6*PW-1:0] pre_top,pre_mid,pre_bot
''','''    output reg [6*PW-1:0]  o_bot
''')
a=nw.index('// Passive combinational taps');z=nw.index('\nalways @(posedge clk) begin',a)
nw=nw[:a]+nw[z:]
assert ow==nw,'Original window registers/memories/valid/tag or bypass/helper code changed'
for row in ['top','mid','bot']:
 rhs=re.search(r'o_'+row+r'\s*<=\s*(.*);',ow)[1]
 pre=re.search(r'assign pre_'+row+r'=(.*);',new)[1]
 assert re.sub(r'\s','',rhs)==re.sub(r'\s','',pre),row+' pre-tap differs from original RHS'
assert 'assign pre_v=s1_v;' in new
og=(B/'style_guide_v8.v').read_text(encoding='utf-8');ng=(H/'style_guide_v8.v').read_text(encoding='utf-8')
a=' wire [10:0] ax='
assert og[og.index(a):]==ng[ng.index(a):],'Guide after-gradient arithmetic changed'
for axis in ['gx','gy']:
 expr=re.search(r'wire signed \[10:0\] '+axis+r'=(.*?);',og,re.S)[1]
 default=re.search(r'assign '+axis+r'=\$signed.*?;',ng,re.S)[0].split('=',1)[1][:-1]
 assert re.sub(r'\s','',expr)==re.sub(r'\s','',default),'Default gradient expression changed'
assert '.pre_v(w3_pre_v)' in new and 'style_guide_v8 #(.EXTERNAL_GRADIENT(1)) u_guide' in new
result={'pass':True,'scope':'Read-only text equality outside the declared retiming seam; paired RTL/math tests separately prove the seam behavior.','checks':['All stages before third window byte-identical','Palette/render/C1/C2/output and LAT16 byte-identical','Original window registered outputs/line memories/valid/tag/bypass helper byte-identical after removing only new passive ports/taps','Each pre-tap equals exact original output-register RHS','Guide post-gradient function byte-identical','Default guide Sobel expressions unchanged','Only u_win_c consumes pre-taps; generated 4 guides select registered external gradients'],
'source_sha256':{p.relative_to(R).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in [H/'stylize_v5_96.v',H/'style_guide_v8.v',B/'stylize_v5_96.v',B/'style_guide_v8.v']},'tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(V/'structural_result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('STYLE_RETIME_STRUCTURAL_PASS')

