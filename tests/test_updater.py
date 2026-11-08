import base64,copy,hashlib,io,json,os,subprocess,sys,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import updater

DATA=b'MZ'+bytes(range(256))*1024
SHA=hashlib.sha256(DATA).hexdigest()
NAME='Morrowind-3D-Atlas-Setup-1.3.0-win-x64.exe'
URL=f'https://github.com/{updater.REPOSITORY}/releases/download/v1.3.0/{NAME}'

def metadata():
 return {'tag_name':'v1.3.0','draft':False,'prerelease':False,'assets':[{'name':NAME,'state':'uploaded','size':len(DATA),'digest':'sha256:'+SHA,'browser_download_url':URL}]}

class UpdaterTests(unittest.TestCase):
 def test_numeric_versions_and_no_downgrade(self):
  self.assertGreater(updater.version_tuple('1.2.10'),updater.version_tuple('v1.2.9'))
  self.assertIsNone(updater.release_from_metadata(metadata(),'1.3.0'))
  self.assertIsNone(updater.release_from_metadata(metadata(),'2.0.0'))
  self.assertEqual(updater.release_from_metadata(metadata(),'1.2.0').sha256,SHA)

 def test_drafts_and_pre_releases_are_not_offered(self):
  for field in ['draft','prerelease']:
   data=metadata();data[field]=True
   self.assertIsNone(updater.release_from_metadata(data,'1.2.0'))
  for version in ['1.3.0-beta','1.03.0','../1.3.0','1.3','version 1.3.0']:
   with self.assertRaises(updater.UpdateError):updater.version_tuple(version)

 def test_metadata_requires_exact_repo_asset_size_and_sha256(self):
  changes=[('browser_download_url',URL.replace('rastaskin','somebody')),('browser_download_url',URL.replace('https:','http:')),('digest','sha256:wrong'),('size',True),('size',0),('size',updater.MAX_INSTALLER_SIZE+1),('state','new')]
  for field,value in changes:
   data=metadata();data['assets'][0][field]=value
   with self.subTest(field=field,value=value),self.assertRaises(updater.UpdateError):updater.release_from_metadata(data,'1.2.0')
  data=metadata();data['assets']*=2
  with self.assertRaises(updater.UpdateError):updater.release_from_metadata(data,'1.2.0')

 def test_network_metadata_is_read_only_and_bounded(self):
  with patch.object(updater,'open_url',return_value=io.BytesIO(json.dumps(metadata()).encode())) as request:
   self.assertEqual(updater.check_latest('1.2.0').version,'1.3.0')
   request.assert_called_once_with(updater.API_URL,'1.2.0')
  with patch.object(updater,'open_url',return_value=io.BytesIO(b' '*1100000)):
   with self.assertRaises(updater.UpdateError):updater.check_latest('1.2.0')

 def test_redirects_never_leave_https_github_hosts(self):
  import urllib.request
  redirect=updater.TrustedRedirects();request=urllib.request.Request(URL)
  for url in ['http://github.com/file','https://evil.example/file','file:///local.exe','https://github.com.evil.example/file','https://user:password@github.com/file']:
   self.assertFalse(updater.trusted_url(url))
   with self.assertRaises(updater.UpdateError):redirect.redirect_request(request,None,302,'',{},url)

 def test_official_asset_api_works_when_browser_download_links_are_unavailable(self):
  data=metadata();asset=data['assets'][0];asset['id']=17;asset['url']=f'https://api.github.com/repos/{updater.REPOSITORY}/releases/assets/17'
  release=updater.release_from_metadata(data,'1.2.0')
  with tempfile.TemporaryDirectory() as cache,patch.object(updater,'open_url',return_value=io.BytesIO(DATA)) as request:
   self.assertEqual(updater.download_release(release,cache,'1.2.0').read_bytes(),DATA)
   request.assert_called_once_with(asset['url'],'1.2.0')
  asset['url']='https://api.github.com/repos/somebody/other/releases/assets/17'
  with self.assertRaises(updater.UpdateError):updater.release_from_metadata(data,'1.2.0')

 def test_verified_download_can_be_reused_without_a_second_download(self):
  release=updater.release_from_metadata(metadata(),'1.2.0')
  with tempfile.TemporaryDirectory() as cache:
   progress=[]
   with patch.object(updater,'open_url',return_value=io.BytesIO(DATA)):
    installer=updater.download_release(release,cache,'1.2.0',lambda done,total:progress.append((done,total)))
   self.assertEqual(installer.read_bytes(),DATA);self.assertEqual(progress[-1],(len(DATA),len(DATA)))
   with patch.object(updater,'open_url',side_effect=AssertionError('Must reuse verified file')):
    self.assertEqual(updater.download_release(release,cache,'1.2.0'),installer)

 def test_truncated_corrupt_and_oversized_downloads_never_become_installers(self):
  release=updater.release_from_metadata(metadata(),'1.2.0')
  for body in [DATA[:-1],DATA+b'X',b'X'*len(DATA)]:
   with tempfile.TemporaryDirectory() as cache,patch.object(updater,'open_url',return_value=io.BytesIO(body)):
    with self.assertRaises(updater.UpdateError):updater.download_release(release,cache,'1.2.0')
    self.assertEqual(list((Path(cache)/'updates').iterdir()),[])

 def test_cancelled_download_keeps_other_cache_data(self):
  release=updater.release_from_metadata(metadata(),'1.2.0');cancel=threading.Event();cancel.set()
  with tempfile.TemporaryDirectory() as cache:
   resource=Path(cache)/'releases'/'existing.bin';resource.parent.mkdir();resource.write_bytes(b'Keep')
   with patch.object(updater,'open_url',return_value=io.BytesIO(DATA)):
    with self.assertRaises(updater.UpdateError):updater.download_release(release,cache,'1.2.0',cancel=cancel)
   self.assertEqual(resource.read_bytes(),b'Keep');self.assertEqual(list((Path(cache)/'updates').iterdir()),[])

 def test_helper_parameters_remain_data_including_spaces_unicode_and_quotes(self):
  payload={'directory':"C:/Test Space/Имя'; Write-Output wrong",'parentPid':123}
  script=updater.helper_script(payload);encoded=script.split("FromBase64String('",1)[1].split("'",1)[0]
  self.assertEqual(json.loads(base64.b64decode(encoded)),payload)
  self.assertNotIn(payload['directory'],script)
  self.assertIn('WaitForExit(120000)',script);self.assertIn('Get-AtlasFileHash $update.installer',script)

 @unittest.skipUnless(sys.platform=='win32','Windows installation handoff')
 def test_handoff_verifies_again_and_launches_hidden_helper(self):
  release=updater.release_from_metadata(metadata(),'1.2.0')
  with tempfile.TemporaryDirectory() as cache:
   root=Path(cache);installer=root/'updates'/NAME;installer.parent.mkdir();installer.write_bytes(DATA)
   executable=root/'program'/'MorrowindAtlas.exe';executable.parent.mkdir();executable.write_bytes(b'MZ')
   with patch.object(updater.subprocess,'Popen') as launch:
    updater.install_release(installer,release,cache,executable,parent_pid=123)
    command=launch.call_args.args[0];script=base64.b64decode(command[-1]).decode('utf-16-le')
    self.assertIn('-EncodedCommand',command);self.assertIn('Hidden',command)
    self.assertNotIn('ExecutionPolicy',command);self.assertIn('WaitForExit(120000)',script)
   installer.write_bytes(b'corrupt')
   with patch.object(updater.subprocess,'Popen') as launch:
    with self.assertRaises(updater.UpdateError):updater.install_release(installer,release,cache,executable)
    launch.assert_not_called()

 @unittest.skipUnless(sys.platform=='win32','Windows PowerShell parser')
 def test_helper_is_valid_powershell_without_executing_it(self):
  encoded=base64.b64encode(updater.helper_script({'directory':'test'}).encode('utf-16-le')).decode()
  script="$tokens=$null;$errors=$null;[void][Management.Automation.Language.Parser]::ParseInput([Text.Encoding]::Unicode.GetString([Convert]::FromBase64String('"+encoded+"')),[ref]$tokens,[ref]$errors);if($errors.Count){$errors|ForEach-Object{$_.Message};exit 1}"
  powershell=Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
  result=subprocess.run([str(powershell),'-NoProfile','-NonInteractive','-Command',script],capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
  self.assertEqual(result.returncode,0,result.stdout+result.stderr)

 @unittest.skipUnless(sys.platform=='win32','Native Windows SHA-256 implementation')
 def test_native_hash_works_without_optional_powershell_modules(self):
  with tempfile.TemporaryDirectory() as directory:
   path=Path(directory)/'update.exe';path.write_bytes(DATA)
   encoded=base64.b64encode(str(path).encode('utf-16-le')).decode()
   script=updater.HASH_SCRIPT+"\nGet-AtlasFileHash ([Text.Encoding]::Unicode.GetString([Convert]::FromBase64String('"+encoded+"')))"
   command=base64.b64encode(script.encode('utf-16-le')).decode()
   powershell=Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
   result=subprocess.run([str(powershell),'-NoProfile','-NonInteractive','-EncodedCommand',command],capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
   self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stdout.strip(),SHA)

 @unittest.skipUnless(sys.platform=='win32','Real hidden Windows helper process')
 def test_hidden_helper_actually_executes_its_command(self):
  with tempfile.TemporaryDirectory() as directory:
   marker=Path(directory)/'executed.txt';encoded=base64.b64encode(str(marker).encode('utf-16-le')).decode()
   script="[IO.File]::WriteAllText([Text.Encoding]::Unicode.GetString([Convert]::FromBase64String('"+encoded+"')),'ok')"
   process=updater._spawn_helper(script,Path(directory))
   self.assertEqual(process.wait(timeout=10),0);self.assertEqual(marker.read_text(),'ok')

if __name__=='__main__':unittest.main()
