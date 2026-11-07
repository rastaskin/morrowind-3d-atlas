"""Serve only public runtime files; uploads and all writes stay in the browser."""
from pathlib import Path
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from urllib.parse import unquote,urlsplit
import argparse
ROOT=Path(__file__).resolve().parent/'public'
class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*args,**kw):super().__init__(*args,directory=str(ROOT),**kw)
 def log_message(self,*args):pass
 def end_headers(self):
  self.send_header('Cache-Control','no-cache')
  self.send_header('X-Content-Type-Options','nosniff')
  self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'")
  super().end_headers()
 def do_GET(self):
  target=(ROOT/unquote(urlsplit(self.path).path).lstrip('/')).resolve()
  if not target.is_relative_to(ROOT) or target.is_dir() and target!=ROOT:return self.send_error(404)
  return super().do_GET()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8766);args=p.parse_args()
 if not (ROOT/'assets3d/world.json').exists():p.error('Run prepare.py with your game directory first.')
 print(f'Morrowind 3D Atlas: http://127.0.0.1:{args.port}',flush=True)
 ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
