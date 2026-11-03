from pathlib import Path
R=Path(__file__).resolve().parents[1];H=R/'user_source/hdl_source'
def d(start,n=1):return ''.join(chr(128+i) for i in range(start,start+n))
reset='K3 HOLD 2S RESET  K4 HOLD 1S AUTO COLOR  READY '+d(41)
fps='CAM SOF FPS '+d(19,2)+'  HDMI FPS '+d(21,2)+'  RUN '+d(14,5)+' S'
keys1='K1 CLEAR  K2 CARTOON  K3 SKETCH  K4 CLEAN EDGE'
keys2='K1 FLAME K2 TRACK K3 LINK/MUTE K4 AID  HOLD K4 WB'
menus={
0:['BASE CLEAR  AUTO COLOR '+d(58)+'  READY '+d(41), 'K1 AUTO K2 COOLER K3 WARMER K4 GREEN MAGENTA', 'TEMP '+d(55,2)+'  TINT '+d(57)+'  K4 HOLD 1S RECALIBRATE',reset],
1:['BASE CLEAR  RUNTIME DETAILS',fps,'CAM CFG '+d(38)+'  DDR READY '+d(39)+'  SOURCE '+d(40),reset],
2:['HELP  ONE OF SW1 SW2 SW3 UP  SW4 INDEPENDENT','SW1 STYLE  SW2 RECOGNITION  SW3 STATUS  SW4 LOGO HELP','SHORT KEYS SELECT  LONG K3 RESET  SW5 BUZZER',reset],
8:['SW2 FLAME DETECTION  EXT2', 'TARGET '+d(31)+'  CONFIRMED '+d(32)+'  READY '+d(42)+' COLOR READY '+d(41), 'YELLOW CANDIDATE PIXELS '+d(8,6),keys2],
9:['SW2 TRACKING  ADV2','TARGET '+d(31)+'  CONFIRMED '+d(32)+'  READY '+d(42)+' COLOR READY '+d(41),'CENTER X '+d(0,4)+' Y '+d(4,4)+'  PIXELS '+d(8,6),keys2],
10:['SW2 SOUND LIGHT LINK  EXT3','CONFIRMED '+d(32)+'  AUDIO ENABLE '+d(33)+'  READY '+d(42)+' COLOR READY '+d(41),'CENTER X '+d(0,4)+' Y '+d(4,4)+'  PIXELS '+d(8,6),keys2],
11:['SW2 FIRST AID SIGN  GREEN PANEL WHITE CROSS','AID FOUND '+d(31)+'  READY '+d(42)+'  COLOR READY '+d(41),'POSITION '+d(43,6)+' '+d(49,6)+'  X '+d(0,4)+' Y '+d(4,4),keys2],
12:['SW3 RUNTIME PERFORMANCE  EXT4',fps,'FRAME EVENT RATES  NOT END TO END LATENCY','K1 RUN  K2 LATENCY  K3 LINK STATUS  K4 ISP'],
13:['SW3 END TO END LATENCY  ADV3','PENDING  FRAME MATCHED MEASUREMENT NOT CONNECTED','RUNTIME COUNTERS DO NOT REPRESENT LATENCY','K1 RUN  K2 LATENCY  K3 LINK STATUS  K4 ISP'],
14:['SW3 LINK DIAGNOSTICS','CAM CFG '+d(38)+'  DDR READY '+d(39)+'  SOURCE '+d(40),'RX '+d(34)+' '+d(35)+' '+d(36)+' '+d(37)+'  BUFFER ERROR COUNTERS PENDING','K1 RUN  K2 LATENCY  K3 LINK STATUS  K4 ISP'],
15:['SW3 EXISTING ISP PARAMETERS  ADV5','EXPOSURE LINES '+d(23,5)+'  GAIN INDEX '+d(28,3),'COLOR READY '+d(41)+'  DEHAZE ON  COLOR READY','K4 HOLD 1S AUTO COLOR  K3 HOLD 2S RESET'],
28:['INVALID SWITCH COMBINATION','ONLY ONE OF SW1 SW2 SW3 MAY BE UP  SW4 IS OSD','CLEAR VIDEO  ALL ALARM OUTPUTS DISABLED',reset],
}
for i,name in enumerate(['CLEAR','CARTOON','SKETCH','CLEAN EDGE']):
    menus[4+i]=['SW1 IMAGE STYLE  EXT1 ADV1  '+name,keys1,reset,'SW4 LOGO INFO  STYLE COLOR SAFE  NOISE FILTER']
lines=['module fusion_menu_rom(input wire I_clk,input wire [12:0] I_address,output reg [7:0] O_char);',
       '(* ram_style="bram" *) reg [7:0] rom[0:8191];','integer i;','initial begin',
       'for(i=0;i<8192;i=i+1)rom[i]=8\'d32;']
for panel,rows in menus.items():
    for row,text in enumerate(rows):
        assert len(text)<=64,(panel,row,len(text),text)
        for col,ch in enumerate(text):
            if ch!=' ':lines.append(f"rom[{panel*256+row*64+col}]=8'd{ord(ch)};")
lines+=['end','always @(posedge I_clk) O_char<=rom[I_address];','endmodule']
columns={
'A':'7e1111117e','B':'7f49494936','C':'3e41414122','D':'7f4141221c','E':'7f49494941','F':'7f09090901',
'G':'3e41495132','H':'7f0808087f','I':'00417f4100','J':'2040413f01','K':'7f08142241','L':'7f40404040',
'M':'7f020c027f','N':'7f0408107f','O':'3e4141413e','P':'7f09090906','Q':'3e4151215e','R':'7f09192946',
'S':'4649494931','T':'01017f0101','U':'3f4040403f','V':'1f2040201f','W':'3f4038403f','X':'6314081463',
'Y':'0708700807','Z':'6151494543','0':'3e5149453e','1':'00427f4000','2':'4261514946','3':'2141454b31',
'4':'1814127f10','5':'2745454539','6':'3c4a494930','7':'0171090503','8':'3649494936','9':'064949291e',
':':'0036360000','/':'2010080402','-':'0808080808', ' ':'0000000000'}
lines+=['module fusion_font_rom(input wire I_clk,input wire [9:0] I_address,output reg [7:0] O_bits);',
        '(* ram_style="bram" *) reg [7:0] rom[0:1023];','integer i;','initial begin','for(i=0;i<1024;i=i+1)rom[i]=0;']
for ch,hexcols in columns.items():
    cols=bytes.fromhex(hexcols)
    for row in range(7):
        bits=sum(((c>>row)&1)<<(6-col) for col,c in enumerate(cols))
        if bits:lines.append(f"rom[{ord(ch)*8+row}]=8'h{bits:02x};")
lines+=['end','always @(posedge I_clk) O_bits<=rom[I_address];','endmodule']
(H/'fusion_menu_rom.v').write_text('\n'.join(lines)+'\n',encoding='ascii')
print('Menu and font ROM generated:',len(menus),'screens')
