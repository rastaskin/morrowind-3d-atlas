"""Windows desktop launcher and isolated asset worker. No external Python needed."""
from pathlib import Path
import argparse,contextlib,datetime,io,json,os,queue,runpy,subprocess,sys,threading,traceback,webbrowser
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import unquote,urlsplit
from updater import check_latest,download_release,install_release,UpdateError

VERSION='1.5.0'
ROOT=Path(__file__).resolve().parent
PUBLIC=ROOT/'bundle-public' if getattr(sys,'frozen',False) else ROOT/'public'
SCRIPTS=ROOT/'scripts'
PORT=8768

def write_json(path,data):
 path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8');temp.replace(path)

def stop_preparation(process):
 """Stop only this launcher's preparation process and its export workers."""
 if os.name=='nt':
  subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 else:process.terminate()

def worker(args):
 """Separate process: game processing never blocks the launcher UI."""
 if args.log:
  args.log.parent.mkdir(parents=True,exist_ok=True);sys.stdout=sys.stderr=args.log.open('w',encoding='utf8')
 try:
  game=args.data_files.resolve()
  missing=[name+ext for name in ['Morrowind','Tribunal','Bloodmoon']for ext in ['.esm','.bsa']if not (game/(name+ext)).is_file()]
  if missing:raise ValueError('Не найдены файлы GOTY: '+', '.join(missing))
  os.environ['MORROWIND_DATA_DIR']=str(game);os.environ['ATLAS_OUTPUT_DIR']=str(args.output.resolve())
  sys.path.insert(0,str(SCRIPTS))
  from atlas_profile import resolve_profile
  profile=resolve_profile(game,tamriel_rebuilt=args.tamriel_rebuilt,data_dirs=args.data_dir,openmw_config=args.openmw_config)
  profile_path=args.output.parent/'inputs.local.json';write_json(profile_path,profile);os.environ['ATLAS_PROFILE']=str(profile_path);os.environ['ATLAS_BASE_CATALOG']=str(PUBLIC/'catalog.json')
  for name in ['build_3d.py','build_detail.py','prepare_ui.py']:runpy.run_path(str(SCRIPTS/name),run_name='__main__')
  write_json(args.output/'ready.json',{'schema':1,'appVersion':VERSION,'tamrielRebuilt':profile['tamrielRebuilt']})
  if args.report:write_json(args.report,{'ok':True,'version':VERSION})
  return 0
 except Exception as error:
  if args.report:write_json(args.report,{'ok':False,'error':str(error)})
  traceback.print_exc();return 1

def self_test(args):
 """Safe diagnostic used by packaging tests; reports contain no personal paths."""
 try:
  import time
  if not hasattr(time,'clock'):time.clock=time.perf_counter
  import numpy as np
  from PIL import Image
  from fontTools.ttLib import TTFont
  from pyffi.formats.nif import NifFormat as N
  import tkinter
  assert (PUBLIC/'index.html').is_file() and all((SCRIPTS/name).is_file() for name in ['build_3d.py','atlas_profile.py','world_data.py'])
  assert (PUBLIC/'catalog.json').is_file() and np.isfinite(np.array([1.,2.])).all()
  assert (PUBLIC/'lore.js').is_file() and (PUBLIC/'world-models.js').is_file()
  bundled_font=TTFont(PUBLIC/'fonts/MysticCards.ttf');glyphs=bundled_font.getBestCmap()
  assert all(ord(character) in glyphs for character in 'АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдеёжзийклмнопрстуфхцчшщъыьэюя')
  lore=json.loads((PUBLIC/'lore.json').read_text(encoding='utf8'));assert lore['schema']==1 and len(lore['entries'])>0
  im=Image.new('RGBA',(32,32),(0,0,0,0));buf=io.BytesIO();im.save(buf,format='PNG');assert Image.open(io.BytesIO(buf.getvalue())).size==(32,32)
  checks=['bundled UI','bundled lore','bundled Cyrillic font','numpy','Pillow PNG','fontTools','NIF schema','Tk']
  if args.data_files:
   os.environ['MORROWIND_DATA_DIR']=str(args.data_files.resolve());sys.path.insert(0,str(SCRIPTS));from game_assets import Assets
   assets=Assets();old=N.NiGeometryData.__init__
   def init(self,*a,**kw):old(self,*a,**kw);self._num_uv_sets_value_=N.ushort()
   N.NiGeometryData.__init__=init
   data=N.Data();data.read(io.BytesIO(assets.read('meshes/x/Ex_hlaalu_b_01.NIF')));assert data.roots
   checks.append('BSA and real NIF decode')
  if args.font:
   font=TTFont(args.font);font.flavor='woff2';target=io.BytesIO();font.save(target);assert target.getvalue().startswith(b'wOF2');checks.append('WOFF2 encode')
  result={'ok':True,'version':VERSION,'checks':checks}
  if args.report:write_json(args.report,result)
  return 0
 except Exception as error:
  if args.report:write_json(args.report,{'ok':False,'errorType':type(error).__name__,'error':str(error)})
  return 1

