"""Export full-resolution landscape and real exterior NIF geometry, read-only."""
from pathlib import Path
import os
import io,json,struct,time,hashlib,logging,math
import numpy as np
from PIL import Image
from game_assets import GAME,Assets,records,text,norm
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
for game in ['Morrowind','Tribunal','Bloodmoon']:
 local_palette={}
 for typ,ss in records(GAME/(game+'.esm'),{'LAND','CELL','STAT','DOOR','ACTI','CONT','LTEX'}):
  if typ in {'STAT','DOOR','ACTI','CONT'}:
   d=dict(ss)
   if 'MODL' in d:definitions[text(d['NAME']).lower()]=text(d['MODL'])
  elif typ=='LTEX':
   d=dict(ss);local_palette[struct.unpack('<I',d['INTV'])[0]+1]=text(d['DATA'])
  elif typ=='LAND':
   d=dict(ss)
   if 'VHGT' not in d:continue
   xy=struct.unpack('<ii',d['INTV']);lands[xy]=(d,game)
  else:
   head={};refs=[];ref=None
   for t,v in ss:
    if t=='FRMR':
     if ref:refs.append(ref)
     ref={'id':struct.unpack('<I',v)[0]}
    elif ref is None:head[t]=v
    else:ref[t]=v
   if ref:refs.append(ref)
   flags,x,y=struct.unpack('<Iii',head['DATA'])
   if flags&1:continue
   c=cells.setdefault((x,y),{})
   for r in refs:c[r['id']]=r
 palette[game]=local_palette

terrain=[];instances=[];modelnames=set()
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
 if game!='Morrowind':pal={**palette['Morrowind'],**pal}
 colors=np.ones((65,65,3),np.float32)
 if 'VCLR' in d:colors=np.frombuffer(d['VCLR'],np.uint8).reshape(65,65,3).astype(float)/255
 tile=np.empty((512,512,3),np.uint8)
 for yy in range(16):
  for xx in range(16):
   name=pal.get(int(texmap[yy,xx]),'tx_land_default.tga');im=image(name).convert('RGB').resize((32,32),Image.Resampling.LANCZOS)
   tile[yy*32:(yy+1)*32,xx*32:(xx+1)*32]=np.asarray(im)
 tint=np.asarray(Image.fromarray(np.uint8(colors*255)).resize((512,512),Image.Resampling.BILINEAR))/255
 baked=np.uint8(np.clip(tile.astype(float)*tint,0,255));Image.fromarray(baked[::-1]).save(OUT/'terrain'/f'{key}.jpg',quality=90)
 # Full 65x65 grid; 128 game units between samples, no decimation.
 h.astype('<f4').tofile(OUT/'terrain'/f'{key}.bin')
 thumb=np.asarray(Image.fromarray(baked).resize((9,9),Image.Resampling.BILINEAR))
 terrain.append({'x':x,'y':y,'key':key,'h':np.round(h[::8,::8].flatten()/819.2,5).tolist(),'c':thumb.reshape(-1,3).tolist(),'min':float(h.min()/819.2),'max':float(h.max()/819.2)})
 if i%250==0:print('terrain',i,len(lands),flush=True)
for (x,y),rs in cells.items():
 for ref in rs.values():
  if 'NAME' not in ref or 'DATA' not in ref or 'DELE' in ref:continue
  name=definitions.get(text(ref['NAME']).lower())
  if not name:continue
  vals=struct.unpack('<6f',ref['DATA']);sc=struct.unpack('<f',ref.get('XSCL',struct.pack('<f',1)))[0]
  if not all(math.isfinite(v) for v in vals) or not .01<sc<100:continue
  key=hashlib.sha1(norm(name).encode()).hexdigest()[:12];modelnames.add(name)
  instances.append([key,*[round(float(v),5) for v in vals],sc,x,y])
manifest={'terrain':terrain,'instances':instances,'models':{},'failures':[],'scale':819.2,'source':'Original Morrowind + Tribunal + Bloodmoon ESM/BSA','resolution':65}
(OUT/'world.json').write_text(json.dumps(manifest,separators=(',',':')),encoding='utf8')
print('terrain complete',len(terrain),'instances',len(instances),'unique models',len(modelnames),flush=True)

