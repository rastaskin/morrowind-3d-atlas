"""Export full-resolution landscape and real exterior NIF geometry, read-only."""
from pathlib import Path
import os
import io,json,struct,time,hashlib,logging,math
import numpy as np
from PIL import Image
from game_assets import GAME,Assets,records,text,norm,is_editor_model
from atlas_profile import current_profile
from world_data import read_world,build_catalog
ROOT=Path(os.environ['ATLAS_OUTPUT_DIR']);OUT=ROOT/'assets3d'
for d in ['terrain','models','textures']:(OUT/d).mkdir(parents=True,exist_ok=True)
assets=Assets();texture_cache={};definitions={};cells={};lands={};palette={}
def image(name):
 name=norm(name)
 if not name.startswith('textures/'):name='textures/'+name
 if name in texture_cache:return texture_cache[name]
 try:im=Image.open(io.BytesIO(assets.read(name))).convert('RGBA')
 except Exception:
  try:im=Image.open(io.BytesIO(assets.read(str(Path(name).with_suffix('.dds'))))).convert('RGBA')
  except Exception:im=Image.new('RGBA',(16,16),(130,119,95,255))
 texture_cache[name]=im;return im
profile=current_profile();world=read_world(profile)
definitions=world['definitions'];lands=world['lands'];palette=world['palettes']
base_path=Path(os.environ.get('ATLAS_BASE_CATALOG',Path(__file__).resolve().parents[1]/'public/catalog.json'))
catalog=build_catalog(world,json.loads(base_path.read_text(encoding='utf8')))
(OUT/'catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,separators=(',',':')),encoding='utf8')
print('catalog',len(catalog['locations']),'lands',len(lands),flush=True)
terrain=[];instances=[];modelnames=set();small_textures={}
def transpose_vtex(v):
 # ESM stores sixteen 4x4 blocks, ordered bottom-to-top.
 src=np.frombuffer(v,dtype='<u2');dst=np.zeros((16,16),dtype=np.uint16);p=0
 for by in range(4):
  for bx in range(4):
   for yy in range(4):
    for xx in range(4):dst[by*4+yy,bx*4+xx]=src[p];p+=1
 return dst
for i,((x,y),(d,game)) in enumerate(lands.items()):
 v=d['VHGT'];delta=np.frombuffer(v,dtype=np.int8,count=4225,offset=4).reshape(65,65).astype(float)
 first=struct.unpack_from('<f',v)[0]+np.cumsum(delta[:,0]);h=(first[:,None]+np.cumsum(np.column_stack([np.zeros(65),delta[:,1:]]),axis=1))*8
 if h.max()< -200:continue
 key=f'{x}_{y}';texmap=transpose_vtex(d.get('VTEX',bytes(512)));pal=palette[game]
 colors=np.ones((65,65,3),np.float32)
 if 'VCLR' in d:colors=np.frombuffer(d['VCLR'],np.uint8).reshape(65,65,3).astype(float)/255
 tile=np.empty((512,512,3),np.uint8)
 for yy in range(16):
  for xx in range(16):
   name=pal.get(int(texmap[yy,xx]),'tx_land_default.tga')
   if name not in small_textures:small_textures[name]=np.asarray(image(name).convert('RGB').resize((32,32),Image.Resampling.LANCZOS))
   tile[yy*32:(yy+1)*32,xx*32:(xx+1)*32]=small_textures[name]
 tint=np.asarray(Image.fromarray(np.uint8(colors*255)).resize((512,512),Image.Resampling.BILINEAR))/255
 baked=np.uint8(np.clip(tile.astype(float)*tint,0,255))
 # Full 65x65 grid; 128 game units between samples, no decimation.
 h.astype('<f4').tofile(OUT/'terrain'/f'{key}.bin')
 thumb=np.asarray(Image.fromarray(baked).resize((9,9),Image.Resampling.BILINEAR))
 terrain.append({'x':x,'y':y,'key':key,'h':np.round(h[::8,::8].flatten()/819.2,5).tolist(),'c':thumb.reshape(-1,3).tolist(),'min':float(h.min()/819.2),'max':float(h.max()/819.2)})
 if i%250==0:print('terrain',i,len(lands),flush=True)
for ref in world['refs'].values():
 cell=world['cells'].get(ref['cell'])
 if not cell or cell['interior'] or 'NAME' not in ref or 'DATA' not in ref:continue
 x,y=cell['grid'];name=definitions.get(ref['NAME'].casefold())
 if not name or is_editor_model(name):continue
 vals=struct.unpack('<6f',ref['DATA']);sc=struct.unpack('<f',ref.get('XSCL',struct.pack('<f',1)))[0]
 if not all(math.isfinite(v) for v in vals) or not .01<sc<100:continue
 key=hashlib.sha1(norm(name).encode()).hexdigest()[:12];modelnames.add(name)
 instances.append([key,*[round(float(v),5) for v in vals],sc,x,y])
manifest={'terrain':terrain,'instances':instances,'models':{},'failures':[],'scale':819.2,'source':'Morrowind GOTY + Tamriel Rebuilt' if profile['tamrielRebuilt'] else 'Morrowind GOTY','plugins':[p['name'] for p in profile['plugins']],'resolution':65}
(OUT/'world.json').write_text(json.dumps(manifest,separators=(',',':')),encoding='utf8')
print('terrain complete',len(terrain),'instances',len(instances),'unique models',len(modelnames),flush=True)

# Separate processes avoid the Python parser's GIL on large Tamriel Rebuilt meshes.
import sys,subprocess
unique={norm(name):name for name in modelnames};names=sorted(unique.values(),key=lambda n:('ex_' not in n.lower(),n))
work=ROOT.parent/'config.local.model-work';work.mkdir(exist_ok=True)
command=[sys.executable] if getattr(sys,'frozen',False) else [sys.executable,str(Path(__file__).resolve().parents[1]/'desktop.py')]
workers=[];handles=[];jobs=min(4,os.cpu_count() or 1)
del world
for index in range(jobs):
 batch=work/f'models-{index}.json';batch.write_text(json.dumps(names[index::jobs]),encoding='utf8');log=batch.with_suffix('.log').open('w',encoding='utf8');handles.append(log)
 workers.append((subprocess.Popen([*command,'--export-models','--batch',str(batch)],stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)),batch))
try:
 for process,batch in workers:
  if process.wait():raise RuntimeError('Model export worker failed; see '+batch.with_suffix('.log').name)
  result=json.loads(batch.with_suffix('.result.json').read_text(encoding='utf8'));manifest['models'].update(result['models']);manifest['failures'].extend(result['failures'])
finally:
 for process,batch in workers:
  if process.poll() is None:process.terminate();process.wait()
 for handle in handles:handle.close()
(OUT/'world.json').write_text(json.dumps(manifest,separators=(',',':')),encoding='utf8')
print('DONE',len(terrain),'terrain tiles',len(manifest['models']),'models',len(instances),'instances','failures',len(manifest['failures']),flush=True)
