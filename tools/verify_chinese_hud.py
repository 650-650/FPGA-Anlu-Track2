"""Compile and execute the production V16 Chinese HUD and render its pixels.

This is RTL simulation, not a synthesized timing proof or board capture. The
reference uses the Chinese text specification and individual font bitmaps;
it does not decode the production menu ROM to predict menu content.
"""
from pathlib import Path
import hashlib,json,re,subprocess,time
from PIL import Image,ImageDraw,ImageFont

R=Path(__file__).resolve().parents[1]
H=R/'user_source/hdl_source'
A=R/'tools/chinese_assets'
V=R/'validation/chinese_hud'
IV=Path(r'D:\anlu\iverilog\bin\iverilog.exe')
VVP=IV.with_name('vvp.exe')
FILES=[H/'fusion_hud.v',H/'fusion_menu_rom.v',H/'fusion_chinese_font_rom.v']
Y0,Y1,W=540,720,1280
TOKEN=re.compile(r'\{(\d+)\}')

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,s):p.write_text(s,encoding='utf-8',newline='\n')
def cells(s):
    out=[];last=0
    for m in TOKEN.finditer(s):
        out+=list(s[last:m.start()]);out.append(int(m[1]));last=m.end()
    return out+list(s[last:])

def panel(control):
    group=control>>5;sub=(control>>3)&3
    return 0 if group==0 else group*4+sub if group<=4 else 28

