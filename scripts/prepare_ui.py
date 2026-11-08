"""Local Morrowind UI assets and browser font; no game files modified."""
from pathlib import Path
import os
from PIL import Image
from game_assets import Assets
import io,json
ROOT=Path(os.environ['ATLAS_OUTPUT_DIR']);OUT=ROOT/'ui';OUT.mkdir(exist_ok=True);assets=Assets();manifest=[]
def img(name):
 raw=assets.read('textures/'+name+'.dds');im=Image.open(io.BytesIO(raw)).convert('RGBA');return im
def frame(stem,size):
 n=32;s=size;out=Image.new('RGBA',(n,n))
 for suffix,box in [('top',(s,0,n-s,s)),('bottom',(s,n-s,n-s,n)),('left',(0,s,s,n-s)),('right',(n-s,s,n,n-s))]:
  im=img(stem+'_'+suffix);out.paste(im.resize((box[2]-box[0],box[3]-box[1]),Image.Resampling.NEAREST),box)
 for suffix,point in [('top_left_corner',(0,0)),('top_right_corner',(n-s,0)),('bottom_left_corner',(0,n-s)),('bottom_right_corner',(n-s,n-s))]:out.paste(img(stem+'_'+suffix),point)
 out.save(OUT/(stem+'.png'));manifest.append(stem)
frame('menu_thick_border',4);frame('menu_thin_border',2);frame('menu_button_frame',4)
for name in ['menu_rightbuttonup_center','menu_rightbuttondown_center','menu_head_block_middle','menu_scroll_bar_vert','menu_scroll_elevator']:
 img(name).save(OUT/(name+'.png'));manifest.append(name)
(OUT/'sources.json').write_text(json.dumps({'textures':'Local original Morrowind.bsa','frames':manifest,'font':'MysticCards, bundled with the application under SIL OFL 1.1','font_source':'https://github.com/OpenMW/openmw/tree/master/files/data/fonts'},ensure_ascii=False,indent=2),encoding='utf8')
print('Prepared original frames and buttons. The map font is bundled with the application.')
