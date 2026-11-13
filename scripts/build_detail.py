"""Shared source-resolution terrain atlas and original material indices."""
from pathlib import Path
import os
import io,json,struct,math
import numpy as np
from PIL import Image
from game_assets import Assets,GAME,records,text,norm
from atlas_profile import current_profile
from world_data import read_world
ROOT=Path(os.environ['ATLAS_OUTPUT_DIR']);OUT=ROOT/'assets3d';assets=Assets();palettes={};lands={}
world=read_world(current_profile(),terrain_only=True);palettes=world['palettes'];lands=world['lands']
names=sorted(set(norm(n) for p in palettes.values() for n in p.values())|{'tx_land_default.tga'})
if len(names)>65536:raise ValueError('Too many landscape textures')
lookup={n:i for i,n in enumerate(names)};grid=max(16,2**math.ceil(math.log2(math.ceil(math.sqrt(len(names))))));size=min(256,8192//grid);atlas=Image.new('RGB',(grid*size,grid*size));missing=[]
aliases={'tx_land_default.tga':'_land_default.dds','tx_lavacrust00.tga':'tx_lavacrust01.dds','tx_ma_sandstone02.tga':'tx_sandstone02.dds'}
for i,name in enumerate(names):
 try:
  source=aliases.get(name,name)
  try:b=assets.read('textures/'+source)
  except KeyError:b=assets.read('textures/'+str(Path(source).with_suffix('.dds')))
  im=Image.open(io.BytesIO(b)).convert('RGB').resize((size,size),Image.Resampling.LANCZOS)
 except Exception:missing.append(name);im=Image.new('RGB',(size,size),(120,113,89))
 atlas.paste(im,((i%grid)*size,(i//grid)*size))
atlas.save(OUT/'terrain-atlas.webp',quality=96,method=5)
count=0
for (x,y),(d,game) in lands.items():
 key=f'{x}_{y}'
 if not (OUT/'terrain'/f'{key}.bin').exists():continue
 pal=palettes[game];src=np.frombuffer(d.get('VTEX',bytes(512)),dtype='<u2');a=np.zeros((16,16),np.uint16);p=0
 for by in range(4):
  for bx in range(4):
   for yy in range(4):
    for xx in range(4):a[by*4+yy,bx*4+xx]=lookup[norm(pal.get(int(src[p]),'tx_land_default.tga'))];p+=1
 encoded=np.zeros((16,16,3),np.uint8);encoded[:,:,0]=a&255;encoded[:,:,1]=a>>8
 Image.fromarray(encoded[::-1]).save(OUT/'terrain'/f'{key}-index.png')
 c=np.frombuffer(d.get('VCLR',bytes([255])*(65*65*3)),dtype=np.uint8).reshape(65,65,3)
 Image.fromarray(c[::-1]).save(OUT/'terrain'/f'{key}-tint.png');count+=1
(OUT/'detail.json').write_text(json.dumps({'grid':grid,'size':size,'indexChannels':2,'textures':len(names),'tiles':count,'missing':missing,'aliases':aliases}),encoding='utf8')
print(json.dumps({'textures':len(names),'tiles':count,'missing':missing}))
