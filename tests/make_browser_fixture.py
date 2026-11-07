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
print('Synthetic fixture prepared under ignored .tmp/')
