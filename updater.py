"""Opt-in GitHub release checks and verified Windows installer handoff."""
from dataclasses import dataclass
from pathlib import Path
import base64,hashlib,json,os,re,subprocess,sys,urllib.error,urllib.request
from urllib.parse import urlsplit

REPOSITORY='rastaskin/morrowind-3d-atlas'
API_URL=f'https://api.github.com/repos/{REPOSITORY}/releases/latest'
MAX_INSTALLER_SIZE=256*1024*1024
ALLOWED_HOSTS={'api.github.com','github.com','release-assets.githubusercontent.com','objects.githubusercontent.com'}

class UpdateError(Exception):pass

@dataclass(frozen=True)
class Release:
 version:str
 filename:str
 url:str
 size:int
 sha256:str
 api_url:str=''

def version_tuple(value):
 match=re.fullmatch(r'v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)',value or '')
 if not match:raise UpdateError('Сервер вернул неподдерживаемый номер версии.')
 return tuple(int(part) for part in match.groups())

def trusted_url(url):
 try:
  parsed=urlsplit(url)
  return parsed.scheme=='https' and parsed.hostname in ALLOWED_HOSTS and not parsed.username and not parsed.password and parsed.port in (None,443)
 except (ValueError,TypeError):return False

class TrustedRedirects(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,request,fp,code,message,headers,newurl):
  if not trusted_url(newurl):raise UpdateError('Обновление перенаправлено на неизвестный сервер.')
  return super().redirect_request(request,fp,code,message,headers,newurl)

def open_url(url,current_version):
 if not trusted_url(url):raise UpdateError('Недопустимый адрес обновления.')
 request=urllib.request.Request(url,headers={'User-Agent':f'Morrowind-3D-Atlas/{current_version}','Accept':'application/json' if url==API_URL else 'application/octet-stream'})
 return urllib.request.build_opener(TrustedRedirects()).open(request,timeout=25)

def release_from_metadata(data,current_version):
 if not isinstance(data,dict):raise UpdateError('Некорректный ответ сервера обновлений.')
 if data.get('draft') or data.get('prerelease'):return None
 tag=data.get('tag_name','');version=version_tuple(tag)
 if version<=version_tuple(current_version):return None
 number='.'.join(map(str,version));filename=f'Morrowind-3D-Atlas-Setup-{number}-win-x64.exe'
 assets=[asset for asset in data.get('assets',[]) if isinstance(asset,dict) and asset.get('name')==filename and asset.get('state')=='uploaded']
 if len(assets)!=1:raise UpdateError('В новом релизе пока нет готового установщика Windows.')
 asset=assets[0];url=asset.get('browser_download_url');expected=f'https://github.com/{REPOSITORY}/releases/download/{tag}/{filename}'
 if url!=expected:raise UpdateError('Адрес установщика не относится к этому проекту.')
 digest=asset.get('digest','')
 if not isinstance(digest,str) or not re.fullmatch(r'sha256:[0-9a-fA-F]{64}',digest):raise UpdateError('У установщика нет контрольной суммы SHA-256. Обновление не будет установлено.')
 size=asset.get('size')
 if type(size) is not int or not 0<size<=MAX_INSTALLER_SIZE:raise UpdateError('Недопустимый размер установщика.')
 api_url=asset.get('url','')
 if api_url and (type(asset.get('id')) is not int or asset['id']<=0 or api_url!=f"https://api.github.com/repos/{REPOSITORY}/releases/assets/{asset['id']}"):raise UpdateError('Недопустимый API-адрес установщика.')
 return Release(number,filename,url,size,digest[7:].lower(),api_url)

def check_latest(current_version):
 try:
  with open_url(API_URL,current_version) as response:
   raw=response.read(1024*1024+1)
  if len(raw)>1024*1024:raise UpdateError('Ответ сервера обновлений слишком большой.')
  return release_from_metadata(json.loads(raw),current_version)
 except UpdateError:raise
 except urllib.error.HTTPError as error:
  if error.code in (403,429):raise UpdateError('GitHub временно ограничил проверки. Попробуйте позже.') from error
  if error.code==404:raise UpdateError('На GitHub пока нет опубликованного релиза.') from error
  raise UpdateError('Сервер обновлений недоступен. Попробуйте позже.') from error
 except (OSError,ValueError) as error:raise UpdateError('Не удалось проверить обновления. Проверьте подключение к интернету.') from error

def file_digest(path):
 digest=hashlib.sha256()
 with Path(path).open('rb') as stream:
  for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
 return digest.hexdigest()

