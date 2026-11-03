"""Prove the single green-classifier timing rewrite, then optionally install it.

Reference and candidate are complete actual detector RTL. The only semantic
edit is replacing g-minimum by parallel comparisons under the same green
prefix. Exhaustive RGB and paired multi-frame state tests must both pass.
"""
from pathlib import Path
import argparse,hashlib,json,re,subprocess,time
R=Path(__file__).resolve().parents[1];H=R/'user_source/hdl_source';V=R/'validation/aid_timing'
IV=Path(r'D:\anlu\iverilog\bin\iverilog.exe');VVP=IV.with_name('vvp.exe')
REFERENCE_SHA='624e2d0d6055b86953479cbbeb754962db08c9a86fa890c67db9b0682ea9f1ed'
OLD="{1'b0,g}-{1'b0,minimum}>={4'd0,g[7:3]};"
NEW="({1'b0,g}>={1'b0,r}+{4'd0,g[7:3]} || {1'b0,g}>={1'b0,b}+{4'd0,g[7:3]});"
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,s):p.write_text(s,encoding='utf-8',newline='\n')
def digest(s):return hashlib.sha256(s.encode('utf-8')).hexdigest()
def instance(module,name,clock='clk',reset='rst'):
    return f'''{module} {name}(.clk({clock}),.rst_n({reset}),.frame_start(frame),.de(de),.enable(enable),.x(x),.y(y),.rgb(rgb),
 .hit({name}_hit),.color({name}_color),.target({name}_target),.center_x({name}_cx),.center_y({name}_cy));
'''
COMMON='''wire a_hit,b_hit,a_target,b_target;wire[23:0]a_color,b_color;wire[11:0]a_cx,a_cy,b_cx,b_cy;
'''+instance('aid_reference','a')+instance('aid_candidate','b')
RGB_TB='''`timescale 1ns/1ps
module aid_rgb_tb;
reg clk=0,rst=1,frame=0,de=0,enable=0;reg[11:0]x=0,y=0;reg[23:0]rgb=0;
'''+COMMON+'''
integer i,checked=0;
initial begin
 #1;rst=0;
 for(i=0;i<16777216;i=i+1)begin
  rgb=i;#1;
  if(a.green!==b.green || a.white!==b.white || (b.green!==0 && b.green!==1) || (b.white!==0 && b.white!==1))
   $fatal(1,"RGB classification differs rgb=%h green=%b/%b white=%b/%b",rgb,a.green,b.green,a.white,b.white);
  checked=checked+1;
 end
 $display("AID_RGB_EXHAUSTIVE_PASS rgb_values=%0d green_white_bits=%0d",checked,checked*2);$finish;
end
endmodule
'''

