"""Run only after both production style and guide have been frozen."""
from pathlib import Path
import hashlib,importlib.util,json,subprocess,sys,time
import numpy as np
from PIL import Image
sys.stdout.reconfigure(encoding='utf-8')
R=Path(__file__).resolve().parents[1];V=R/'validation/cartoon_v8';V.mkdir(exist_ok=True)
H=R/'user_source/hdl_source/isp';IV=Path(r'D:\anlu\iverilog\bin\iverilog.exe')
import model_baseline as b
import cartoon_v8_model as model
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
guide_path=R/'tools/style_guide_v8_model.py'
if not guide_path.exists():guide_path=R/'tools/guide_v8_model.py'
assert guide_path.exists(),'guide agent must supply a frozen independent Python guide oracle'
spec=importlib.util.spec_from_file_location('frozen_guide',guide_path);guide_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(guide_module)
guide=guide_module.guide
sources={p.relative_to(R).as_posix():sha(p) for p in [H/'stylize_v5_96.v',H/'style_guide_v8.v',guide_path]}
tb=r'''`timescale 1ns/1ps
module cartoon_v8_tb;
 parameter W=160,H=90,F=4;
 localparam N=W*H/4;
 reg clk=0;always #5 clk=~clk;
 reg rst=0,v=0,u=0,l=0;reg[95:0]rgb=0;reg[1:0]mode=0;
 wire ov,ou,ol;wire[95:0]q;reg[95:0]image[0:N*F-1];
 integer f,j,k,selected,lead,fd,beats=0;
 reg[15:0]vh=0,uh=0,lh=0;
 stylize_v5_96 #(.IMG_WIDTH(W),.IMG_HEIGHT(H),.EXTERNAL_EDGE(0)) dut(.I_clk(clk),.I_rst_n(rst),.I_mode(mode),.I_tvalid(v),.I_tuser(u),.I_tlast(l),.I_tdata(rgb),.I_edge_data(96'd0),.I_tready(1'b1),.O_tvalid(ov),.O_tuser(ou),.O_tlast(ol),.O_tdata(q));
 task tick;begin
  @(posedge clk);#1;vh={vh[14:0],v};uh={uh[14:0],u};lh={lh[14:0],l};
  if(rst)begin
   if({ov,ou,ol}!=={vh[15],uh[15],lh[15]})$fatal(1,"style no longer has exactly 16 clocks");
   if(ov)begin $fdisplay(fd,"%024h",q);beats=beats+1;end
  end @(negedge clk);
 end endtask
 initial begin
  if(!$value$plusargs("mode=%d",selected))selected=1;
  if(!$value$plusargs("lead=%d",lead))lead=52;
  $readmemh("frames.hex",image);fd=$fopen("actual.hex","w");repeat(4)tick;rst=1;
  for(f=0;f<F;f=f+1)begin
   v=0;u=lead!=0;l=0;mode=$random;tick;u=0;repeat(lead)tick;
   for(j=0;j<N;j=j+1)begin
    v=1;u=lead==0&&j==0;l=j%(W/4)==W/4-1;mode=j==0?selected:$random;rgb=image[f*N+j];tick;
    if((j+f)%19==0)begin v=0;u=0;l=0;mode=$random;tick;end
    if(j%(W/4)==W/4-1)begin v=0;u=0;l=0;repeat(3)tick;end
   end v=0;u=0;l=0;repeat(40)tick;
  end
  $fclose(fd);if(beats!=N*F)$fatal(1,"output beat count");
  $display("CARTOON_V8_MODEL_TB_PASS pixels=%0d mode=%0d random_gaps SOF_lead=%0d latency=16",beats*4,selected,lead);$finish;
 end
endmodule
'''
(V/'cartoon_v8_tb.v').write_text(tb,encoding='utf-8')
def run(name,args):
 p=subprocess.run(list(map(str,args)),cwd=V,capture_output=True,text=True,timeout=300)
 log=p.stdout+p.stderr;(V/(name+'.log')).write_text(log,encoding='utf-8');assert p.returncode==0,(name,log[-1800:]);return log
def save_frames(images):
 with (V/'frames.hex').open('w') as f:
  for image in images:
   for group in image.reshape(-1,12):f.write(group.tobytes().hex()+'\n')
start=time.time();tests={}
raw=R.parent/'05_stylize_on_v5/sim/test_photo.raw'
natural=np.fromfile(raw,np.uint8).reshape(720,1280,3)
cases=[]
for label,w,h,F in [('natural',160,90,4),('full_width',1280,48,2),('colour_noise',160,90,18)]:
 clean=np.asarray(Image.fromarray(natural).resize((w,h),Image.Resampling.BILINEAR));rng=np.random.default_rng(29)
 images=[clean,np.clip(clean.astype(float)*0.35,0,255).astype(np.uint8)]
 if F>2:images+=[np.clip(images[1].astype(int)+rng.integers(-20,21,images[1].shape),0,255).astype(np.uint8),clean]
 if label=='colour_noise':
  images=[]
  for level in [40,42,44,82,84,86,124,126,128,166,168,170,208,210,212,4,8,16]:
   img=np.full((h,w,3),level,dtype=int)
   img[:,w//4:w//2]=[18,32,70];img[:,w//2:3*w//4]=[210,160,130];img[:,3*w//4:]=[244,200,172]
   images.append(np.clip(img+rng.integers(-24,25,img.shape),0,255).astype(np.uint8))
 save_frames(images)
 run(label+'_compile',[IV,'-g2012','-s','cartoon_v8_tb','-P',f'cartoon_v8_tb.W={w}','-P',f'cartoon_v8_tb.H={h}','-P',f'cartoon_v8_tb.F={F}','-o','style.vvp',V/'cartoon_v8_tb.v',H/'stylize_v5_96.v',H/'style_guide_v8.v'])
 for mode in ([1] if label=='colour_noise' else [1,2,3]):
  name=f'{label}_mode{mode}';log=run(name,[IV.with_name('vvp.exe'),'style.vvp',f'+mode={mode}',f'+lead={52 if mode%2 else 0}']);assert 'CARTOON_V8_MODEL_TB_PASS' in log
  actual=np.frombuffer(bytes.fromhex(''.join((V/'actual.hex').read_text().split())),np.uint8).reshape(F,h,w,3)
  for f,img in enumerate(images):
   expected,features=model.render(img,mode,guide)
   if not np.array_equal(actual[f],expected):
    yy,xx=np.nonzero(np.any(actual[f]!=expected,axis=-1));y,x=int(yy[0]),int(xx[0]);raise AssertionError((name,f,len(yy),(y,x),actual[f,y,x],expected[y,x]))
  tests[name]={'pass':True,'pixels':w*h*F,'frames':F,'width':w};Image.fromarray(actual[-1]).save(V/(name+'.png'));print('CARTOON_V8_MODEL_MATCH',name,tests[name],flush=True)
assert sources=={f:sha(R/f) for f in sources},'tested source changed during verification'
result={'tests':tests,'source_sha256':sources,'seconds':round(time.time()-start,2),'scope':'RTL spatial/model comparison, temporal input variation, full width, random valid gaps, exactly16 clocks, first-valid mode latching'}
(V/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('CARTOON_V8_VERIFICATION_PASS',result['seconds'],flush=True)