def download_release(release,cache,current_version,on_progress=lambda done,total:None,cancel=None):
 """A failed/cancelled download never becomes an executable installer."""
 version_tuple(release.version)
 expected=f'Morrowind-3D-Atlas-Setup-{release.version}-win-x64.exe'
 if release.filename!=expected or not trusted_url(release.url) or not release.url.startswith(f'https://github.com/{REPOSITORY}/releases/download/') or not re.fullmatch(r'[0-9a-f]{64}',release.sha256) or not 0<release.size<=MAX_INSTALLER_SIZE:raise UpdateError('Некорректные данные установщика.')
 if release.api_url and not re.fullmatch(re.escape(f'https://api.github.com/repos/{REPOSITORY}/releases/assets/')+r'[1-9][0-9]*',release.api_url):raise UpdateError('Недопустимый API-адрес установщика.')
 directory=Path(cache).resolve()/'updates';directory.mkdir(parents=True,exist_ok=True)
 target=directory/release.filename;partial=target.with_suffix('.exe.part')
 if target.is_file() and target.stat().st_size==release.size and file_digest(target)==release.sha256:
  on_progress(release.size,release.size);return target
 try:
  count=0;digest=hashlib.sha256()
  with open_url(release.api_url or release.url,current_version) as response,partial.open('wb') as stream:
   while True:
    if cancel is not None and cancel.is_set():raise UpdateError('Загрузка обновления отменена.')
    chunk=response.read(256*1024)
    if not chunk:break
    count+=len(chunk)
    if count>release.size:raise UpdateError('Размер загруженного файла не совпадает с релизом.')
    stream.write(chunk);digest.update(chunk);on_progress(count,release.size)
  if count!=release.size or digest.hexdigest()!=release.sha256:raise UpdateError('Проверка SHA-256 или размера не пройдена. Установщик не запущен.')
  if cancel is not None and cancel.is_set():raise UpdateError('Загрузка обновления отменена.')
  partial.replace(target)
  return target
 except UpdateError:raise
 except OSError as error:raise UpdateError('Не удалось скачать обновление. Проверьте интернет и свободное место.') from error
 finally:
  if partial.exists():partial.unlink()

# This helper runs outside the app process, waits for its exit, installs, and
# reopens the same executable. Arguments are data in base64 JSON, never PS code.
HASH_SCRIPT=r'''
function Get-AtlasFileHash([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
    finally { $stream.Dispose(); $algorithm.Dispose() }
}
'''
INSTALL_SCRIPT=HASH_SCRIPT+r'''
$ErrorActionPreference = 'Stop'
try {
    $parent = Get-Process -Id $update.parentPid -ErrorAction SilentlyContinue
    if ($parent -and -not $parent.WaitForExit(120000)) { throw 'Приложение не закрылось. Установка отменена.' }
    if ((Get-AtlasFileHash $update.installer) -ne $update.sha256) { throw 'Контрольная сумма установщика изменилась. Установка отменена.' }
    $arguments = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/SP-', '/NORESTART', '/RESTARTEXITCODE=3010', ('/DIR="' + $update.directory + '"'), ('/LOG="' + $update.log + '"'))
    $installer = Start-Process -FilePath $update.installer -ArgumentList $arguments -WindowStyle Hidden -PassThru -Wait
    if ($installer.ExitCode -ne 0) { throw ('Установщик завершился с кодом ' + $installer.ExitCode + '. Установка не завершена; попробуйте обновить ещё раз.') }
    $result = @{ok=$true;version=$update.version}
} catch {
    $result = @{ok=$false;error=$_.Exception.Message}
}
$temporary = $update.result + '.tmp'
$result | ConvertTo-Json | Set-Content -LiteralPath $temporary -Encoding UTF8
Move-Item -LiteralPath $temporary -Destination $update.result -Force
if (Test-Path -LiteralPath $update.executable -PathType Leaf) {
    Start-Process -FilePath $update.executable -ArgumentList '--auto-open'
}
'''

def helper_script(payload):
 encoded=base64.b64encode(json.dumps(payload,ensure_ascii=False).encode('utf8')).decode('ascii')
 return "$update = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+encoded+"')) | ConvertFrom-Json\n"+INSTALL_SCRIPT

def _spawn_helper(script,directory):
 # Windows PowerShell silently skips EncodedCommand with DETACHED_PROCESS.
 # CREATE_NO_WINDOW hides the helper while allowing its command to execute.
 encoded=base64.b64encode(script.encode('utf-16-le')).decode('ascii')
 powershell=Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
 if not powershell.is_file():raise UpdateError('Не найден Windows PowerShell для установки обновления.')
 with (Path(directory)/'helper.log').open('wb') as log:
  return subprocess.Popen([str(powershell),'-NoProfile','-NonInteractive','-WindowStyle','Hidden','-EncodedCommand',encoded],cwd=directory,creationflags=subprocess.CREATE_NO_WINDOW,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)

def install_release(installer,release,cache,executable=None,parent_pid=None):
 if sys.platform!='win32':raise UpdateError('Автоматическая установка доступна в Windows.')
 if executable is None and not getattr(sys,'frozen',False):raise UpdateError('Обновление устанавливается из EXE-версии приложения.')
 executable=Path(executable or sys.executable).resolve();directory=executable.parent
 update_root=Path(cache).resolve()/'updates';installer=Path(installer).resolve()
 if executable.name!='MorrowindAtlas.exe' or installer.parent!=update_root or installer.name!=release.filename or not installer.is_file() or installer.stat().st_size!=release.size or file_digest(installer)!=release.sha256:raise UpdateError('Не удалось подтвердить файл обновления.')
 payload={'parentPid':parent_pid or os.getpid(),'installer':str(installer),'sha256':release.sha256,'directory':str(directory),'executable':str(executable),'version':release.version,'log':str(update_root/'install.log'),'result':str(update_root/'result.json')}
 try:
  return _spawn_helper(helper_script(payload),update_root)
 except OSError as error:raise UpdateError('Не удалось запустить установщик. Программа остаётся открытой.') from error