def state_tb():
    fields=[('run_start',12),('run_len',12),('panel_valid',3),('misses',3),('pending',1),('pending_x',12),('pending_y',12),
            ('bx0',12),('bx1',12),('by0',12),('by1',12),('scan_active',1),('scan_done',1),('scan_panel',2),('scan_green',2),
            ('found',1),('best_score',13),('next_x0',12),('next_x1',12),('next_y0',12),('next_y1',12),
            ('sum',13),('vpw',13),('vph',13),('vcx',13),('vcy',13),('same_target',1)]
    for i in range(3):
        for n,w in [('gx0',12),('gx1',12),('gy0',12),('gy1',12),('green_count',12),('px0',12),('px1',12),('py0',12),('py1',12),('panel_score',12),('white_v',6),('white_h',6),('white_c',4)]:
            fields.append((f'{n}[{i}]',w))
    width=sum(w for _,w in fields)
    packs=''
    for label in ['a','b']:
        packs+=f'wire [{width-1}:0] {label}_state={{'+','.join(label+'.'+n for n,_ in fields)+'};\n'
    return '''`timescale 1ns/1ps
module aid_state_tb;
localparam W=1280,H=104;
reg clk=0;always #5 clk=~clk;reg rst=0,frame=0,de=0,enable=1;
reg[11:0]x=0,y=0;reg[23:0]rgb=0;
'''+COMMON+packs+'''
integer f,xx,yy,j,cycles=0,active_pixels=0,seen=0,acquires=0,losses=0,moves=0,runends=0;
reg old_target=0;reg[23:0]old_center=0;reg[31:0]rng=32'h13a1d5e7;
always @(posedge clk)begin
 if(rst && a.run_end)runends=runends+1;
 #1;
 if(a_state!==b_state || a_hit!==b_hit || a_target!==b_target || a_cx!==b_cx || a_cy!==b_cy || a_color!==b_color)
  $fatal(1,"paired detector state/output mismatch frame=%d pixel=%d,%d",f,x,y);
 if(rst)begin
  cycles=cycles+1;if(de)active_pixels=active_pixels+1;
  if(a_target)seen=seen+1;
  if(a_target && !old_target)acquires=acquires+1;
  if(!a_target && old_target)losses=losses+1;
  if(a_target && old_target && {a_cx,a_cy}!=old_center)moves=moves+1;
  old_target=a_target;old_center={a_cx,a_cy};
 end
end
function[23:0]sign_pixel;
 input integer px,py,x0,y0,width,height;
 integer cx,cy;
 begin
  cx=x0+width/2;cy=y0+height/2;sign_pixel=24'h302c38;
  if(px>=x0 && px<x0+width && py>=y0 && py<y0+height)begin
   sign_pixel=24'h20c030;
   if((px>=cx-6 && px<=cx+6 && py>=cy-22 && py<=cy+22) ||
      (py>=cy-6 && py<=cy+6 && px>=cx-22 && px<=cx+22))sign_pixel=24'he8e8e8;
  end
 end
endfunction
function[23:0]sample_pixel;
 input integer frm,px,py;
 reg[23:0]p;
 begin
  p=24'h302c38;
  if(frm>=1 && frm<=7)p=sign_pixel(px,py,32,20,64,64);
  if(frm>=8 && frm<=12)p=sign_pixel(px,py,32+3*(frm-7),20,64,64);
  if(frm>=19 && frm<=23)begin
   p=sign_pixel(px,py,32,20,64,64);
   if(px>=300)p=sign_pixel(px,py,300,24,56,56);
  end
  if(frm>=24 && frm<=26)p=sign_pixel(px,py,W-48,20,48,64);
  if(frm>=29)p=sign_pixel(px,py,40,20,64,64);
  if(frm==28)p={px[7:0],py[7:0],(px[7:0]^py[7:0])};
  sample_pixel=p;
 end
endfunction
initial begin
 repeat(5)@(negedge clk);rst=1;
 for(f=0;f<32;f=f+1)begin
  @(negedge clk);frame=1;de=0;rgb=0;x=0;y=0;
  @(negedge clk);frame=0;repeat(13)@(negedge clk);
  for(yy=0;yy<H;yy=yy+1)begin
   for(xx=0;xx<W;xx=xx+1)begin
    @(negedge clk);de=1;x=xx;y=yy;rgb=sample_pixel(f,xx,yy);
    if(f==27 && yy==40 && xx==200)enable=0;
    if(f==27 && yy==40 && xx==223)enable=1;
    if(f==28 && yy==50 && xx==100)rst=0;
    if(f==28 && yy==50 && xx==108)rst=1;
   end
   @(negedge clk);de=0;rgb=0;repeat(3)@(negedge clk);
  end
  repeat(20)@(negedge clk);
 end
 if(seen==0 || acquires==0 || losses==0 || moves==0 || runends<1000)
  $fatal(1,"insufficient real detector activity seen=%d acquires=%d losses=%d moves=%d runs=%d",seen,acquires,losses,moves,runends);
 $display("AID_PAIRED_STATE_PASS frames=32 cycles=%0d active_pixels=%0d target_cycles=%0d acquire=%0d loss=%0d move=%0d runs=%0d",cycles,active_pixels,seen,acquires,losses,moves,runends);$finish;
end
initial begin #100000000;$fatal(1,"paired detector timeout");end
endmodule
'''

