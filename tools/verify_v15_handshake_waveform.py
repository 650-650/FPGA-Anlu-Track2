"""Save a real RTL VCD of the first lost-AR counterexample, not a drawn model."""
from pathlib import Path
import json,re,hashlib,subprocess
R=Path(__file__).resolve().parents[1];V=R/'validation/handshake_waveform';V.mkdir(parents=True,exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
report=json.loads((R/'validation/ddr_handshake/result.json').read_text(encoding='utf-8'))
files=[R/p for p in report['source_sha256'] if not p.endswith('ddr_handshake_tb.sv')]
t=(R/'tools/ddr_handshake_tb.sv').read_text(encoding='utf-8')
mark=' initial begin\n  reset_case(0,1);'
assert t.count(mark)==1
t=t.replace(mark,' initial begin\n  $dumpfile("'+(V/'lost_read.vcd').as_posix()+'");$dumpvars(1,handshake_tb);\n  reset_case(0,1);')
mark='observed_idle_clocks=4096",old_outstanding,new_outstanding);tested=tested+1;'
assert t.count(mark)==1
t=t.replace(mark,mark+'\n  $display("LOST_AR_WAVEFORM_PASS");$finish;')
tb=V/'tb.sv';tb.write_text(t,encoding='utf-8');files.append(tb)
sources={str(p):sha(p) for p in files}
iv=Path(r'D:\anlu\iverilog\bin\iverilog.exe')
c=subprocess.run([str(iv),'-g2012','-s','handshake_tb','-o',str(V/'sim.vvp'),*map(str,files)],capture_output=True,text=True)
(V/'compile.log').write_text(c.stdout+c.stderr,encoding='utf-8');assert c.returncode==0,c.stderr
c=subprocess.run([str(iv.with_name('vvp.exe')),str(V/'sim.vvp')],capture_output=True,text=True)
(V/'run.log').write_text(c.stdout+c.stderr,encoding='utf-8');assert c.returncode==0 and 'LOST_AR_WAVEFORM_PASS' in c.stdout
# Extract selected signals directly from the VCD into a small inspectable table.
signals=['clk','rst','ctl_aw','ctl_ar','ocv','ncv','opop','npop','orh','nrh','orv','nrv','old_outstanding','new_outstanding']
codes={};events=[];values={};stamp=0;defs=True
for line in (V/'lost_read.vcd').read_text().splitlines():
 if line.startswith('$var'):
  a=line.split();name=a[4]
  if name in signals:codes[a[3]]=name
 elif line.startswith('$enddefinitions'):defs=False
 elif not defs:
  if line.startswith('#'):stamp=int(line[1:])
  elif line.startswith('b'):
   v,code=line[1:].split()
   if code in codes:
    name=codes[code];values[name]=v;events.append((stamp,name,v))
  elif line and line[0] in '01xz' and line[1:] in codes:
   name=codes[line[1:]];v=line[0];values[name]=v;events.append((stamp,name,v))
assert set(codes.values())==set(signals)
assert values['old_outstanding']=='1' and int(values['new_outstanding'],2)==0
(V/'events.json').write_text(json.dumps({'time_unit':'ps','events':events},indent=2),encoding='utf-8')
# SVG is an evidence view of recorded values. The VCD remains the source.
rows=['ctl_aw','ctl_ar','ocv','opop','orh','ncv','npop','nrh','old_outstanding','new_outstanding']
start,end=210000,900000;left,width,top,step=190,1000,60,46
def x(time):return left+(time-start)/(end-start)*width
parts=['<svg xmlns="http://www.w3.org/2000/svg" width="1230" height="570" viewBox="0 0 1230 570">',
 '<rect width="1230" height="570" fill="white"/>',
 '<text x="20" y="27" font-family="sans-serif" font-size="18">Recorded RTL: old path drops unaccepted AR; corrected path holds until ARREADY</text>']
for ns in range(250,901,50):
 xx=x(ns*1000);parts.append(f'<path d="M{xx:.1f},40 V525" stroke="#ddd"/><text x="{xx:.1f}" y="548" font-size="11">{ns}ns</text>')
for ri,name in enumerate(rows):
 y=top+ri*step;parts.append(f'<text x="12" y="{y+8}" font-family="monospace" font-size="15">{name}</text>')
 ev=[(tm,v) for tm,nm,v in events if nm==name];before=[v for tm,v in ev if tm<=start];v=before[-1] if before else 'x';points=[(start,v)]+[(tm,vv) for tm,vv in ev if start<tm<end]+[(end,v)]
 path=[];last_y=None
 for tm,vv in points[:-1]:
  yy=y+(0 if vv=='1' else 18 if vv=='0' else 9)
  if not path:path.append(f'M{x(tm):.2f},{yy}')
  else:path.append(f'H{x(tm):.2f} V{yy}')
  last_y=yy
 path.append(f'H{x(end):.2f}');color='#b42318' if name in ('ocv','opop','old_outstanding') else '#087443'
 parts.append(f'<path d="{" ".join(path)}" fill="none" stroke="{color}" stroke-width="2"/>')
parts.append('</svg>');(V/'lost_read.svg').write_text('\n'.join(parts),encoding='utf-8')
assert sources=={str(p):sha(p) for p in files}
r={'pass':True,'source_sha256':sources,'vcd_sha256':sha(V/'lost_read.vcd'),'events_sha256':sha(V/'events.json'),
 'svg_sha256':sha(V/'lost_read.svg'),'verifier_sha256':sha(Path(__file__)),'counterexample':'AWREADY=1 ARREADY=0; old FIFO pops unread AR. Old outstanding remains 1 after 4096 idle clocks; corrected=0.'}
(V/'result.json').write_text(json.dumps(r,indent=2),encoding='utf-8');print('LOST_AR_VCD_PASS',V/'lost_read.vcd')
