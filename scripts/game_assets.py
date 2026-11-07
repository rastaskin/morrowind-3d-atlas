"""Read-only Morrowind ESM/BSA access for the local 3D atlas."""
from pathlib import Path
import os
import struct
GAME=Path(os.environ['MORROWIND_DATA_DIR'])
def norm(s):return s.replace('\\','/').lower().strip('/')
class Assets:
 def __init__(self):
  self.index={}
  for name in ['Morrowind.bsa','Tribunal.bsa','Bloodmoon.bsa']:
   p=GAME/name
   with p.open('rb') as f:
    version,offset,count=struct.unpack('<III',f.read(12));assert version==0x100
    rows=[struct.unpack('<II',f.read(8)) for _ in range(count)]
    pointers=struct.unpack('<'+'I'*count,f.read(4*count));names=f.read(offset-12*count);start=12+offset+8*count
    for (size,pos),pointer in zip(rows,pointers):
     n=norm(names[pointer:names.index(b'\0',pointer)].decode('cp1252'));self.index[n]=(p,start+pos,size)
 def read(self,name):
  name=norm(name);loose=GAME/name
  if loose.exists():return loose.read_bytes()
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