def make_cases():
    common=dict(control=0,style_levels=0x492,color=0,target=1,alarm=1,audio=1,cam_cfg=1,
                ddr_ready=1,source_ok=1,wb_locked=1,armed=1,debug=10,
                h_zone=1,v_zone=1,x_bcd='1234',y_bcd='5678',pixels_bcd='123456',
                seconds_bcd='12345',exposure_bcd='54321',camera_fps_bcd='24',
                output_fps_bcd='60',gain_bcd='123',latency_bcd='03579',
                frame_id='6c02',latency_valid=1,latency_repeat=1,latency_skip=1,
                latency_status='a5')
    cases=[]
    def add(name,**kw):cases.append(dict(common,name=name,**kw))
    for p in [0,*range(4,20),28]:
        add(f'page_{p:02}',control=0 if p==0 else (p//4)*32+(p%4)*8 if p<20 else 0xe0)
    for name,color in [('cool',(-3&15)<<2),('warm',3<<2),('magenta',1),('green',2),
                       ('reserved_tint',3),('temperature_min',8<<2),('temperature_max',7<<2)]:
        add('base_'+name,color=color)
    for v in range(3):
        for h in range(3):add(f'aid_v{v}_h{h}',control=0x58,h_zone=h,v_zone=v)
    add('aid_reserved_zones',control=0x58,h_zone=3,v_zone=3)
    add('aid_no_target',control=0x58,target=0)
    add('latency_invalid',control=0x68,latency_valid=0,latency_status='03')
    add('latency_hex_cafe',control=0x68,frame_id='cafe',latency_status='df')
    add('latency_hex_dead',control=0x68,frame_id='dead',latency_status='bc')
    add('latency_zero',control=0x68,latency_bcd='00000',frame_id='0000',
        latency_repeat=0,latency_skip=0,latency_status='00')
    for control in [0,0x40,0x48,0x50,0x58,0x60,0x68,0x70,0x78]:
        add(f'flags_off_{control:02x}',control=control,target=0,alarm=0,audio=0,
            cam_cfg=0,ddr_ready=0,source_ok=0,wb_locked=0,armed=0,debug=0,
            latency_valid=0,latency_repeat=0,latency_skip=0,latency_status='80')
    add('invalid_group_5',control=0xa0)
    add('invalid_group_6',control=0xc0)
    # Each selected mode has all five values. Other modes intentionally hold
    # different levels, exposing a wrong nibble/order instead of masking it.
    for mode in range(4):
        for level in range(5):
            levels=[(level+i+1)%5 for i in range(4)]
            levels[mode]=level
            packed=sum(value<<(i*3) for i,value in enumerate(levels))
            add(f'style_{mode}_level_{level+1}',control=0x20+mode*8,style_levels=packed)
    return common,cases

TB_HEAD=r'''`timescale 1ns/1ps
module chinese_hud_tb;
reg clk=0;always #5 clk=~clk;
reg rst=0;
reg [11:0] x=0,y=0;
// Exercise an actual transition from reset/invalid controls to the first page.
reg [7:0] control=8'hff;
reg [11:0] style_levels=12'h492;
reg [15:0] x_bcd=0,y_bcd=0;
reg [23:0] pixels_bcd=0;
reg [19:0] seconds_bcd=0,exposure_bcd=0,latency_bcd=0;
reg [7:0] camera_fps_bcd=0,output_fps_bcd=0,latency_status=0;
reg [11:0] gain_bcd=0;
reg [15:0] frame_id=0;
reg target=0,alarm=0,audio=0,cam_cfg=0,ddr_ready=0,source_ok=0,wb_locked=0,armed=0;
reg latency_valid=0,latency_repeat=0,latency_skip=0;
reg [3:0] debug=0;
reg [1:0] h_zone=0,v_zone=0;
reg [5:0] color=0;
wire hit;wire [23:0] rgb;
fusion_hud dut(.I_clk(clk),.I_rst_n(rst),.I_x(x),.I_y(y),.I_control(control),
 .I_style_levels(style_levels),
 .I_x_bcd(x_bcd),.I_y_bcd(y_bcd),.I_pixels_bcd(pixels_bcd),
 .I_seconds_bcd(seconds_bcd),.I_exposure_bcd(exposure_bcd),
 .I_camera_fps_bcd(camera_fps_bcd),.I_output_fps_bcd(output_fps_bcd),.I_gain_bcd(gain_bcd),
 .I_latency_bcd(latency_bcd),.I_latency_frame_id(frame_id),.I_latency_status(latency_status),
 .I_latency_valid(latency_valid),.I_latency_repeat(latency_repeat),.I_latency_skip(latency_skip),
 .I_target(target),.I_alarm(alarm),.I_audio(audio),.I_cam_cfg(cam_cfg),.I_ddr_ready(ddr_ready),
 .I_source_ok(source_ok),.I_wb_locked(wb_locked),.I_armed(armed),.I_debug(debug),
 .I_aid_h_zone(h_zone),.I_aid_v_zone(v_zone),.I_color_control(color),.O_hit(hit),.O_color(rgb));
task render_page;
 input string filename;
 integer fd,xx,yy,previous_x,previous_y,have_previous;
 reg [1279:0] scanline;
 begin
  fd=$fopen(filename,"w");if(fd==0)$fatal(1,"cannot open page output");
  repeat(3)@(negedge clk);have_previous=0;scanline=0;
  for(yy=540;yy<720;yy=yy+1)begin
   for(xx=0;xx<1280;xx=xx+1)begin
    @(negedge clk);x=xx;y=yy;
    @(posedge clk);#1;
    if(have_previous)begin
     if(hit!==1'b0 && hit!==1'b1)$fatal(1,"unknown HUD hit previous=%d,%d input=%d,%d control=%h panel=%h address=%h mem0=%h code=%h glyph=%h font=%h row=%h col=%h",previous_x,previous_y,x,y,control,dut.panel,dut.u_menu.I_address,dut.u_menu.rom[0],dut.code,dut.glyph,dut.bits,dut.font_row1,dut.col2);
     if(rgb!==24'hfff200)$fatal(1,"unexpected HUD color");
     scanline[1279-previous_x]=hit;
     if(previous_x==1279)$fdisplay(fd,"%h",scanline);
    end
    previous_x=xx;previous_y=yy;have_previous=1;
   end
  end
  @(negedge clk);x=0;y=0;@(posedge clk);#1;
  if(hit!==1'b0 && hit!==1'b1)$fatal(1,"unknown flushed HUD hit");
  scanline[0]=hit;$fdisplay(fd,"%h",scanline);
  $fclose(fd);
 end
endtask
task probe_controls;
 input string filename;
 integer fd,i,px,py,pc,pl,have_previous;
 begin
  fd=$fopen(filename,"w");have_previous=0;
  repeat(3)@(negedge clk);
  for(i=0;i<4096;i=i+1)begin
   @(negedge clk);
   case(i%8)0:control=8'h00;1:control=8'h20;2:control=8'h28;3:control=8'h58;
     4:control=8'h68;5:control=8'h70;6:control=8'ha0;default:control=8'h78;endcase
   x=(i*37)%1280;y=540+(i*53)%180;
   // Half of the samples concentrate on the level glyph while both the
   // panel and packed remembered levels change on consecutive clocks.
   if(i%2==0)begin
    control=8'h20+((i/2)%4)*8;
    x=16+12*32+((i/8)%32);y=552+((i/256)%32);
   end
   style_levels=((i%5)<<9)|(((i+1)%5)<<6)|(((i+2)%5)<<3)|((i+3)%5);
   @(posedge clk);#1;
   if(have_previous)$fdisplay(fd,"%d %d %d %d %b",px,py,pc,pl,hit);
   px=x;py=y;pc=control;pl=style_levels;have_previous=1;
  end
  @(negedge clk);x=0;y=0;@(posedge clk);#1;
  $fdisplay(fd,"%d %d %d %d %b",px,py,pc,pl,hit);$fclose(fd);
 end
endtask
initial begin
 repeat(4)@(negedge clk);
 if(hit!==0)$fatal(1,"HUD not blank in reset");rst=1;
'''

def assignments(case):
    widths=dict(control=8,style_levels=12,color=6,target=1,alarm=1,audio=1,cam_cfg=1,ddr_ready=1,
                source_ok=1,wb_locked=1,armed=1,debug=4,h_zone=2,v_zone=2,
                x_bcd=16,y_bcd=16,pixels_bcd=24,seconds_bcd=20,exposure_bcd=20,
                camera_fps_bcd=8,output_fps_bcd=8,gain_bcd=12,latency_bcd=20,
                frame_id=16,latency_valid=1,latency_repeat=1,latency_skip=1,latency_status=8)
    return ' '.join(f"{k}={w}'h{int(case[k],16) if isinstance(case[k],str) else case[k]:x};"
                    for k,w in widths.items())+'\n'

def build_reference(spec,ids,patterns,case):
    p=panel(case['control'])
    def dynamic(n):
        fields=[('x_bcd',0,4),('y_bcd',4,8),('pixels_bcd',8,14),('seconds_bcd',14,19),
                ('camera_fps_bcd',19,21),('output_fps_bcd',21,23),('exposure_bcd',23,28),('gain_bcd',28,31)]
        for name,low,high in fields:
            if low<=n<high:return case[name][n-low].upper()
        if n>=59:return case['latency_bcd'][n-59] if case['latency_valid'] else '-'
        if p in (4,5,6,7) and n==52:
            return str(((case['style_levels']>>((p-4)*3))&7)+1)
        if p in (13,14):
            if n==43:return str(case['latency_valid'])
            if 44<=n<=47:return case['frame_id'][n-44].upper()
            if n==48:return str(case['latency_repeat'])
            if n==49:return str(case['latency_skip'])
            if n in [50,51]:return case['latency_status'][n-50].upper()
        if p==0:
            temp=case['color']>>2
            if temp&8:temp-=16
            tint=case['color']&3
            if n==55:return '中' if temp==0 else '冷' if temp<0 else '暖'
            if n==56:return str(abs(temp))
            if n==57:return '品' if tint==1 else '绿' if tint==2 else '中'
            if n==54:return '红' if tint==1 else '色' if tint==2 else '性'
            if n==58:return '无' if case['color']==0 else '有'
        flags={31:'target',32:'alarm',33:'audio',38:'cam_cfg',39:'ddr_ready',40:'source_ok',41:'wb_locked',42:'armed'}
        if n in flags:return str(case[flags[n]])
        if 34<=n<=37:return str((case['debug']>>(n-34))&1)
        if not case['target']:return ' '
        if n in [43,44]:return ['上部','中部','下部','下部'][case['v_zone']][n-43]
        if n in [49,50]:return ['左侧','中央','右侧','右侧'][case['h_zone']][n-49]
        return ' '
    output=[0]*(Y1-Y0)
    def double_bits(word):
        v=0
        for i in range(15,-1,-1):v=(v<<2)|(3 if (word>>i)&1 else 0)
        return v
    for row,text in enumerate(spec['panels'][str(p)]):
        for col,c in enumerate(cells(text)):
            if isinstance(c,int):c=dynamic(c)
            glyph=ids[c]
            for fy in range(16):
                v=double_bits(patterns[glyph*16+fy])<<(W-(16+col*32+32))
                offset=552+row*36+fy*2-Y0
                output[offset]|=v;output[offset+1]|=v
    return output

def main():
    start=time.time();V.mkdir(parents=True,exist_ok=True)
    checked_sources=[*FILES,Path(__file__),A/'menu_zh.json',A/'build_chinese_assets.py']
    source_start={str(p.relative_to(R)):sha(p) for p in checked_sources}
    spec=json.loads((A/'menu_zh.json').read_text(encoding='utf-8'))
    manifest=json.loads((A/'generated/manifest.json').read_text(encoding='utf-8'))
    ids=manifest['char_to_id']
    patterns=[int(s,16) for s in (A/'generated/font16.mem').read_text().splitlines()]
    assert len(patterns)==4096 and len(ids)<=256
    common,cases=make_cases();write(V/'cases.json',json.dumps(cases,ensure_ascii=False,indent=2)+'\n')
    tb=TB_HEAD
    for case in cases:
        tb+='@(negedge clk);'+assignments(case)
        tb+=f'render_page("{(V/(case["name"]+".hex")).as_posix()}");\n'
        tb+=f'$display("HUD_PAGE_DONE {case["name"]}");\n'
    tb+='@(negedge clk);'+assignments(common)
    tb+=f'probe_controls("{(V/"control_probes.txt").as_posix()}");\n'
    tb+='$display("CHINESE_HUD_RTL_PASS");$finish;\nend\nendmodule\n'
    bench=V/'chinese_hud_tb.v';binary=V/'chinese_hud_tb.vvp';write(bench,tb)
    command=[str(IV),'-g2012','-Wall','-s','chinese_hud_tb','-o',str(binary),str(bench),*[str(p) for p in FILES]]
    compile_result=subprocess.run(command,cwd=R,text=True,capture_output=True,check=True)
    write(V/'compile.log',compile_result.stdout+compile_result.stderr)
    with (V/'simulation.log').open('w',encoding='utf-8') as log:
        sim=subprocess.run([str(VVP),str(binary)],cwd=R,text=True,stdout=log,stderr=subprocess.STDOUT,check=True)
    assert 'CHINESE_HUD_RTL_PASS' in (V/'simulation.log').read_text()
    font=ImageFont.truetype(r'C:\Windows\Fonts\simsun.ttc',24)
    mismatch=[];total=0;images={};reference_cache={}
    for case in cases:
        actual=[int(line,16) for line in (V/(case['name']+'.hex')).read_text().splitlines()]
        expected=build_reference(spec,ids,patterns,case)
        assert len(actual)==len(expected)==180,(case['name'],len(actual))
        for row,(a,e) in enumerate(zip(actual,expected)):
            diff=a^e
            if diff:mismatch.append(dict(case=case['name'],y=Y0+row,wrong_pixels=diff.bit_count()))
        assert not mismatch,mismatch[:10]
        total+=W*len(actual)
        image=Image.new('RGB',(W,230),(22,26,30));draw=ImageDraw.Draw(image)
        draw.text((16,5),case['name']+'  中文界面 RTL 仿真预览，非实板照片',font=font,fill=(235,235,235))
        for yy,word in enumerate(actual):
            for x in range(W):
                if (word>>(W-1-x))&1:image.putpixel((x,yy+45),(255,242,0))
        image.save(V/(case['name']+'.png'));images[case['name']]=image
    probe_count=0
    for line in (V/'control_probes.txt').read_text().splitlines():
        x,y,c,levels,hit=map(int,line.split());probe_count+=1
        key=(c,levels)
        if key not in reference_cache:
            reference_cache[key]=build_reference(spec,ids,patterns,dict(common,control=c,style_levels=levels))
        expect=(reference_cache[key][y-Y0]>>(W-1-x))&1
        assert hit==expect,('control/level/coordinate pipeline mismatch',x,y,c,levels,hit,expect)
    assert probe_count==4096
    for name,selection in [('main_contact',['page_00','page_05','page_06','page_07','page_11','page_13']),
                           ('status_contact',['base_cool','base_warm','base_magenta','base_green','latency_invalid','page_14']),
                           ('direction_contact',['aid_v0_h0','aid_v0_h2','aid_v1_h1','aid_v2_h0','aid_v2_h2','aid_no_target']),
                           *[(f'style_{mode}_five_levels',[f'style_{mode}_level_{level}' for level in range(1,6)])
                             for mode in range(4)]]:
        sheet=Image.new('RGB',(W,230*len(selection)),(22,26,30))
        for i,key in enumerate(selection):sheet.paste(images[key],(0,230*i))
        sheet.save(V/(name+'.png'))
    result=dict(status='PASS',evidence='production RTL simulation and pixel comparison; not a board capture',
                page_cases=len(cases),compared_pixels=total,control_switch_probes=probe_count,
                pipeline='menu + font, two synchronous rising-edge reads; output matches the prior sampled coordinate',
                cjk_glyphs=manifest['cjk_count'],max_static_id=manifest['max_static_glyph_id'],
                menu_bits=4096*9,font_bits=4096*16,eram_target_estimate=6,
                elapsed_seconds=round(time.time()-start,2),
                sources=source_start,
                style_level_cases=20,style_levels_packing='{edge,sketch,cartoon,clear}, internal 0..4 displayed 1..5',
                checks=['all active pages and reserved/invalid pages','all green-white-cross directions and missing target',
                        'neutral/cool/warm/magenta/green and signed temperature endpoints',
                        'candidate/alarm/audio/config/DDR/source/color-ready/armed/debug flags',
                        'latency valid and invalid, zero, hexadecimal frame and diagnostic values',
                        'all menu pixels, visible boundaries, row gaps, and two-stage coordinate alignment',
                        'all four SW1 modes at each of five levels with unequal remembered values',
                        'control/panel/packed-level changes on consecutive pixels'],
                limitations=['no new TD synthesis/placement/timing evidence in this test',
                             'no camera image quality or detection behavior changed or accepted by this test',
                             'no board Chinese glyph readability or final latency core verification in this test'])
    assert source_start=={str(p.relative_to(R)):sha(p) for p in checked_sources},'HUD sources changed during simulation'
    write(V/'result.json',json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['status','page_cases','compared_pixels','control_switch_probes','elapsed_seconds']},ensure_ascii=False))
    print('CHINESE_HUD_PIXEL_COMPARE_PASS',str(V))

if __name__=='__main__':main()
