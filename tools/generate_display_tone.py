"""Separate grey-floor suppression and midtones; preserve V7 on SW2/SW3."""
from pathlib import Path
R=Path(__file__).resolve().parents[1]
def day(y):
 return y//2 if y<32 else y-16 if y<64 else y+(y-128)//4 if y<160 else y+8 if y<224 else y+(255-y)//4
def legacy_night(y):
 return y+y//2 if y<32 else y+16 if y<64 else y+(128-y)//4 if y<128 else y
def night(y):
 points=[(0,0),(16,12),(32,40),(64,76),(128,132),(160,164),(224,228),(255,255)]
 for (x0,v0),(x1,v1) in zip(points,points[1:]):
  if y<=x1:return v0+(y-x0)*(v1-v0)//(x1-x0)
 raise AssertionError(y)
def tone(y,level,legacy=False):return ((7-level)*day(y)+level*(legacy_night(y) if legacy else night(y))+3)//7
values=[tone(y,s,k==1) for k in range(2) for s in range(8) for y in range(256)]
for s in range(16):
 a=values[s*256:(s+1)*256];assert a[0]==0 and a[-1]==255 and all(a[i]<=a[i+1] for i in range(255))
old=[int(s,2) for s in (R.parent/'07_stylize_flame_fusion_v7_shadow_clean/user_source/hdl_source/display_tone.dat').read_text().split()]
assert values[2048:]==old,'legacy SW2/SW3 curve changed'
assert night(20)<20 and night(24)<legacy_night(24) and night(96)>96 and night(128)>128
(R/'user_source/hdl_source/display_tone.dat').write_text(''.join(f'{v:08b}\n' for v in values),encoding='ascii')
print('DISPLAY_TONE_TABLE_PASS',len(values),'values; visual grey floor lower/midtones higher; legacy 2048 values exact')