def make_handler(generated):
 class Handler(SimpleHTTPRequestHandler):
  def log_message(self,*args):pass
  def translate_path(self,path):
   route=unquote(urlsplit(path).path).lstrip('/')
   base=generated if route.startswith(('assets3d/','ui/')) else PUBLIC
   if route=='assets3d/catalog.json' and not (generated/route).is_file():return str(PUBLIC/'catalog.json')
   candidate=(base/(route or 'index.html')).resolve()
   return str(candidate) if candidate.is_relative_to(base.resolve()) else str(PUBLIC/'__not_found__')
  def do_GET(self):
   if urlsplit(self.path).path=='/_atlas_health':
    body=json.dumps({'app':'morrowind-atlas-desktop','version':VERSION}).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
   else:super().do_GET()
  def list_directory(self,path):self.send_error(404);return None
  def end_headers(self):
   self.send_header('Cache-Control','no-cache');self.send_header('X-Content-Type-Options','nosniff')
   self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'")
   super().end_headers()
 return Handler

def start_server(generated,port=PORT):
 server=ThreadingHTTPServer(('127.0.0.1',port),make_handler(generated));threading.Thread(target=server.serve_forever,daemon=True).start();return server

def launch(args):
 import tkinter as tk
 from tkinter import ttk,filedialog,messagebox
 cache=(args.cache_dir or Path(os.environ.get('LOCALAPPDATA',Path.home()/'.cache'))/'Morrowind3DAtlas').resolve();cache.mkdir(parents=True,exist_ok=True)
 config_path=cache/'config.local.json'
 try:config=json.loads(config_path.read_text(encoding='utf8'))
 except (OSError,ValueError):config={}
 root=tk.Tk();root.title('Morrowind 3D Atlas');root.geometry('740x780');root.minsize(700,750);root.configure(bg='#11100d')
 font_family='MysticCards'
 if os.name=='nt':
  import ctypes,atexit
  font_path=str(PUBLIC/'fonts/MysticCards.ttf')
  ctypes.windll.gdi32.AddFontResourceExW(font_path,0x10,0)
  atexit.register(lambda:ctypes.windll.gdi32.RemoveFontResourceExW(font_path,0x10,0))
  from fontTools.ttLib import TTFont
  with TTFont(font_path) as bundled_font:font_family=bundled_font['name'].getDebugName(1) or font_family
 root.option_add('*Font',(font_family,13))
 style=ttk.Style();style.theme_use('clam');style.configure('TFrame',background='#11100d');style.configure('TLabel',background='#11100d',foreground='#d9c49a',font=(font_family,13));style.configure('TButton',font=(font_family,13),padding=7);style.configure('TEntry',font=(font_family,13));style.configure('TCheckbutton',background='#11100d',foreground='#d9c49a',font=(font_family,13));style.configure('Title.TLabel',font=(font_family,22),foreground='#ecd6a8')
 frame=ttk.Frame(root,padding=24);frame.pack(fill='both',expand=True)
 ttk.Label(frame,text='Morrowind 3D Atlas',style='Title.TLabel').pack(anchor='w')
 ttk.Label(frame,text='Локальная карта · без аккаунтов и загрузки сохранений в сеть',wraplength=620).pack(anchor='w',pady=(5,15))
 update_row=ttk.Frame(frame);update_row.pack(fill='x',pady=(0,5))
 ttk.Label(update_row,text=f'Версия {VERSION}').pack(side='left')
 update_button=ttk.Button(update_row,text='Проверить обновления');update_button.pack(side='right')
 update_status=tk.StringVar(value='Проверка на GitHub — только по кнопке.')
 ttk.Label(frame,textvariable=update_status,wraplength=615).pack(anchor='w')
 update_bar=ttk.Progressbar(frame,mode='determinate',maximum=100);update_bar.pack(fill='x',pady=(5,12))
 sources=config.get('sources',{})
 game_var=tk.StringVar(value=sources.get('game',''));status=tk.StringVar(value='Выберите оригинальную папку Data Files из Morrowind GOTY.')
 def folder_row(title,var,command):
  ttk.Label(frame,text=title).pack(anchor='w');row=ttk.Frame(frame);row.pack(fill='x',pady=(4,10));ttk.Entry(row,textvariable=var).pack(side='left',fill='x',expand=True);ttk.Button(row,text='Выбрать…',command=command).pack(side='left',padx=(8,0))
 folder_row('Папка игры: Data Files',game_var,lambda:game_var.set(filedialog.askdirectory(title='Выберите папку Data Files') or game_var.get()))
 tr_var=tk.BooleanVar(value=sources.get('tamrielRebuilt',False));cfg_var=tk.StringVar(value=sources.get('openmwConfig',''))
 ttk.Checkbutton(frame,text='Добавить Tamriel Rebuilt',variable=tr_var).pack(anchor='w',pady=(0,8))
 folder_row('Конфигурация OpenMW: openmw.cfg (для TR из другой папки)',cfg_var,lambda:cfg_var.set(filedialog.askopenfilename(title='Выберите openmw.cfg',filetypes=[('OpenMW','*.cfg')]) or cfg_var.get()))
 ttk.Label(frame,text='TR и Tamriel_Data берутся из папки игры или каталогов OpenMW. Игровые файлы остаются без изменений.',wraplength=650).pack(anchor='w',pady=(0,8))
 ttk.Label(frame,text='Шрифт карты: MysticCards с кириллицей — встроен.',wraplength=615).pack(anchor='w',pady=(0,12))
 actions=ttk.Frame(frame);actions.pack(fill='x',pady=(0,12));events=queue.Queue();state={'server':None,'process':None,'active':None,'update_busy':False,'available_update':None};cancel_update=threading.Event()
 active=cache/'releases'/str(config.get('active',''))/'public'
 if active.resolve().is_relative_to(cache) and (active/'ready.json').is_file():state['active']=active;status.set('Ресурсы подготовлены. Можно открыть карту.')
 update_result=cache/'updates/result.json'
 if update_result.is_file():
  try:
   result=json.loads(update_result.read_text(encoding='utf-8-sig'))
   update_status.set('Обновление установлено. Ресурсы сохранены.' if result.get('ok') else 'Обновление не установлено. Можно повторить проверку.')
   if not result.get('ok'):root.after(300,lambda message=result.get('error','Ошибка установки'):messagebox.showerror('Обновление',message))
   update_result.replace(update_result.with_name('last-result.json'))
  except (OSError,ValueError):pass
 def update_action():
  if state['update_busy'] or state['process'] and state['process'].poll() is None:return
  release=state['available_update']
  if release:
   if not getattr(sys,'frozen',False):return messagebox.showinfo('Обновление','Установка по кнопке доступна в EXE-версии приложения.')
   if not messagebox.askyesno('Обновление',f'Установить версию {release.version}?\n\nПрограмма скачает {release.size/1024/1024:.1f} МБ, проверит файл и перезапустится. Подготовленные ресурсы, отметки и заметки сохранятся.'):return
  state['update_busy']=True;cancel_update.clear();update_button.state(['disabled']);prepare_button.state(['disabled']);update_bar['value']=0
  update_status.set('Скачиваю обновление…' if release else 'Проверяю последнюю версию на GitHub…')
  def work():
   try:
    if release:
     path=download_release(release,cache,VERSION,on_progress=lambda done,total:events.put(('update_progress',100*done/total)),cancel=cancel_update)
     events.put(('update_downloaded',(path,release)))
    else:events.put(('update_checked',check_latest(VERSION)))
   except Exception as error:events.put(('update_error',str(error) if isinstance(error,UpdateError) else 'Не удалось выполнить обновление. Попробуйте позже.'))
  threading.Thread(target=work,daemon=True).start()
 update_button.configure(command=update_action)
 def open_map():
  if not state['active']:return messagebox.showinfo('Первый запуск','Сначала выберите папку игры и подготовьте ресурсы.')
  try:
   if state['server'] is None:state['server']=start_server(state['active'])
   webbrowser.open(f'http://127.0.0.1:{PORT}/')
  except OSError:messagebox.showerror('Порт занят',f'Не удалось запустить карту на порту {PORT}. Закройте другую копию приложения и повторите.')
 def prepare_assets():
  if state['update_busy']:return
  if state['process'] and state['process'].poll() is None:return
  game=Path(game_var.get())
  missing=[n+e for n in ['Morrowind','Tribunal','Bloodmoon']for e in ['.esm','.bsa']if not (game/(n+e)).is_file()]
  if missing:return messagebox.showerror('Папка игры','Нужны оригинальные английские ESM/BSA GOTY:\n'+', '.join(missing))
  release=datetime.datetime.now().strftime('%Y%m%d-%H%M%S');staging=cache/'staging'/release/'public';staging.mkdir(parents=True,exist_ok=True);report=staging.parent/'result.json';log=cache/'prepare.log'
  command=[sys.executable] if getattr(sys,'frozen',False) else [sys.executable,str(Path(__file__).resolve())]
  command+=['--prepare','--data-files',str(game.resolve()),'--output',str(staging),'--report',str(report),'--log',str(log)]
  if tr_var.get():command+=['--tamriel-rebuilt']
  if cfg_var.get():command+=['--openmw-config',cfg_var.get()]
  prepared_sources={'game':str(game.resolve()),'openmwConfig':cfg_var.get(),'tamrielRebuilt':tr_var.get()}
  try:state['process']=subprocess.Popen(command,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
  except OSError as e:return messagebox.showerror('Не удалось начать',str(e))
  prepare_button.state(['disabled']);open_button.state(['disabled']);update_button.state(['disabled']);status.set('Подготовка ресурсов. Это займёт несколько минут…');bar.start()
  def watch():
   state['process'].wait()
   try:
    result=json.loads(report.read_text(encoding='utf8'))
    if state['process'].returncode or not result.get('ok'):raise RuntimeError(result.get('error','Ошибка подготовки'))
    target=cache/'releases'/release/'public';target.parent.mkdir(parents=True,exist_ok=True)
    # Both absolute directory targets must stay inside this application's cache.
    if not staging.resolve().is_relative_to(cache) or not target.resolve().is_relative_to(cache):raise RuntimeError('Неверный каталог кэша')
    staging.rename(target);write_json(config_path,{'active':release,'schema':1,'sources':prepared_sources});events.put(('ready',target))
   except Exception as error:events.put(('error',str(error)))
  threading.Thread(target=watch,daemon=True).start()
 prepare_button=ttk.Button(actions,text='Подготовить ресурсы',command=prepare_assets);prepare_button.pack(side='left')
 open_button=ttk.Button(actions,text='Открыть карту',command=open_map);open_button.pack(side='left',padx=10)
 bar=ttk.Progressbar(frame,mode='indeterminate');bar.pack(fill='x',pady=(0,12));ttk.Label(frame,textvariable=status,wraplength=615).pack(anchor='w')
 ttk.Label(frame,text='Оставьте это окно открытым, пока используете карту.\nФайлы игры не изменяются. Прогресс хранится в браузере.',wraplength=615).pack(anchor='w',pady=(15,0))
 def poll():
  try:
   while True:
    kind,value=events.get_nowait()
    if kind=='update_progress':update_bar['value']=value;update_status.set(f'Скачиваю обновление: {value:.0f}%');continue
    if kind.startswith('update_'):
     state['update_busy']=False;update_button.state(['!disabled']);prepare_button.state(['!disabled'])
     if kind=='update_checked':
      state['available_update']=value;update_button.configure(text=f'Обновить до {value.version}' if value else 'Проверить обновления')
      update_status.set(f'Доступна версия {value.version} · {value.size/1024/1024:.1f} МБ' if value else f'Установлена актуальная версия {VERSION}.')
     elif kind=='update_error':update_status.set(value);update_bar['value']=0
     elif kind=='update_downloaded':
      path,release=value
      try:install_release(path,release,cache)
      except UpdateError as error:update_status.set(str(error));continue
      if state['server']:state['server'].shutdown();state['server'].server_close();state['server']=None
      root.destroy();return
     continue
    bar.stop();prepare_button.state(['!disabled']);open_button.state(['!disabled']);update_button.state(['!disabled'])
    if kind=='ready':
     if state['server']:state['server'].shutdown();state['server'].server_close();state['server']=None
     state['active']=value;status.set('Ресурсы готовы. Нажмите «Открыть карту».')
    else:status.set('Подготовка не выполнена. Предыдущий кэш сохранён.');messagebox.showerror('Ошибка подготовки',value)
  except queue.Empty:pass
  root.after(200,poll)
 def close():
  if state['update_busy']:
   if not messagebox.askyesno('Обновление','Прервать проверку или загрузку обновления и выйти?'):return
   cancel_update.set()
  process=state['process']
  if process and process.poll() is None:
   if not messagebox.askyesno('Подготовка ресурсов','Остановить подготовку и выйти? Готовый кэш будет сохранён.'):return
   stop_preparation(process)
  if state['server']:state['server'].shutdown();state['server'].server_close()
  root.destroy()
 root.protocol('WM_DELETE_WINDOW',close);root.after(200,poll)
 if args.auto_open and state['active']:root.after(300,open_map)
 root.mainloop();return 0

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--prepare',action='store_true');parser.add_argument('--self-test',action='store_true');parser.add_argument('--serve-only',action='store_true');parser.add_argument('--auto-open',action='store_true');parser.add_argument('--data-files',type=Path);parser.add_argument('--output',type=Path);parser.add_argument('--font',type=Path);parser.add_argument('--report',type=Path);parser.add_argument('--log',type=Path);parser.add_argument('--cache-dir',type=Path);parser.add_argument('--port',type=int,default=PORT);parser.add_argument('--tamriel-rebuilt',action='store_true');parser.add_argument('--openmw-config',type=Path);parser.add_argument('--data-dir',type=Path,action='append',default=[]);parser.add_argument('--export-models',action='store_true',help=argparse.SUPPRESS);parser.add_argument('--batch',type=Path,help=argparse.SUPPRESS);args=parser.parse_args()
 if args.self_test:return self_test(args)
 if args.export_models:
  if not args.batch:parser.error('--export-models requires --batch')
  sys.path.insert(0,str(SCRIPTS));from nif_export import run_batch
  run_batch(args.batch);return 0
 if args.prepare:
  if not args.data_files or not args.output:parser.error('--prepare requires --data-files and --output')
  return worker(args)
 if args.serve_only:
  if not args.output:parser.error('--serve-only requires --output')
  server=start_server(args.output.resolve(),args.port)
  if args.report:write_json(args.report,{'ok':True,'port':args.port,'version':VERSION})
  try:threading.Event().wait()
  finally:server.shutdown();server.server_close()
 return launch(args)
if __name__=='__main__':raise SystemExit(main())
