"""Read-only Morrowind ESM/BSA access for the local 3D atlas."""
from pathlib import Path
import os
import struct
GAME=Path(os.environ['MORROWIND_DATA_DIR'])
def norm(s):return s.replace('\\','/').lower().strip('/')
def is_editor_model(name):
 return norm(name).rsplit('/',1)[-1] in {'editormarker.nif','editormarker_box_01.nif','marker_divine.nif','marker_prison.nif','marker_temple.nif'}
class Assets:
 def __init__(self,profile=None):
  from atlas_profile import current_profile
  profile=profile or current_profile();self.directories=[Path(p) for p in profile['dataDirs']]
  self.index={}
  for archive in profile['archives']:
   p=Path(archive)
   with p.open('rb') as f:
    version,offset,count=struct.unpack('<III',f.read(12));assert version==0x100
    rows=[struct.unpack('<II',f.read(8)) for _ in range(count)]
    pointers=struct.unpack('<'+'I'*count,f.read(4*count));names=f.read(offset-12*count);start=12+offset+8*count
    for (size,pos),pointer in zip(rows,pointers):
     n=norm(names[pointer:names.index(b'\0',pointer)].decode('cp1252'));self.index[n]=(p,start+pos,size)
 def read(self,name):
  name=norm(name)
  if '..' in name.split('/'):raise ValueError('Invalid asset path')
  for directory in reversed(self.directories):
   loose=directory/name
   if loose.is_file():return loose.read_bytes()
  p,pos,size=self.index[name]
  with p.open('rb') as f:f.seek(pos);return f.read(size)
def records(path,types):
 b=path.read_bytes();p=0
 while p<len(b):
  t=b[p:p+4].decode('ascii');n=struct.unpack_from('<I',b,p+4)[0];end=p+16+n
  if end>len(b):raise ValueError('Truncated ESM')
  if t in types:yield t,list(subrecords(b[p+16:end]))
  p=end
def subrecords(b):
 p=0
 while p<len(b):
  t=b[p:p+4].decode('ascii');n=struct.unpack_from('<I',b,p+4)[0];p+=8
  if p+n>len(b):raise ValueError('Truncated subrecord')
  yield t,b[p:p+n];p+=n
def text(v):return v.rstrip(b'\0').decode('cp1252')
