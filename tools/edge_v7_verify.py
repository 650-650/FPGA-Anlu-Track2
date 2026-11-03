"""Independent 5x5 consensus frame oracle and exact streaming RTL checks."""
from pathlib import Path
import hashlib,json,subprocess,time,sys
import numpy as np
from PIL import Image
sys.stdout.reconfigure(encoding='utf-8')
R=Path(__file__).resolve().parents[1];V=R/'validation/edge_v7';V.mkdir(exist_ok=True)
RTL=R/'user_source/hdl_source/isp/edge_detect_96.v';IV=Path(r'D:\anlu\iverilog\bin\iverilog.exe')

def core(g,th):
 h,w=g.shape;z=[[g[y:y+h-4,x:x+w-4].astype(int) for x in range(5)] for y in range(5)]
 gradients=[
 [z[j][3]-z[j][1] for j in [1,2,3]],
 [z[3][j]-z[1][j] for j in [1,2,3]],
 [z[0][2]-z[2][0],z[1][3]-z[3][1],z[2][4]-z[4][2]],
 [z[0][2]-z[2][4],z[1][1]-z[3][3],z[2][0]-z[4][2]]]
 floor=max(4,(th+4)//8-1)
 e=np.any(np.stack([np.all(np.stack(a)>=floor,axis=0)|np.all(np.stack(a)<=-floor,axis=0) for a in gradients]),axis=0)
 expected=np.zeros((h,w),np.uint8);expected[4:,4:]=e*255
 residual=np.abs(4*z[2][2]-z[1][2]-z[2][1]-z[2][3]-z[3][2])[:,0::4]
 n=residual.size;rough=np.count_nonzero(residual>th//2)
 nxt=th+4 if rough>n//4 and th<108 else th+2 if rough>n//8 and th<112 else th-2 if rough<n//32 and th>28 else th
 return expected,nxt

def original(g,th=40):
 h,w=g.shape;z=[g[y:y+h-2,x:x+w-2].astype(int) for y in range(3) for x in range(3)]
 r=np.stack([z[2]-z[0],z[5]-z[3],z[8]-z[6]]);c=np.stack([z[6]-z[0],z[7]-z[1],z[8]-z[2]])
 m=np.abs(r[0]+2*r[1]+r[2])+np.abs(c[0]+2*c[1]+c[2]);high=np.where(z[4]<64,th//2+8,np.where(z[4]<160,th-th//4,th));low=np.maximum(high//2,10)
 coh=(np.all(r>=2,axis=0)|np.all(r<=-2,axis=0)|np.all(c>=2,axis=0)|np.all(c<=-2,axis=0))
 e=(m>=2*high)|(coh&(m>=low));out=np.zeros((h,w),np.uint8);out[2:,2:]=e*255;out[:,:4]=0
 count=(h-2)*(w//4-1);edges=np.count_nonzero(out[2:,4::4]);nxt=th-2 if edges<count//32 and th>28 else th+2 if edges>count//8 and th<80 else th
 return out,nxt

TB='''`timescale 1ns/1ps
module edge_v7_tb;
parameter W=160,H=96,F=48;localparam N=W*H/4;
reg clk=0;always #5 clk=~clk;
reg rst=0,v=0,u=0,l=0;reg [95:0] rgb=0;wire ov,ou,ol;wire [95:0] op;
reg [95:0] image[0:N-1];reg pv=0,pu=0,pl=0;integer f,b,fd,checks=0,seed=12;
reg [1023:0] inf,outf;
edge_detect_96 #(.IMG_WIDTH(W),.IMG_HEIGHT(H),.EDGE_TH(40)) dut(
.I_clk(clk),.I_rst_n(rst),.I_tvalid(v),.I_tuser(u),.I_tlast(l),.I_tdata(rgb),.I_tready(1'b1),
.O_tvalid(ov),.O_tuser(ou),.O_tlast(ol),.O_tdata(op));
task tick;begin @(posedge clk);#1;
if(rst)begin
if({ov,ou,ol}!=={pv,pu,pl})$fatal(1,"two-clock metadata latency changed");
if(ov)begin $fdisplay(fd,"%024h",op);checks=checks+1;end
end pv=v;pu=u;pl=l;@(negedge clk);end endtask
initial begin
if(!$value$plusargs("in=%s",inf))inf="input.hex";
if(!$value$plusargs("out=%s",outf))outf="actual.hex";
$readmemh(inf,image);fd=$fopen(outf,"w");repeat(4)tick;rst=1;
for(f=0;f<F;f=f+1)begin
v=0;u=f%2==0;l=0;tick;u=0;repeat(7)tick;
for(b=0;b<N;b=b+1)begin
v=1;u=f%2==1&&b==0;l=b%(W/4)==W/4-1;rgb=image[b];tick;
if(($random(seed)&31)==0)begin v=0;u=0;l=0;rgb={$random(seed),$random(seed),$random(seed)};tick;end
if(b%(W/4)==W/4-1)begin v=0;u=0;l=0;repeat(4)tick;end
end v=0;u=0;l=0;repeat(12)tick;
end $fclose(fd);if(checks!=F*N)$fatal(1,"beat count");
$display("EDGE_V7_RTL_PASS beats=%0d full_resolution metadata gaps both_SOF",checks);$finish;end
endmodule
'''

def run_case(name,g,frames):
 h,w=g.shape;rgb=np.repeat(g[...,None],3,-1).astype(np.uint8)
 if name=='fullwidth':
  # Independent RGB-to-gray coverage, including four distinct pixels per beat.
  rng=np.random.default_rng(771);rgb=rng.integers(0,256,(h,w,3),dtype=np.uint8)
  g=(rgb[...,0].astype(int)+2*rgb[...,1].astype(int)+rgb[...,2].astype(int))//4
 with (V/(name+'_input.hex')).open('w') as f:
  for beat in rgb.reshape(-1,12):f.write(beat.tobytes().hex()+'\n')
 binary=V/(name+'.vvp');start=time.time()
 commands=[('compile',[IV,'-g2012','-s','edge_v7_tb','-P',f'edge_v7_tb.W={w}','-P',f'edge_v7_tb.H={h}','-P',f'edge_v7_tb.F={frames}','-o',binary,V/'edge_v7_tb.v',RTL]),
 ('run',[IV.with_name('vvp.exe'),binary,f'+in={name}_input.hex',f'+out={name}_actual.hex'])]
 for stage,cmd in commands:
  p=subprocess.run(list(map(str,cmd)),cwd=V,capture_output=True,text=True,timeout=180)
  log=p.stdout+p.stderr;(V/(name+'_'+stage+'.log')).write_text(log,encoding='utf-8');assert p.returncode==0,(name,stage,log[-1200:])
  if stage=='run':assert 'EDGE_V7_RTL_PASS' in log
 actual=np.frombuffer(bytes.fromhex(''.join((V/(name+'_actual.hex')).read_text().split())),np.uint8).reshape(frames,h,w,3)
 th=40;oldth=40;history=[]
 for f in range(frames):
  expected,nxt=core(g,th);old,oldnxt=original(g,oldth)
  assert np.array_equal(actual[f],expected[...,None].repeat(3,axis=-1)),(name,f,th,int(np.any(actual[f]!=expected[...,None],axis=-1).sum()))
  history.append({'frame':f,'threshold':th,'v7_edges':int(np.count_nonzero(expected)),'v6_threshold':oldth,'v6_edges':int(np.count_nonzero(old))});th=nxt;oldth=oldnxt
 Image.fromarray(actual[-1]).save(V/(name+'_verified.png'))
 return {'pass':True,'pixels':frames*w*h,'seconds':round(time.time()-start,2),'history':history}

def main():
 (V/'edge_v7_tb.v').write_text(TB,encoding='utf-8');rng=np.random.default_rng(43);h,w=96,160;tests={}
 for sigma in [2,4,8,12]:
  g=np.clip(48+rng.normal(0,sigma,(h,w)),0,255).astype(np.uint8)
  name=f'gaussian_{sigma}';tests[name]=run_case(name,g,48);v=tests[name]['history'][-1]
  assert v['v7_edges']<v['v6_edges']*.55,(name,v)
  print(name,v,flush=True)
 g=np.full((h,w),48,np.uint8);g[12:88:9,16:155:17]=240
 tests['impulse']=run_case('impulse',g,8);assert tests['impulse']['history'][-1]['v7_edges']==0
 y,x=np.mgrid[:h,:w];g=np.full((h,w),48,int)
 for pos in [16,96]:g[:,pos:pos+1]+=8
 for pos in [20,60]:g[pos:pos+1,:]+=8
 g[(x-y)%80==40]+=16;g[(x+y)%80==30]+=16
 tests['contours']=run_case('contours',np.clip(g,0,255).astype(np.uint8),16)
 e,_=core(g,40)
 assert e[8:88,12:22].sum()>0 and e[8:88,92:102].sum()>0
 # Distinct full-width RGB pixels exercise every 1280-pixel line address.
 tests['fullwidth']=run_case('fullwidth',np.zeros((96,1280),np.uint8),8)
 # Orientation coverage is measured in a common interior region after mapping
 # the different stencil centres back to source coordinates. Fewer top rows
 # are valid for the new 5x5 stencil; do not count that border as lost lines.
 geometry=[];hh,ww=96,1280;yy,xx=np.mgrid[:hh,:ww]
 for contrast in [4,6,8,16,64]:
  for orientation in ['vertical','horizontal','diag+','diag-']:
   gray=np.full((hh,ww),48,int)
   if orientation=='vertical':gray[:,100]+=contrast;gray[:,740]+=contrast
   elif orientation=='horizontal':gray[30,:]+=contrast;gray[60,:]+=contrast
   elif orientation=='diag+':gray[(xx-yy)%320==100]+=contrast
   else:gray[(xx+yy)%320==100]+=contrast
   edge,_=core(gray,40);old,_=original(gray,40)
   aligned=np.zeros_like(edge);aligned[:-2,:-2]=edge[2:,2:]
   if orientation=='vertical':
    occupancy=[np.any(aligned[8:88,c-3:c+4],axis=1) for c in [100,740]]
    assert all(np.all(a) for a in occupancy)
   elif orientation=='horizontal':
    occupancy=[np.any(aligned[c-3:c+4,16:ww-16],axis=0) for c in [30,60]]
    assert all(np.all(a) for a in occupancy)
   else:
    occupancy=[]
    for row in range(8,88):
     columns=np.flatnonzero(((np.arange(ww)-row if orientation=='diag+' else np.arange(ww)+row)%320)==100)
     occupancy.extend(bool(np.any(aligned[row,c-3:c+4])) for c in columns if c>=16 and c<ww-16)
    assert all(occupancy)
   geometry.append({'contrast':contrast,'orientation':orientation,'no_interior_gaps':True,
     'v7_edge_pixels':int(np.count_nonzero(edge)),'v6_edge_pixels':int(np.count_nonzero(old))})
 tests['contour_geometry']={'pass':True,'cases':geometry,'note':'Independent oracle geometry; corresponding composite directional fixture is also RTL exact.'}
 source={'user_source/hdl_source/isp/edge_detect_96.v':hashlib.sha256(RTL.read_bytes()).hexdigest()}
 result={'tests':tests,'source_sha256':source,'latency_clocks':2,'pixels_per_clock':4,'window_rows':5,'new_gray_line_buffers':2,
  'scope':'Synthetic/noisy fixtures and exact RTL, not board accuracy or visual acceptance',
  'spatial_centre':'two rows and two pixels behind; invalid top 4 rows and first 4 columns masked'}
 (V/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('EDGE_V7_ALL_PASS',flush=True)
if __name__=='__main__':main()