if not hasattr(time,'clock'):time.clock=time.perf_counter
from pyffi.formats.nif import NifFormat as N
# PyFFI's duplicate Num UV Sets field otherwise allocates a byte for 4.0.0.2.
oldinit=N.NiGeometryData.__init__
def init_geometry(self,*a,**kw):
 oldinit(self,*a,**kw);self._num_uv_sets_value_=N.ushort()
N.NiGeometryData.__init__=init_geometry
logging.disable(logging.CRITICAL)
def export_model(name):
 key=hashlib.sha1(norm(name).encode()).hexdigest()[:12];dest=OUT/'models'/f'{key}.json'
 if dest.exists():return key,json.loads(dest.read_text())
 data=N.Data();data.read(io.BytesIO(assets.read('meshes/'+name)));parts=[];binary=bytearray();extent=0
 for root in data.roots:
  for node in root.get_global_iterator():
   if not isinstance(node,N.NiTriBasedGeom) or not node.data or node.flags&1:continue
   chain=root.find_chain(node,block_type=N.NiAVObject)
   if any(isinstance(n,N.RootCollisionNode) for n in chain):continue
   gd=node.data;verts=np.array([[v.x,v.y,v.z,1] for v in gd.vertices],dtype=float)
   if not len(verts):continue
   m=np.array(node.get_transform(root).as_list())@np.array(root.get_transform().as_list());verts=(verts@m)[:,:3]
   extent=max(extent,float(np.linalg.norm(verts,axis=1).max()))
   # Keep model coordinates Z-up; browser converts the instance as a whole.
   normals=np.array([[n.x,n.y,n.z] for n in gd.normals],dtype=float) if gd.has_normals else np.zeros((len(verts),3))
   if len(normals):normals=normals@np.linalg.inv(m[:3,:3]).T;normals/=np.maximum(np.linalg.norm(normals,axis=1)[:,None],1e-8)
   uvs=np.array([[uv.u,1-uv.v] for uv in gd.uv_sets[0]]) if len(gd.uv_sets) else np.zeros((len(verts),2))
   idx=np.array(list(gd.get_triangles()),dtype='<u4').flatten()
   if not len(idx):continue
   tex=None;diffuse=[1,1,1];alpha=False
   for prop in node.properties:
    if isinstance(prop,N.NiTexturingProperty) and prop.has_base_texture and prop.base_texture.source:
     source=prop.base_texture.source.file_name.decode('cp1252');tid=hashlib.sha1(norm(source).encode()).hexdigest()[:12];tex=f'textures/{tid}.webp';tp=OUT/tex
     if not tp.exists():
      im=image(source);im.thumbnail((1024,1024));im.save(tp,quality=93,method=3)
    elif isinstance(prop,N.NiAlphaProperty):alpha=True
    elif isinstance(prop,N.NiMaterialProperty):diffuse=[prop.diffuse_color.r,prop.diffuse_color.g,prop.diffuse_color.b]
   inter=np.column_stack([verts/819.2,normals,uvs]).astype('<f4');vo=len(binary);binary.extend(inter.tobytes());ioff=len(binary);binary.extend(idx.tobytes())
   parts.append({'v':vo,'n':len(verts),'i':ioff,'count':len(idx),'texture':tex,'color':diffuse,'alpha':alpha})
 if not parts:raise ValueError('No visible geometry')
 (OUT/'models'/f'{key}.bin').write_bytes(binary)
 desc={'parts':parts,'radius':extent/819.2,'name':name};dest.write_text(json.dumps(desc,separators=(',',':')),encoding='utf8');return key,desc
# Common architecture first; each mesh is cached and reused for every instance.
for i,name in enumerate(sorted(modelnames,key=lambda n:('ex_' not in n.lower(),n))):
 try:
  key,desc=export_model(name);manifest['models'][key]={'radius':desc['radius'],'name':name}
 except Exception as e:manifest['failures'].append({'model':name,'error':str(e)[:180]})
 if i%40==0:
  p=OUT/'world.tmp';p.write_text(json.dumps(manifest,separators=(',',':')),encoding='utf8');p.replace(OUT/'world.json');print('models',i,'ok',len(manifest['models']),'failed',len(manifest['failures']),flush=True)
(OUT/'world.json').write_text(json.dumps(manifest,separators=(',',':')),encoding='utf8')
print('DONE',len(terrain),'terrain tiles',len(manifest['models']),'models',len(instances),'instances','failures',len(manifest['failures']),flush=True)