def run(name,top,tb,sources):
    bench=V/(name+'_tb.v');write(bench,tb);binary=V/(name+'.vvp');result={}
    for phase,cmd in [('compile',[IV,'-g2012','-s',top,'-o',binary,bench,*sources]),('run',[VVP,binary])]:
        if phase=='run':print('RUNNING',name,flush=True)
        with (V/(name+'_'+phase+'.log')).open('w',encoding='utf-8') as log:
            p=subprocess.run(list(map(str,cmd)),cwd=R,stdout=log,stderr=subprocess.STDOUT,timeout=240)
        output=(V/(name+'_'+phase+'.log')).read_text(encoding='utf-8')
        assert p.returncode==0,(name,phase,output[-5000:])
        if phase=='run':assert '_PASS' in output;print(output.strip(),flush=True)
        result[phase]={'returncode':p.returncode,'log':(V/(name+'_'+phase+'.log')).relative_to(R).as_posix()}
        if phase=='run':result['output']=output.strip()
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--install',action='store_true');args=ap.parse_args()
    start=time.time();V.mkdir(parents=True,exist_ok=True);production=H/'first_aid_detector.v'
    captured=V/'reference_original.v'
    if not captured.exists():
        assert sha(production)==REFERENCE_SHA,'Unexpected original detector source'
        captured.write_bytes(production.read_bytes())
    assert sha(captured)==REFERENCE_SHA,'Reference snapshot changed'
    original=captured.read_text(encoding='utf-8');assert original.count(OLD)==1
    candidate=original.replace(OLD,NEW,1)
    assert candidate.replace(NEW,OLD,1)==original
    production_before=sha(production);assert production_before in [REFERENCE_SHA,digest(candidate)]
    write(V/'reference_first_aid.v',original.replace('module first_aid_detector','module aid_reference',1))
    write(V/'candidate_first_aid.v',candidate.replace('module first_aid_detector','module aid_candidate',1))
    sources=[V/'reference_first_aid.v',V/'candidate_first_aid.v']
    tests={'rgb_exhaustive':run('rgb_exhaustive','aid_rgb_tb',RGB_TB,sources),
           'paired_detector':run('paired_detector','aid_state_tb',state_tb(),sources)}
    assert sha(production)==production_before,'Detector changed concurrently during proof'
    if args.install:write(production,candidate)
    current=sha(production)
    result={'pass':True,'reference_sha256':REFERENCE_SHA,'candidate_sha256':digest(candidate),'current_sha256':current,
            'production_uses_verified_rewrite':current==digest(candidate),'install_requested':args.install,
            'exhaustive_rgb_count':1<<24,'green_white_bits_compared':2*(1<<24),'paired_frames':32,'paired_frame_width':1280,
            'only_production_edit':'One green-classifier tail expression. Prefix, white expression, threshold, all sequential/state/box logic, ports and cycles unchanged.',
            'old_expression':OLD,'new_expression':NEW,
            'mathematical_proof':['Let P be the unchanged prefix: g>=32 and g>=r+margin and g>=b+margin, where margin>=8.',
                                  'If P is false, both green expressions are false regardless of the tail.',
                                  'If P is true, g is strictly above r and b, so minimum=min(r,b) and subtraction is nonnegative.',
                                  'For q=g[7:3], g-min(r,b)>=q iff g>=min(r,b)+q iff (g>=r+q or g>=b+q).',
                                  'All operands/additions are nine bits; r+q,b+q<=286 and g<=255, so no addition overflow occurs.',
                                  'white uses the unchanged expression with !green; equal green implies equal white for every RGB.',
                                  'All remaining RTL is byte-identical; equal current green/white and prior state imply equal next state and output with no latency change.'],
            'tests':tests,'verifier_sha256':sha(Path(__file__)),'seconds':round(time.time()-start,2),
            'limitations':['Exhaustive classifier is complete for two-state 24-bit RGB, not unknown/metastable inputs.',
                           'Multi-frame fixture uses production default FRAME_WIDTH=1280 and 104 active rows, including true acquisition, motion, loss, two targets, right boundary, disable and reset.',
                           'Timing and resource benefit must be established by final new implementation; functional proof alone does not prove positive slack.']}
    write(V/'result.json',json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('AID_TIMING_EQUIVALENCE_ALL_PASS current_sha256='+current,flush=True)
if __name__=='__main__':main()
