"""Real RTL, independent V9 oracle and exact V10 protected-mode regression."""
from pathlib import Path
import hashlib, importlib.util, json, re, subprocess, sys, time
import numpy as np
from PIL import Image
import cartoon_v11_model as model
import guide_v8_model as gm
R=Path(__file__).resolve().parents[1];V=R/'validation/cartoon_v11';V.mkdir(exist_ok=True)
H=R/'user_source/hdl_source/isp';BASE=R.parent/'07_stylize_flame_fusion_v10_final_visual'
IV=Path(r'D:\anlu\iverilog\bin\iverilog.exe');start=time.time()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
sources={p.relative_to(R).as_posix():sha(p) for p in [H/'stylize_v5_96.v',H/'style_guide_v8.v']}
oracles={p.relative_to(R).as_posix():sha(p) for p in [R/'tools/cartoon_v11_model.py',R/'tools/guide_v8_model.py',Path(__file__)]}
assert sha(H/'style_guide_v8.v')==sha(BASE/'user_source/hdl_source/isp/style_guide_v8.v')
ref=(BASE/'user_source/hdl_source/isp/stylize_v5_96.v').read_text(encoding='utf-8')
for name in sorted(re.findall(r'(?m)^module\s+(\w+)',ref),key=len,reverse=True):ref=re.sub(r'\b'+name+r'\b',name+'_v10_ref',ref)
(V/'style_v10_reference.v').write_text(ref,encoding='utf-8')
tb=r'''`timescale 1ns/1ps
module cartoon_v11_tb;
 parameter W=160,H=90,F=4;
 localparam N=W*H/4;
 reg clk=0;always #5 clk=~clk;reg rst=0,v=0,u=0,l=0;reg[95:0]rgb=0;reg[1:0]mode=0;
 wire ov,ou,ol,pv,pu,pl;wire[95:0]q,pq;reg[95:0]image[0:N*F-1];
 integer f,j,k,selected,lead,fd,beats=0,protected_pixels=0;reg[15:0]vh=0,uh=0,lh=0;
 stylize_v5_96 #(.IMG_WIDTH(W),.IMG_HEIGHT(H),.EXTERNAL_EDGE(0)) dut(.I_clk(clk),.I_rst_n(rst),.I_mode(mode),.I_tvalid(v),.I_tuser(u),.I_tlast(l),.I_tdata(rgb),.I_edge_data(96'd0),.I_tready(1'b1),.O_tvalid(ov),.O_tuser(ou),.O_tlast(ol),.O_tdata(q));
 stylize_v5_96_v10_ref #(.IMG_WIDTH(W),.IMG_HEIGHT(H),.EXTERNAL_EDGE(0)) prior(.I_clk(clk),.I_rst_n(rst),.I_mode(mode),.I_tvalid(v),.I_tuser(u),.I_tlast(l),.I_tdata(rgb),.I_edge_data(96'd0),.I_tready(1'b1),.O_tvalid(pv),.O_tuser(pu),.O_tlast(pl),.O_tdata(pq));
 task tick;begin
  @(posedge clk);#1;vh={vh[14:0],v};uh={uh[14:0],u};lh={lh[14:0],l};
  if(rst)begin
   if({ov,ou,ol}!=={vh[15],uh[15],lh[15]})$fatal(1,"latency not16");
   if({ov,ou,ol}!=={pv,pu,pl})$fatal(1,"V10 synchronisation changed");
   if(ov)begin
    if(dut.mode_o!==prior.mode_o)$fatal(1,"mode latch changed");
    if(dut.mode_o!=1)begin if(q!==pq)$fatal(1,"protected mode pixels changed");protected_pixels=protected_pixels+4;end
    $fdisplay(fd,"%024h",q);beats=beats+1;
   end
  end @(negedge clk);
 end endtask
 initial begin
  if(!$value$plusargs("mode=%d",selected))selected=1;if(!$value$plusargs("lead=%d",lead))lead=52;
  $readmemh("frames.hex",image);fd=$fopen("actual.hex","w");repeat(4)tick;rst=1;
  for(f=0;f<F;f=f+1)begin
   v=0;u=lead!=0;l=0;mode=$random;tick;u=0;repeat(lead)tick;
   for(j=0;j<N;j=j+1)begin
    v=1;u=lead==0&&j==0;l=j%(W/4)==W/4-1;mode=j==0?(selected==4?f%4:selected):$random;rgb=image[f*N+j];tick;
    if((j+f)%19==0)begin v=0;u=0;l=0;mode=$random;tick;end
    if(j%(W/4)==W/4-1)begin v=0;u=0;l=0;repeat(3)tick;end
   end v=0;u=0;l=0;repeat(40)tick;
  end
  $fclose(fd);if(beats!=N*F)$fatal(1,"beat count");
  $display("CARTOON_V11_RTL_PASS pixels=%0d protected_pixels=%0d latency16 random_gaps mode_latch all_modes",beats*4,protected_pixels);$finish;
 end
endmodule
'''
(V/'cartoon_v11_tb.v').write_text(tb,encoding='utf-8')
def run(name,args):
 p=subprocess.run(list(map(str,args)),cwd=V,capture_output=True,text=True,timeout=600)
 log=p.stdout+p.stderr;(V/(name+'.log')).write_text(log,encoding='utf-8');assert p.returncode==0,(name,p.returncode,log[-1800:]);return log
