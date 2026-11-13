"""Resolve user-owned game/mod inputs without changing their configuration."""
from pathlib import Path
import json, os, re

BASE = ('Morrowind.esm', 'Tribunal.esm', 'Bloodmoon.esm')

def openmw_settings(path):
    result = {'data': [], 'content': [], 'fallback-archive': [], 'encoding': 'cp1252'}
    path = Path(path)
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        key, sep, value = line.strip().partition('=')
        if not sep or key not in result: continue
        value = value.strip().strip('"').replace('&"', '"').replace('&&', '&')
        if key == 'encoding': result[key] = value.replace('win', 'cp')
        elif key == 'data':
            directory = Path(os.path.expandvars(value))
            result[key].append(str(directory if directory.is_absolute() else path.parent / directory))
        else: result[key].append(value)
    return result

def resolve_profile(game, *, tamriel_rebuilt=False, data_dirs=(), openmw_config=None, encoding='cp1252'):
    game = Path(game).resolve()
    cfg = openmw_settings(openmw_config) if openmw_config else {}
    dirs = list(dict.fromkeys([str(game), *cfg.get('data', []), *(str(Path(p).resolve()) for p in data_dirs)]))
    def locate(name):
        for directory in reversed(dirs):
            p = Path(directory) / name
            if p.is_file(): return p.resolve()
        raise ValueError('Не найден файл: ' + name)
    # Original base files remain the authoritative base, even with a localized mod profile.
    plugins = [{'name': n, 'path': str(game/n), 'encoding': 'cp1252', 'masters': []} for n in BASE]
    for p in plugins:
        if not Path(p['path']).is_file(): raise ValueError('Не найден файл: ' + p['name'])
        from game_assets import records
        p['masters']=[v.rstrip(b'\0').decode('cp1252') for k,v in next(records(Path(p['path']),{'TES3'}))[1] if k=='MAST']
    archives = [str(game/(Path(n).stem+'.bsa')) for n in BASE]
    for p in archives:
        if not Path(p).is_file(): raise ValueError('Не найден архив: ' + Path(p).name)
    if tamriel_rebuilt:
        names = ['Tamriel_Data.esm', 'TR_Mainland.esm']
        names += [n for n in cfg.get('content', []) if n.lower().endswith(('.esm','.esp')) and (n.lower().startswith('tr_') or 'tr_patch' in n.lower()) and not any(s in n.lower() for s in ('grass','preview'))]
        codec = cfg.get('encoding', encoding)
        visiting, added = set(), {p['name'].lower() for p in plugins}
        def add(name):
            if name.lower() in added: return
            if name.lower() in visiting: raise ValueError('Цикл зависимостей плагинов: '+name)
            visiting.add(name.lower()); p = locate(name)
            from game_assets import records
            header = next(records(p, {'TES3'}))[1]
            masters = [value.rstrip(b'\0').decode('cp1252') for tag,value in header if tag=='MAST']
            for master in masters: add(master)
            plugins.append({'name': p.name, 'path': str(p), 'encoding': codec, 'masters': masters})
            added.add(name.lower()); visiting.remove(name.lower())
        for name in dict.fromkeys(names): add(name)
        # Keep the configured relative order of selected plugins and their dependencies.
        rank={name.lower():i for i,name in enumerate([*BASE,*cfg.get('content',[])])}
        selected={p['name'].lower():p for p in plugins}; ordered=[]; done=set()
        def visit(plugin):
            if plugin['name'].lower() in done:return
            for master in plugin['masters']:visit(selected[master.lower()])
            done.add(plugin['name'].lower());ordered.append(plugin)
        for plugin in sorted(plugins,key=lambda p:rank.get(p['name'].lower(),len(rank))):visit(plugin)
        plugins=ordered
        for directory in dirs:
            for p in sorted(Path(directory).glob('*.bsa')):
                with p.open('rb') as archive: signature=archive.read(4)
                # Some installations carry an empty Oblivion-format invalidation archive.
                if signature==b'\x00\x01\x00\x00' and str(p.resolve()) not in archives: archives.append(str(p.resolve()))
    return {'schema':1, 'tamrielRebuilt':tamriel_rebuilt, 'dataDirs':dirs if tamriel_rebuilt else [str(game)], 'archives':archives, 'plugins':plugins}

def current_profile():
    path = os.environ.get('ATLAS_PROFILE')
    if path: return json.loads(Path(path).read_text(encoding='utf8'))
    return resolve_profile(Path(os.environ['MORROWIND_DATA_DIR']))
