"""Generate a compact, deterministic Chinese OSD subset without production edits.

Run with the bundled Python. The output is a staging asset, not a board build.
Static glyph IDs are compact indices (NOT Unicode or ASCII code points).
Menu bit 8 marks a dynamic slot; low six bits retain the old slot numbering.
"""
from pathlib import Path
import argparse, hashlib, json, re
from PIL import Image, ImageDraw, ImageFont

HERE=Path(__file__).resolve().parent
DEFAULT_OLD=HERE/'legacy_ascii_font.v.txt'
ASCII=' 0123456789ABCDEFKSW.-/:'
TOKEN=re.compile(r'\{(\d+)\}')

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,text):p.write_text(text,encoding='utf-8',newline='\n')
def tokenize(s):
    parts=[];last=0
    for m in TOKEN.finditer(s):
        parts.extend(s[last:m.start()]);parts.append(int(m[1]));last=m.end()
    parts.extend(s[last:]);return parts

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--install',action='store_true',help='Install ROMs and compact glyph constants into this project')
    ap.add_argument('--spec',type=Path,default=HERE/'menu_zh.json')
    ap.add_argument('--font',type=Path,default=Path(r'C:\Windows\Fonts\simsun.ttc'))
    ap.add_argument('--old-ascii-source',type=Path,default=DEFAULT_OLD)
    ap.add_argument('--extra-text',type=Path,help='Optional UTF8 Chinese labels for later diagnostics')
    ap.add_argument('--out',type=Path,default=HERE/'generated')
    args=ap.parse_args();out=args.out;out.mkdir(parents=True,exist_ok=True)
    spec=json.loads(args.spec.read_text(encoding='utf-8'))
    assert spec['columns']==32 and spec['rows']==4
    labels=[s for rows in spec['panels'].values() for s in rows]
    labels += [s for terms in spec['dynamic_chinese_values'].values() for s in terms]
    if args.extra_text:labels.append(args.extra_text.read_text(encoding='utf-8'))
    chinese=sorted({c for s in labels for c in TOKEN.sub('',s) if ord(c)>127})
    unknown_ascii=sorted({c for s in labels for c in TOKEN.sub('',s) if ord(c)<128 and c not in ASCII and c not in '\r\n\t'})
    assert not unknown_ascii,unknown_ascii
    glyphs=list(ASCII)+['']*(32-len(ASCII))+chinese
    assert len(glyphs)<=256,('Too many subset glyphs',len(glyphs))
    char_to_id={c:i for i,c in enumerate(glyphs) if c}
    assert char_to_id['0']==1 and char_to_id['9']==10 and char_to_id['A']==11 and char_to_id['F']==16

    # Carry over the exact accepted ASCII bitmap (8x8 -> 16x16), rather than
    # silently changing digit shapes while adding Chinese.
    old=args.old_ascii_source.read_text(encoding='utf-8').split('module fusion_font_rom',1)[1]
    oldbits=[0]*1024
    for a,v in re.findall(r"rom\[(\d+)\]=8'h([0-9a-fA-F]+);",old):oldbits[int(a)]=int(v,16)
    # The legacy font did not define a decimal point (the old delay page
    # inserted blank spacing there). Add two rows for the new numeric format.
    if not any(oldbits[ord('.')*8:ord('.')*8+8]):
        oldbits[ord('.')*8+5]=0x30
        oldbits[ord('.')*8+6]=0x30
    font=ImageFont.truetype(str(args.font),16,index=0,layout_engine=ImageFont.Layout.BASIC)
    patterns=[[0]*16 for _ in range(256)]
    for c,gid in char_to_id.items():
        if ord(c)<128:
            for y in range(16):
                src=oldbits[ord(c)*8+y//2];bits=0
                for x in range(16):bits=(bits<<1)|((src>>(7-x//2))&1)
                patterns[gid][y]=bits
        else:
            image=Image.new('1',(16,16),0)
            ImageDraw.Draw(image).text((0,0),c,font=font,fill=1)
            bbox=font.getbbox(c)
            assert min(bbox[:2])>=0 and max(bbox[2:])<=16,('font clips cell',c,bbox)
            for y in range(16):
                v=0
                for x in range(16):v=(v<<1)|int(bool(image.getpixel((x,y))))
                patterns[gid][y]=v
        assert c==' ' or any(patterns[gid]),('empty required glyph',c,gid)

    menu=[0]*4096;row_lengths={}
    for p,rows in spec['panels'].items():
        panel=int(p);assert 0<=panel<32 and len(rows)==4
        for row,s in enumerate(rows):
            cells=tokenize(s);assert len(cells)<=32,(panel,row,len(cells),s)
            row_lengths[f'{panel}:{row}']=len(cells)
            for col,item in enumerate(cells):
                if isinstance(item,int):assert 0<=item<64;code=0x100|item
                else:code=char_to_id[item]
                menu[panel*128+row*32+col]=code
    font_words=[w for pattern in patterns for w in pattern]
    write(out/'font16.mem',''.join(f'{w:04x}\n' for w in font_words))
    write(out/'menu9.mem',''.join(f'{w:03x}\n' for w in menu))

    constants=['// Generated compact glyph IDs; do not use ASCII + 48.']
    constants+=['localparam [7:0] ZH_SPACE=8\'d0;',"localparam [7:0] ZH_DIGIT_BASE=8'd1;","localparam [7:0] ZH_HEX_A_BASE=8'd11;"]
    for c,gid in char_to_id.items():
        if ord(c)>127:constants.append(f"localparam [7:0] ZH_U{ord(c):04X}=8'd{gid}; // {c}")
    write(out/'glyph_ids.vh','\n'.join(constants)+'\n')

    # Literal initialization avoids fragile absolute .mem paths in imported TD
    # projects. These modules are only generated here; caller decides integration.
    for name,width,words,ow in [('chinese_menu_rom',9,menu,'O_code'),('chinese_font_rom',16,font_words,'O_bits')]:
        chunks=[f'module {name}(input wire I_clk,input wire [11:0] I_address,output reg [{width-1}:0] {ow});',
                f'(* ram_style="bram" *) reg [{width-1}:0] rom[0:4095];',
                'integer i;','initial begin','for(i=0;i<4096;i=i+1)rom[i]=0;']
        chunks += [f"rom[{i}]={width}'h{v:0{(width+3)//4}x};" for i,v in enumerate(words) if v]
        chunks += ['end',f'always @(posedge I_clk) {ow}<=rom[I_address];','endmodule']
        write(out/(name+'.v'),'\n'.join(chunks)+'\n')

    def draw_panel(panel,scale):
        image=Image.new('RGB',(1280,720),(20,25,28))
        if scale==2:origin=(16,552);step=36;cell=32
        else:origin=(16,600);step=24;cell=16
        for row in range(4):
            for col in range(32):
                code=menu[panel*128+row*32+col]
                if code&0x100:
                    slot=code&63
                    # Example states only. Delays are sample glyph previews,
                    # never advertised as a measured hardware delay.
                    samples={41:'1',42:'1',43:'1',44:'6',45:'C',46:'0',47:'2',48:'0',49:'0',
                             52:'3',54:'性',55:'中',56:'0',57:'中',58:'无',59:'0',60:'3',61:'5',62:'7',63:'9'}
                    c=samples.get(slot,'0')
                    if panel not in (13,14) and slot in [43,44,49,50]:
                        c={43:'中',44:'部',49:'中',50:'央'}[slot]
                    gid=char_to_id[c]
                else:gid=code
                for y,word in enumerate(patterns[gid]):
                    for x in range(16):
                        if (word>>(15-x))&1:
                            px=origin[0]+col*cell+x*scale;py=origin[1]+row*step+y*scale
                            for yy in range(scale):
                                for xx in range(scale):image.putpixel((px+xx,py+yy),(255,242,0))
        return image
    for panel in [0,4,5,6,7,8,9,10,11,12,13,14,15,28]:
        draw_panel(panel,2).save(out/f'panel-{panel:02d}-32px.png')
    draw_panel(13,1).save(out/'panel-13-16px.png')
    sheets=Image.new('RGB',(1280,160*5),(20,25,28))
    for i,p in enumerate([0,4,10,13,14]):
        sheets.paste(draw_panel(p,2).crop((0,540,1280,700)),(0,i*160))
    sheets.save(out/'contact-sheet-32px.png')

    manifest={'scope':'Staging Chinese UI assets only; no production edits, synthesis or hardware acceptance',
              'font_source':str(args.font),'font_source_sha256':sha(args.font),
              'old_ascii_source':str(args.old_ascii_source),'old_ascii_source_sha256':sha(args.old_ascii_source),
              'source_spec_sha256':sha(args.spec),'cjk_count':len(chinese),'ascii_count':len(ASCII),
              'reserved_static_ids':list(range(len(ASCII),32)),'max_static_glyph_id':len(glyphs)-1,
              'rom_font_words':4096,'rom_font_word_bits':16,'rom_menu_words':4096,'rom_menu_word_bits':9,
              'max_row_cells':max(row_lengths.values()),'row_lengths':row_lengths,
              'char_to_id':char_to_id,'files':{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='manifest.json'}}
    write(out/'manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    print(json.dumps({k:manifest[k] for k in ['cjk_count','ascii_count','max_static_glyph_id','max_row_cells']},ensure_ascii=False))
    if args.install:
        production=HERE.parents[1]/'user_source/hdl_source'
        write(production/'fusion_menu_rom.v',(out/'chinese_menu_rom.v').read_text(encoding='utf-8').replace('module chinese_menu_rom','module fusion_menu_rom').replace('O_code','O_char'))
        write(production/'fusion_chinese_font_rom.v',(out/'chinese_font_rom.v').read_text(encoding='utf-8').replace('module chinese_font_rom','module fusion_chinese_font_rom'))
        hud=production/'fusion_hud.v'
        before=hud.read_text(encoding='utf-8')
        marker=r'    // BEGIN GENERATED CHINESE GLYPH IDS.*?    // END GENERATED CHINESE GLYPH IDS'
        inserted='    // BEGIN GENERATED CHINESE GLYPH IDS\n'+'\n'.join('    '+line for line in constants)+'\n    // END GENERATED CHINESE GLYPH IDS'
        after,n=re.subn(marker,lambda m:inserted,before,flags=re.S)
        assert n==1,('HUD constant markers missing',n)
        write(hud,after)
    print('CHINESE_ASSETS_GENERATED',str(out))

if __name__=='__main__':main()