def save(images):
 with (V/'frames.hex').open('w') as f:
  for im in images:
   for beat in im.reshape(-1,12):f.write(beat.tobytes().hex()+'\n')
natural=np.fromfile(R.parent/'05_stylize_on_v5/sim/test_photo.raw',np.uint8).reshape(720,1280,3)
tests={};rng=np.random.default_rng(39)
for name,w,h,F,selected in [('natural',160,90,4,1),('full_width',1280,48,2,1),('colour_noise',160,90,18,1),('moving_colour_detail',160,90,12,1),('protected_modes',320,48,8,4)]:
 clean=np.asarray(Image.fromarray(natural).resize((w,h),Image.Resampling.BILINEAR));images=[]
 for f in range(F):
  im=clean.copy()
  if name=='colour_noise':
   im=np.full((h,w,3),[0,4,8,16,31,32,48,63,64,80,96,127,128,160,192,224,240,255][f],dtype=int)
   im[:,w//4:w//2]=[18,32,70];im[:,w//2:3*w//4]=[86,52,29];im[:,3*w//4:]=[210,160,130]
   im=np.clip(im+rng.integers(-20,21,im.shape),0,255).astype(np.uint8)
  elif name=='moving_colour_detail':
   im=np.full((h,w,3),60,np.uint8);x=40+f
   im[:,x:x+1]=[40,80,40];im[20:22,20+f:100+f]=[20,32,90]
   im[45:,80+f:]=[190,170,145];im=np.clip(im.astype(int)+rng.integers(-3,4,im.shape),0,255).astype(np.uint8)
  elif f%2:im=np.clip(im.astype(float)*0.35,0,255).astype(np.uint8)
  images.append(im)
 save(images)
 run(name+'_compile',[IV,'-g2012','-s','cartoon_v11_tb','-P',f'cartoon_v11_tb.W={w}','-P',f'cartoon_v11_tb.H={h}','-P',f'cartoon_v11_tb.F={F}','-o','style.vvp',V/'cartoon_v11_tb.v',H/'stylize_v5_96.v',V/'style_v10_reference.v',H/'style_guide_v8.v'])
 log=run(name,[IV.with_name('vvp.exe'),'style.vvp',f'+mode={selected}',f'+lead={0 if selected==4 else 52}']);assert 'CARTOON_V11_RTL_PASS' in log
 actual=np.frombuffer(bytes.fromhex(''.join((V/'actual.hex').read_text().split())),np.uint8).reshape(F,h,w,3)
 for f,im in enumerate(images):
  expected,_=model.render(im,f%4 if selected==4 else selected,gm.guide)
  if not np.array_equal(actual[f],expected):
   yy,xx=np.nonzero(np.any(actual[f]!=expected,axis=-1));y,x=int(yy[0]),int(xx[0]);raise AssertionError((name,f,len(yy),(y,x),actual[f,y,x],expected[y,x]))
 tests[name]={'pass':True,'pixels':w*h*F,'width':w,'frames':F,'log':log.strip()}
 Image.fromarray(actual[-1]).save(V/(name+'.png'));print('CARTOON_V11_MODEL_MATCH',name,flush=True)
assert sources=={p:sha(R/p) for p in sources},'source changed during test'
assert oracles=={p:sha(R/p) for p in oracles},'oracle changed during test'
result={'tests':tests,'source_sha256':sources,'oracle_sha256':oracles,'seconds':round(time.time()-start,2),'scope':'real style+guide RTL exact spatial oracle; V10 mode0/2/3 every-pixel equivalence; all modes fixed16 clocks; random valid gaps and frame-mode latching'}
(V/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('CARTOON_V11_VERIFICATION_PASS',result['seconds'],flush=True)
