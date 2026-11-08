"""Build private runtime assets from a user-supplied legal GOTY installation."""
from pathlib import Path
import argparse,os,subprocess,sys
ROOT=Path(__file__).resolve().parent
def main():
 parser=argparse.ArgumentParser(description='Prepare local Morrowind 3D map resources')
 parser.add_argument('--data-files',required=True,type=Path,help='Directory with original English GOTY ESM and BSA files')
 parser.add_argument('--font',type=Path,help=argparse.SUPPRESS) # accepted for older command lines
 args=parser.parse_args();game=args.data_files.resolve()
 missing=[n+ext for n in ['Morrowind','Tribunal','Bloodmoon']for ext in ['.esm','.bsa']if not (game/(n+ext)).is_file()]
 if missing:parser.error('Missing game files: '+', '.join(missing))
 env=os.environ.copy();env['MORROWIND_DATA_DIR']=str(game);env['ATLAS_OUTPUT_DIR']=str(ROOT/'public')
 if args.font:print('Font selection is no longer needed; the bundled MysticCards font is used.')
 for script in ['build_3d.py','build_detail.py','prepare_ui.py']:
  subprocess.run([sys.executable,str(ROOT/'scripts'/script)],env=env,check=True)
 print('Ready. Start with: python serve.py')
if __name__=='__main__':main()
