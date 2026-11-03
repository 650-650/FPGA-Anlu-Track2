"""Exhaustive channel pairs and random structured windows vs pre-area V9 RTL."""
from pathlib import Path
import hashlib,json,re,subprocess,time
R=Path(__file__).resolve().parents[1];V=R/'validation/cartoon_v9/area_equivalence';V.mkdir(exist_ok=True)
S=R/'user_source/hdl_source/isp/stylize_v5_96.v';OLD=R/'validation/cartoon_v9/style_before_area_v9.v';IV=Path(r'D:\anlu\iverilog\bin\iverilog.exe')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
source={p.relative_to(R).as_posix():sha(p) for p in [S,OLD]};oracle={Path(__file__).relative_to(R).as_posix():sha(Path(__file__))}
old=OLD.read_text(encoding='utf-8')
for name in sorted(re.findall(r'(?m)^module\s+(\w+)',old),key=len,reverse=True):old=re.sub(r'\b'+name+r'\b',name+'_before_area',old)
(V/'old_reference.v').write_text(old,encoding='utf-8')
tb=r'''`timescale 1ns/1ps
module area_eq_tb;
reg[215:0]p;wire[215:0]nq,oq;wire np,op;integer a,b,c,i,j,t,checks=0;reg[23:0]base,other;
style_cartoon_select_v9 current(.I_neighbours(p),.O_neighbours(nq),.O_protect(np));
style_cartoon_select_v9_before_area previous(.I_neighbours(p),.O_neighbours(oq),.O_protect(op));
task check;begin #1;if({np,nq}!=={op,oq})$fatal(1,"area change not equivalent window=%h new=%b/%h old=%b/%h",p,np,nq,op,oq);checks=checks+1;end endtask
initial begin
// Every 8-bit channel pair, all three channels, near16 output decisions.
for(c=0;c<3;c=c+1)for(a=0;a<256;a=a+1)for(b=0;b<256;b=b+1)begin
base=24'h808080;other=base;base[23-8*c-:8]=a;other[23-8*c-:8]=b;
for(i=0;i<9;i=i+1)p[215-24*i-:24]=other;p[119-:24]=base;check;
end
// Random full-range, low-contrast, and coherent line windows.
for(t=0;t<150000;t=t+1)begin
base=$random;
for(i=0;i<9;i=i+1)begin
if(t%3==0)p[215-24*i-:24]=$random;
else begin other=base;for(c=0;c<3;c=c+1)other[23-8*c-:8]=base[23-8*c-:8]+($random%20);p[215-24*i-:24]=other;end
end
if(t%5==0)begin p[191-:24]=base;p[47-:24]=base;p[119-:24]=base;p[143-:24]=base^24'h202020;p[95-:24]=base^24'h202020;end
check;
end
$display("CARTOON_V9_AREA_EQ_PASS selector_windows=%0d exhaustive_all_channel_pairs random_lowcontrast structured_lines",checks);$finish;
end
endmodule
'''
(V/'area_eq_tb.v').write_text(tb,encoding='utf-8');start=time.time();logs=[]
for args in [[IV,'-g2012','-s','area_eq_tb','-o',V/'eq.vvp',V/'area_eq_tb.v',S,V/'old_reference.v'],[IV.with_name('vvp.exe'),V/'eq.vvp']]:
 p=subprocess.run(list(map(str,args)),cwd=V,capture_output=True,text=True,timeout=240);logs.append(p.stdout+p.stderr);assert p.returncode==0,(p.returncode,logs[-1][-2000:])
(V/'result.log').write_text('\n'.join(logs),encoding='utf-8');assert 'CARTOON_V9_AREA_EQ_PASS' in logs[-1]
assert source=={p:sha(R/p) for p in source};assert oracle=={p:sha(R/p) for p in oracle}
result={'tests':{'selector_equivalence':{'pass':True,'windows':346608,'log':logs[-1].strip()}},'source_sha256':source,'oracle_sha256':oracle,'seconds':round(time.time()-start,2),'scope':'Exact old-V9 vs optimized-selector RTL, exhaustive 3*256*256 channel pairs plus 150000 random/structured RGB windows.'}
(V/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(logs[-1].strip(),flush=True)
