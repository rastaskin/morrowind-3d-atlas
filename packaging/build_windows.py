"""Reproducible Windows packaging. Never includes generated game assets."""
from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess,sys
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]
def make_icon():
 image=Image.new('RGBA',(256,256),(14,15,13,255));draw=ImageDraw.Draw(image)
 draw.rectangle((9,9,247,247),outline='#b69b68',width=5);draw.ellipse((35,35,221,221),outline='#cbb58b',width=5)
 draw.polygon([(128,31),(153,111),(128,128),(103,111)],fill='#f1d7a1');draw.polygon([(128,225),(103,145),(128,128),(153,145)],fill='#8c7753')
 draw.polygon([(31,128),(111,103),(128,128),(111,153)],fill='#9c8963');draw.polygon([(225,128),(145,153),(128,128),(145,103)],fill='#cbb58b');draw.ellipse((118,118,138,138),fill='#e1c38a')
 image.save(ROOT/'packaging/atlas.ico',sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
def main():
 p=argparse.ArgumentParser();p.add_argument('--iscc',type=Path);p.add_argument('--skip-installer',action='store_true');args=p.parse_args();make_icon()
 subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--distpath',str(ROOT/'dist'),'--workpath',str(ROOT/'build'),str(ROOT/'packaging/MorrowindAtlas.spec')],cwd=ROOT,check=True)
 if args.skip_installer:return
 candidates=[args.iscc,Path(os.environ.get('LOCALAPPDATA',''))/'Programs/Inno Setup 6/ISCC.exe',Path(os.environ.get('ProgramFiles(x86)','C:/Program Files (x86)'))/'Inno Setup 6/ISCC.exe']
 compiler=next((x for x in candidates if x and x.is_file()),None)
 if not compiler:raise SystemExit('Inno Setup 6 compiler not found. Supply --iscc or install JRSoftware.InnoSetup.')
 subprocess.run([str(compiler),str(ROOT/'packaging/installer.iss')],cwd=ROOT,check=True)
 installer=ROOT/'release/Morrowind-3D-Atlas-Setup-1.3.1-win-x64.exe';digest=hashlib.sha256(installer.read_bytes()).hexdigest()
 (ROOT/'release/SHA256SUMS.txt').write_text(digest+'  '+installer.name+'\n',encoding='ascii')
 print(json.dumps({'installer':installer.name,'bytes':installer.stat().st_size,'sha256':digest}))
if __name__=='__main__':main()
