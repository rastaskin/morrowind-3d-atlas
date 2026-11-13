"""Serve only public runtime files; uploads and all writes stay in the browser."""
from pathlib import Path
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from urllib.parse import unquote,urlsplit
import argparse,json
ROOT=Path(__file__).resolve().parent/'public'
GENERATED=ROOT
class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*args,**kw):super().__init__(*args,directory=str(ROOT),**kw)
 def log_message(self,*args):pass
 def translate_path(self,path):
  route=unquote(urlsplit(path).path).lstrip('/')
  base=GENERATED if route.startswith(('assets3d/','ui/')) else ROOT
  candidate=(base/(route or 'index.html')).resolve()
  if route=='assets3d/catalog.json' and not candidate.is_file():return str(ROOT/'catalog.json')
  return str(candidate) if candidate.is_relative_to(base.resolve()) else str(ROOT/'__not_found__')
 def end_headers(self):
  self.send_header('Cache-Control','no-cache')
  self.send_header('X-Content-Type-Options','nosniff')
  self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'")
  super().end_headers()
 def do_GET(self):
  route=unquote(urlsplit(self.path).path).lstrip('/')
  base=GENERATED if route.startswith(('assets3d/','ui/')) else ROOT
  target=(base/route).resolve()
  if not target.is_relative_to(base.resolve()) or target.is_dir() and target!=ROOT:return self.send_error(404)
  return super().do_GET()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8766);p.add_argument('--assets-dir',type=Path);args=p.parse_args()
 config_path=ROOT.parent/'config.local.runtime.json'
 if args.assets_dir:GENERATED=args.assets_dir.resolve()
 elif config_path.is_file():GENERATED=Path(json.loads(config_path.read_text(encoding='utf8'))['assetsDir']).resolve()
 if not (GENERATED/'assets3d/world.json').exists():p.error('Run prepare.py with your game directory first.')
 print(f'Morrowind 3D Atlas: http://127.0.0.1:{args.port}',flush=True)
 ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
