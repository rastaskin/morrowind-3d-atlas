"""Create a synthetic save for the browser smoke test, with no player data."""
from pathlib import Path
from PIL import Image
import struct,io
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'.tmp';OUT.mkdir(exist_ok=True)
def sub(t,b):return t.encode()+struct.pack('<I',len(b))+b
def rec(t,b):return t.encode()+struct.pack('<III',len(b),0,0)+b
buf=io.BytesIO();Image.new('RGBA',(32,32),(0,0,0,0)).save(buf,format='PNG')
save=rec('TES3',sub('FORM',struct.pack('<I',34)))+rec('CSTA',sub('NAME',b'\x02Addamasartus')+sub('FTEX',bytes(8)+buf.getvalue()))
(OUT/'synthetic.omwsave').write_bytes(save)
def classic(name,encoding='cp1252'):
 header=bytearray(300);struct.pack_into('<fI',header,0,1.3,32)
 game=bytearray(124);game[24:24+len(b'Seyda Neen')]=b'Seyda Neen'
 cell=sub('NAME',name.encode(encoding)+b'\0')+sub('DATA',struct.pack('<Iii',1,0,0))+sub('NAM8',bytes(35)+b'\1')
 return rec('TES3',sub('HEDR',header)+sub('GMDT',game))+rec('CELL',cell)
(OUT/'synthetic.ess').write_bytes(classic('Balmora, Guild of Mages'))
(OUT/'synthetic-ru.ess').write_bytes(classic('Балмора, Гильдия Магов','cp1251'))
print('Synthetic fixture prepared under ignored .tmp/')
