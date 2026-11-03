from pathlib import Path
import hashlib,json,re,subprocess,sys,time
import numpy as np
from PIL import Image,ImageDraw
import model_baseline as b
import model_visual_v6 as old
import cartoon_v7_model as new
sys.stdout.reconfigure(encoding='utf-8')
R=Path(__file__).resolve().parents[1];V=R/'validation/cartoon_v7';V.mkdir(exist_ok=True);H=R/'user_source/hdl_source/isp/stylize_v5_96.v'
B=R.parent/'07_stylize_flame_fusion_v6_visual_aid';IV=Path(r'D:\anlu\iverilog\bin\iverilog.exe');tests={}
def run(name,cmd,timeout=300):
 p=subprocess.run(list(map(str,cmd)),cwd=V,capture_output=True,text=True,timeout=timeout)
 log=p.stdout+p.stderr;(V/(name+'.log')).write_text(log,encoding='utf-8');assert p.returncode==0,(name,log[-1800:]);return log

def fixture(w,h):
 y,x=np.mgrid[:h,:w];a=np.zeros((h,w,3),np.int16)
 colors=[(11,18,46),(49,28,14),(18,43,24),(34,34,34),(105,107,109),(190,186,182)]
 for i,c in enumerate(colors):a[(x*6//w)==i]=c
 a+=np.random.default_rng(1028).integers(-9,10,a.shape)
 im=Image.fromarray(np.clip(a,0,255).astype(np.uint8));d=ImageDraw.Draw(im)
 d.line((4,h//3,w-4,h//3),fill=(155,155,155),width=2)
 d.line((w//2,4,w//2,h-4),fill=(12,12,12),width=2)
 d.line((4,h-8,w-5,8),fill=(200,195,185),width=2)
 return np.asarray(im)

tb=(R/'validation/tb_stylize_v5_96.v').read_text(encoding='utf-8')
(V/'tb_stylize_v5_96.v').write_text(tb,encoding='utf-8')
start=time.time()
for w,h,frames,lead in [(96,64,64,52),(1280,48,2,0)]:
 b.set_size(w,h);img=fixture(w,h);b.save_hex(img,V/'img_in.hex');A,Y,M=b.core(img)
 run('compile', [IV,'-g2012','-s','tb_stylize_v5_96','-P',f'tb_stylize_v5_96.W={w}','-P',f'tb_stylize_v5_96.H={h}','-o','cartoon.vvp',V/'tb_stylize_v5_96.v',H])
 name=f'model_{w}_{frames}';log=run(name,[IV.with_name('vvp.exe'),'cartoon.vvp','+mode=1',f'+frames={frames}','+gap=1',f'+lead={lead}',f'+out={name}.hex'])
 assert 'TB_PASS' in log and 'ERROR:' not in log
 actual=b.load_hex(V/(name+'.hex'));assert len(actual)==frames;p=dict(b.P0);pold=dict(b.P0)
 for f in range(frames):
  expected=new.render(A,Y,M,1,p,img)
  if not np.array_equal(actual[f],expected):
   yy,xx=np.nonzero(np.any(actual[f]!=expected,axis=-1));z=int(yy[0]),int(xx[0]);raise AssertionError((name,f,len(yy),z,actual[f][z],expected[z],p))
  if f==frames-1:before=old.render(A,Y,M,1,pold,img)
  p=new.update(p,A,Y,M);pold=old.update(pold,A,Y,M)
 Image.fromarray(img).save(V/f'{name}_input.png');Image.fromarray(actual[-1]).save(V/f'{name}_v7.png');Image.fromarray(before).save(V/f'{name}_v6.png')
 tests[name]={'pass':True,'pixels':w*h*frames,'lead':lead,'random_gaps':True}
 print('CARTOON_V7_MODEL_MATCH',name,tests[name],flush=True)

# Per-colour convergence exposes the previous dark colour teaching itself grey.
b.set_size(160,96);metrics={}
for label,color in [('blue',(12,20,48)),('brown',(48,28,15)),('green',(18,43,24)),('neutral',(35,35,35)),('black',(0,0,0))]:
 img=np.full((96,160,3),color,np.uint8);A,Y,M=b.core(img);pn=dict(b.P0);po=dict(b.P0)
 for f in range(100):
  qn=new.render(A,Y,M,1,pn,img);qo=old.render(A,Y,M,1,po,img);pn=new.update(pn,A,Y,M);po=old.update(po,A,Y,M)
 n=np.median(qn[12:-8,24:-16],axis=(0,1)).astype(int);o=np.median(qo[12:-8,24:-16],axis=(0,1)).astype(int)
 metrics[label]={'input':color,'v6_rgb':o.tolist(),'v7_rgb':n.tolist(),'v6_bias':[po['ocr'],po['ocb']],'v7_bias':[pn['ocr'],pn['ocb']]}
 if label=='blue':assert n[2]-n[0]>=8 and n[2]-n[1]>=8
 if label=='brown':assert n[0]-n[2]>=8 and n[0]-n[1]>=4
 if label=='green':assert n[1]-n[0]>=8 and n[1]-n[2]>=5
 if label in ['neutral','black']:assert int(n.max()-n.min())<=1
 if label=='black':assert np.array_equal(n,o),'black pedestal lifted'
tests['dark_colour_convergence']={'pass':True,'metrics':metrics}

# Compile a literal V6 reference under private names, and compare every valid
# pixel/control in clear, sketch and external-edge modes across frame switches.
src=(B/'user_source/hdl_source/isp/stylize_v5_96.v').read_text(encoding='utf-8')
names=re.findall(r'(?m)^module\s+(\w+)',src)
for name in sorted(names,key=len,reverse=True):src=re.sub(r'\b'+name+r'\b',name+'_v6_ref',src)
(V/'style_v6_reference.v').write_text(src,encoding='utf-8')
pair='''`timescale 1ns/1ps
module cartoon_preservation_tb;
 localparam W=1280,H=48,F=6;
 reg clk=0;always #5 clk=~clk;reg rst=0,v=0,u=0,l=0;reg[1:0] mode=0;reg[95:0] rgb=0,edge_rgb=0;
 wire nv,nu,nl,ov,ou,ol;wire[95:0] np,op;integer f,y,x,checks=0;
 stylize_v5_96 #(.IMG_WIDTH(W),.IMG_HEIGHT(H),.EXTERNAL_EDGE(1)) current(.I_clk(clk),.I_rst_n(rst),.I_mode(mode),.I_tvalid(v),.I_tuser(u),.I_tlast(l),.I_tdata(rgb),.I_edge_data(edge_rgb),.I_tready(1'b1),.O_tvalid(nv),.O_tuser(nu),.O_tlast(nl),.O_tdata(np));
 stylize_v5_96_v6_ref #(.IMG_WIDTH(W),.IMG_HEIGHT(H),.EXTERNAL_EDGE(1)) prior(.I_clk(clk),.I_rst_n(rst),.I_mode(mode),.I_tvalid(v),.I_tuser(u),.I_tlast(l),.I_tdata(rgb),.I_edge_data(edge_rgb),.I_tready(1'b1),.O_tvalid(ov),.O_tuser(ou),.O_tlast(ol),.O_tdata(op));
 task tick;begin @(posedge clk);#1;if(rst)begin
  if({nv,nu,nl}!=={ov,ou,ol})$fatal(1,"V6 sync changed");
  if(nv)begin checks=checks+1;if(np!==op)$fatal(1,"clear sketch or external edge changed mode=%d beat=%d",mode,checks);end
 end @(negedge clk);end endtask
 initial begin
  repeat(4)tick;rst=1;
  for(f=0;f<F;f=f+1)begin
   mode=f%3==0?0:f%3==1?2:3;v=0;u=f%2==0;l=0;tick;u=0;repeat(52)tick;
   for(y=0;y<H;y=y+1)begin for(x=0;x<W/4;x=x+1)begin
    v=1;u=f%2==1&&y==0&&x==0;l=x==W/4-1;rgb={$random,$random,$random};edge_rgb={$random,$random,$random};tick;
    if((x+y+f)%29==0)begin v=0;u=0;l=0;tick;end
   end v=0;u=0;l=0;repeat(3)tick;end repeat(24)tick;
  end
  if(checks!=W*H*F/4)$fatal(1,"coverage");
  $display("CARTOON_V7_PRESERVATION_PASS pixels=%d full_width clear_sketch_external_edge exact_pixels_and_sync",checks*4);$finish;
 end
endmodule
'''
(V/'cartoon_preservation_tb.v').write_text(pair,encoding='utf-8')
run('preservation_compile',[IV,'-g2012','-s','cartoon_preservation_tb','-o','preserve.vvp',V/'cartoon_preservation_tb.v',H,V/'style_v6_reference.v'])
log=run('preservation',[IV.with_name('vvp.exe'),'preserve.vvp']);assert 'CARTOON_V7_PRESERVATION_PASS' in log
tests['clear_sketch_external_edge_preservation']={'pass':True,'pixels':368640,'full_width':1280}
result={'tests':tests,'source_sha256':hashlib.sha256(H.read_bytes()).hexdigest(),'seconds':round(time.time()-start,2)}
(V/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print('CARTOON_V7_VERIFICATION_PASS',json.dumps(result,ensure_ascii=False),flush=True)
