"""Read-only NIF conversion. Workers share only atomic, completed output files."""
from pathlib import Path
import io,json,os,time,hashlib,logging,math
import numpy as np
from PIL import Image
from game_assets import Assets,norm
OUT=Path(os.environ['ATLAS_OUTPUT_DIR'])/'assets3d'
assets=Assets();texture_cache={}
def image(name):
 name=norm(name)
 if not name.startswith('textures/'):name='textures/'+name
 if name in texture_cache:return texture_cache[name]
 try:im=Image.open(io.BytesIO(assets.read(name))).convert('RGBA')
 except Exception:
  try:im=Image.open(io.BytesIO(assets.read(str(Path(name).with_suffix('.dds'))))).convert('RGBA')
  except Exception:im=Image.new('RGBA',(16,16),(130,119,95,255))
 texture_cache[name]=im;return im

if not hasattr(time,'clock'):time.clock=time.perf_counter
from pyffi.formats.nif import NifFormat as N
# OpenMW reads this Morrowind-era block with the ordinary NiNode layout.
# https://github.com/OpenMW/openmw/blob/master/components/nif/niffile.cpp
if not hasattr(N,'NiCollisionSwitch'):N.NiCollisionSwitch=N.NiNode
# PyFFI's duplicate Num UV Sets field otherwise allocates a byte for 4.0.0.2.
oldinit=N.NiGeometryData.__init__
def init_geometry(self,*a,**kw):
 oldinit(self,*a,**kw);self._num_uv_sets_value_=N.ushort()
N.NiGeometryData.__init__=init_geometry
logging.disable(logging.CRITICAL)
def export_model(name):
 key=hashlib.sha1(norm(name).encode()).hexdigest()[:12];dest=OUT/'models'/f'{key}.json'
 if dest.exists():
  try:return key,json.loads(dest.read_text())
  except (ValueError,OSError):pass
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
 bp=OUT/'models'/f'{key}.bin';temp=bp.with_suffix('.'+str(os.getpid())+'.tmp');temp.write_bytes(binary);temp.replace(bp)
 desc={'parts':parts,'radius':extent/819.2,'name':name};temp=dest.with_suffix('.'+str(os.getpid())+'.tmp');temp.write_text(json.dumps(desc,separators=(',',':')),encoding='utf8');temp.replace(dest);return key,desc

def run_batch(batch_path):
 names=json.loads(Path(batch_path).read_text(encoding='utf8'));result={'models':{},'failures':[]}
 for i,name in enumerate(names):
  try:
   key,desc=export_model(name);result['models'][key]={'name':name,'radius':desc['radius']}
  except Exception as error:result['failures'].append({'model':name,'error':str(error)[:180]})
  if i%40==0:print('models',i,'of',len(names),'failed',len(result['failures']),flush=True)
 Path(batch_path).with_suffix('.result.json').write_text(json.dumps(result,separators=(',',':')),encoding='utf8')
