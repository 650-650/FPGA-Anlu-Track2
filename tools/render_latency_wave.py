"""Render real Icarus VCD events; do not fabricate timing samples."""
from pathlib import Path
import re,json
from PIL import Image,ImageDraw,ImageFont
R=Path(__file__).resolve().parents[1];D=R/'validation/board_status05'
text=(D/'status05.vcd').read_text();header,body=text.split('$enddefinitions $end',1)
names={};scope=[]
for line in header.splitlines():
 p=line.split()
 if not p:continue
 if p[0]=='$scope':scope.append(p[2])
 elif p[0]=='$upscope':scope.pop()
 elif p[0]=='$var':names['.'.join(scope+[p[4]])]=p[3]
events={v:[] for v in names.values()};t=0
for line in body.splitlines():
 if line.startswith('#'):t=int(line[1:])
 elif line.startswith('b'):
  v,k=line[1:].split();events[k].append((t,v))
 elif line and line[0] in '01xz' and not line.startswith('$'):events[line[1:]].append((t,line[0]))
keys=[('raw_user','RAW首组'),('write_en','DDR写入'),('read_start','读帧开始'),('read_en','DDR读出'),('final_hdmi_de','最终显示有效'),('old_valid','旧版延迟有效'),('valid','新版延迟有效'),('previous.O_status','旧版状态'),('dut.O_status','新版状态')]
font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',21);small=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',16)
im=Image.new('RGB',(1500,620),'#14202b');d=ImageDraw.Draw(im)
d.text((25,14),'真实 RTL 仿真波形：RAW计数与时间来源检查分离（非实板读数）',font=font,fill='white')
left=210;right=1460;start=25_000_000;end=49_000_000
sx=lambda t:left+(t-start)/(end-start)*(right-left)
for n in range(25,50,2):
 x=sx(n*1_000_000);d.line((x,72,x,570),fill='#344354');d.text((x-12,575),str(n),font=small,fill='white')
for i,(suffix,label) in enumerate(keys):
 name=next(n for n in names if n.endswith('.'+suffix));ev=events[names[name]];y=85+i*52
 d.text((18,y),label,font=font,fill='#d9e8f5');v='x'
 for time,value in ev:
  if time<=start:v=value
 points=[(start,v)]+[(t,v) for t,v in ev if start<t<end]+[(end,'')]
 for j in range(len(points)-1):
  t,v=points[j];nt=points[j+1][0];x=sx(t);nx=sx(nt)
  if suffix.endswith('status'):
   d.line((x,y+10,nx,y+10),fill='#ffcf60',width=2)
   if nx-x>24:d.text((x+3,y+12),f'{int(v,2):02X}' if set(v)<=set('01') else v,font=small,fill='#ffcf60')
  else:
   yy=y+6 if v=='1' else y+30;d.line((x,yy,nx,yy),fill='#54e5ad',width=2)
   if j+1<len(points)-1:d.line((nx,y+6,nx,y+30),fill='#54e5ad')
d.text((1300,595),'时间 / 微秒',font=small,fill='white');im.save(D/'status05_wave.png')
print('VCD_WAVE_RENDERED',D/'status05_wave.png')
