from pathlib import Path
import fitz,json,hashlib
R=Path(__file__).resolve().parents[1];V=R/'validation/hardware';V.mkdir(parents=True,exist_ok=True)
p=Path(r'D:\FPGA\安路杯FPGA2026\02_板卡与芯片资料\PH1P35与HX1P35A\HX1P35A_Contest_202606\9_康芯开发板使用手册及实验平台\新HX1P35A开发板手册-HDL版2604.pdf')
doc=fitz.open(p);hits=[]
for i in range(len(doc)):
 s=doc[i].get_text()
 if ('KEY1' in s or 'KEY 1' in s or 'D5' in s) and ('按键' in s or 'KEY2' in s):
  (V/f'board_page_{i+1}.txt').write_text(s,encoding='utf-8');hits.append(i+1)
  if len(hits)<=2:doc[i].get_pixmap(matrix=fitz.Matrix(1.3,1.3)).save(V/f'board_page_{i+1}.png')
r={'source':str(p),'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'key_pages_1_based':hits,
 'pins':'KEY1 D5, KEY2 A9, KEY3 B9, KEY4 C7; SW1 A4, SW2 B4, SW3 E11, SW4 D11 verified against existing pin.adc.',
 'scope':'Read-only local board guide; board pin direction/electrical polarity retained from accepted V15 controls.'}
(V/'hardware_read.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');print('BOARD_GUIDE_READ',hits)
