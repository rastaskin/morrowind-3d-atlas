"""Audit exactly the source files eligible for Git publication, not ignored runtime data."""
from pathlib import Path
import subprocess,re,json,sys,os,hashlib
ROOT=Path(__file__).resolve().parents[1]
def files():
 out=subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard'],cwd=ROOT)
 return sorted({Path(s.decode('utf8')) for s in out.split(b'\0') if s})
patterns=[r'[A-Za-z]:[\\/](?:Users|Проекты)[\\/]',r'/Us[e]rs/[a-zA-Z0-9_.-]+/',r'(?:ghp|gho|github_pat)_[A-Za-z0-9_]{20,}',r'(?:app\.)?notion\.(?:so|com)/',r'collection://[0-9a-f-]{36}']
patterns += [re.escape(term) for term in os.environ.get('RELEASE_PRIVATE_TERMS','').split('|') if term]
forbidden={'.bsa','.esm','.esp','.ess','.sav','.omwsave','.nif','.dds','.tex','.ttf','.woff2'}
issues=[];listed=files()
for rel in listed:
 p=ROOT/rel
 if not p.is_file():continue
 is_bundled_font=rel.as_posix()=='public/fonts/MysticCards.ttf'
 if is_bundled_font:
  source=json.loads((ROOT/'public/fonts/source.json').read_text(encoding='utf8'))
  assert source['license']=='SIL Open Font License 1.1' and source['modified'] is False
  assert hashlib.sha256(p.read_bytes()).hexdigest()==source['sha256'],'Bundled font differs from credited upstream file'
  assert (ROOT/'public/fonts/MysticCardsFontLicense.txt').is_file()
 if (p.suffix.lower() in forbidden and not is_bundled_font) or rel.parts[:2] in [('public','assets3d'),('public','ui')]:issues.append(str(rel)+': private/generated game resource')
 if p.suffix.lower() in {'.png','.jpg','.webp'}:continue
 try:s=p.read_text(encoding='utf8')
 except UnicodeDecodeError:continue
 for pattern in patterns:
  if re.search(pattern,s,re.I):issues.append(str(rel)+': private identifier/path/token pattern')
catalog=json.loads((ROOT/'public/catalog.json').read_text(encoding='utf8'));ids=set()
for row in catalog['locations']:
 assert set(row)=={'name','en','game','kind','position','positionNote','entry','id'},'Unexpected catalog field'
 assert re.fullmatch(r'loc-[0-9a-f]{16}',row['id']) and row['id'] not in ids,'Invalid/duplicate identifier'
 ids.add(row['id'])
print(json.dumps({'publishable_files':len(listed),'catalog_rows':len(ids),'issues':issues},ensure_ascii=False,indent=2))
sys.exit(bool(issues))
