"""Build private runtime assets from a user-supplied legal GOTY installation."""
from pathlib import Path
import argparse,os,subprocess,sys
ROOT=Path(__file__).resolve().parent
def main():
 parser=argparse.ArgumentParser(description='Prepare local Morrowind 3D map resources')
 parser.add_argument('--data-files',required=True,type=Path,help='Directory with original English GOTY ESM and BSA files')
 parser.add_argument('--font',type=Path,help=argparse.SUPPRESS) # accepted for older command lines
 parser.add_argument('--tamriel-rebuilt',action='store_true',help='Include installed Tamriel Rebuilt')
 parser.add_argument('--openmw-config',type=Path,help='Read data directories, mod encoding and TR patches from openmw.cfg')
 parser.add_argument('--data-dir',type=Path,action='append',default=[],help='Additional Tamriel_Data/TR resource directory (repeatable)')
 args=parser.parse_args();game=args.data_files.resolve()
 missing=[n+ext for n in ['Morrowind','Tribunal','Bloodmoon']for ext in ['.esm','.bsa']if not (game/(n+ext)).is_file()]
 if missing:parser.error('Missing game files: '+', '.join(missing))
 env=os.environ.copy();env['MORROWIND_DATA_DIR']=str(game);env['ATLAS_OUTPUT_DIR']=str(ROOT/'public')
 os.environ['MORROWIND_DATA_DIR']=str(game);sys.path.insert(0,str(ROOT/'scripts'))
 from atlas_profile import resolve_profile
 import json
 profile=resolve_profile(game,tamriel_rebuilt=args.tamriel_rebuilt,data_dirs=args.data_dir,openmw_config=args.openmw_config)
 profile_path=ROOT/'config.local.inputs.json';profile_path.write_text(json.dumps(profile,ensure_ascii=False),encoding='utf8');env['ATLAS_PROFILE']=str(profile_path)
 if args.font:print('Font selection is no longer needed; the bundled MysticCards font is used.')
 for script in ['build_3d.py','build_detail.py','prepare_ui.py']:
  subprocess.run([sys.executable,str(ROOT/'scripts'/script)],env=env,check=True)
 (ROOT/'config.local.runtime.json').write_text(json.dumps({'assetsDir':str(ROOT/'public')},ensure_ascii=False),encoding='utf8')
 print('Ready. Start with: python serve.py')
if __name__=='__main__':main()
