"""Merge TES3 world records in master-aware load order and build local TR markers."""
import collections, hashlib, json, math, struct
from pathlib import Path
from game_assets import records

def read_world(profile, terrain_only=False):
    definitions, cells, refs, lands, palettes = {}, {}, {}, {}, {}
    translations = {}
    for plugin in profile['plugins']:
        name = plugin['name']; codec = plugin['encoding']
        decode = lambda value: value.rstrip(b'\0').decode(codec)
        table = Path(plugin['path']).with_suffix('.cel')
        if table.is_file():
            for line in table.read_text(encoding='cp1251').splitlines():
                pair=line.split('\t',1)
                if len(pair)==2: translations[pair[0]]=pair[1]
        palette={}
        types={'LAND','LTEX'} if terrain_only else {'STAT','DOOR','ACTI','CONT','CELL','LAND','LTEX'}
        for typ, pairs in records(Path(plugin['path']), types):
            if typ in {'STAT','DOOR','ACTI','CONT'}:
                d=dict(pairs); key=decode(d['NAME']).casefold()
                if 'DELE' in d: definitions.pop(key,None)
                elif 'MODL' in d: definitions[key]=decode(d['MODL'])
            elif typ=='LTEX':
                d=dict(pairs); palette[struct.unpack('<I',d['INTV'])[0]+1]=decode(d['DATA'])
            elif typ=='LAND':
                d=dict(pairs); xy=struct.unpack('<ii',d['INTV'])
                if 'DELE' in d: lands.pop(xy,None); continue
                old=lands.get(xy,({},name))
                lands[xy]=({**old[0],**d},name if 'VTEX' in d else old[1])
            else:
                head={}; parts=[]; ref=None
                for tag,value in pairs:
                    if tag=='FRMR':
                        if ref: parts.append(ref)
                        raw=struct.unpack('<I',value)[0]; index=raw>>24
                        masters=plugin['masters']
                        if index>len(masters): raise ValueError('Invalid master reference in '+name)
                        owner=masters[index-1] if index else name
                        ref={'key':(owner.lower(),raw&0xffffff)}
                    elif ref is None: head[tag]=value
                    elif tag in {'NAME','DATA','XSCL','DODT','DNAM','DELE'}: ref[tag]=value
                if ref: parts.append(ref)
                flags,x,y=struct.unpack('<Iii',head['DATA']); interior=bool(flags&1); cellname=decode(head.get('NAME',b''))
                key=('i',cellname.casefold()) if interior else ('e',x,y)
                old=cells.get(key,{})
                if 'DELE' in head:
                    cells.pop(key,None)
                    for r in parts: refs.pop(r['key'],None)
                    continue
                cells[key]={**old,'name':cellname or old.get('name',''),'interior':interior,'grid':[x,y], 'source':old.get('source',name)}
                for ref in parts:
                    refkey=ref.pop('key')
                    if 'DELE' in ref: refs.pop(refkey,None); continue
                    parsed={'cell':key}
                    for tag in ['NAME','DNAM']:
                        if tag in ref: parsed[tag]=decode(ref[tag])
                    for tag in ['DATA','XSCL','DODT']:
                        if tag in ref: parsed[tag]=ref[tag]
                    refs[refkey]={**refs.get(refkey,{}),**parsed}
        # Master indices for landscape materials are local to each plugin.
        inherited={}
        for master in plugin['masters']: inherited.update(palettes.get(master,{}))
        palettes[name]={**inherited,**palette}
    lands={xy:item for xy,item in lands.items() if 'VHGT' in item[0]}
    return {'definitions':definitions,'cells':cells,'refs':refs,'lands':lands,'palettes':palettes,'translations':translations}

def build_catalog(world, base):
    rows=[dict(row) for row in base['locations']]; cells=world['cells']; adjacency=collections.defaultdict(set); positions={}; queue=collections.deque(); exterior_entries=collections.defaultdict(list)
    translations=world['translations']; reverse=collections.defaultdict(set)
    for en,ru in translations.items(): reverse[ru.casefold()].add(en)
    def labels(raw):
        originals=reverse.get(raw.casefold(),set())
        en=next(iter(originals)) if len(originals)==1 else raw
        return en,translations.get(en,raw)
    for ref in world['refs'].values():
        if 'DODT' not in ref or ref['cell'] not in cells: continue
        origin=ref['cell']; destination=('i',ref.get('DNAM','').casefold())
        if not destination[1]:
            if cells[origin]['interior']:
                x,y=struct.unpack('<6f',ref['DODT'])[:2]; positions.setdefault(origin,[x/8192,y/8192])
            continue
        if destination not in cells: continue
        if cells[origin]['interior']:
            adjacency[origin].add(destination); adjacency[destination].add(origin)
        elif 'DATA' in ref:
            x,y=struct.unpack('<6f',ref['DATA'])[:2]; positions.setdefault(destination,[x/8192,y/8192])
            exterior_entries[cells[origin]['name'].casefold()].append([x/8192,y/8192])
    queue.extend(positions)
    while queue:
        key=queue.popleft()
        for other in sorted(adjacency[key]):
            if other not in positions: positions[other]=positions[key];queue.append(other)
    existing={label.casefold() for row in rows for label in [row['en'],row['name']]}
    grouped={}
    for key,cell in cells.items():
        raw=cell['name']
        if not raw or not cell['source'].lower().startswith('tr_'): continue
        en,ru=labels(raw)
        if en.casefold() in existing or ru.casefold() in existing: continue
        identity=('i' if cell['interior'] else 'e',en.casefold())
        if identity in grouped: continue
        entrances=exterior_entries.get(raw.casefold(),[]) if not cell['interior'] else []
        if entrances:
            center=[sum(p[i] for p in entrances)/len(entrances) for i in (0,1)]
            position=min(entrances,key=lambda p:math.dist(p,center))
        else:position=positions.get(key) if cell['interior'] else [cell['grid'][0]+.5,cell['grid'][1]+.5]
        grouped[identity]={'id':'loc-'+hashlib.sha256(('Tamriel Rebuilt\0'+identity[0]+'\0'+en.casefold()).encode()).hexdigest()[:16],
            'name':ru,'en':en,'game':'Tamriel Rebuilt','kind':'Интерьер' if cell['interior'] else 'На открытом воздухе',
            'position':position,'positionNote':'Вход из игровых файлов TR' if position and cell['interior'] else 'Поселение по входам в здания TR' if entrances else 'Центр внешней ячейки TR' if position else 'Подтверждённый внешний вход не найден','entry':'',
            'aliases':list(dict.fromkeys([raw,en,ru]))}
    rows.extend(grouped.values())
    points=[r['position'] for r in rows if r['position']]
    return {'locations':rows,'bounds':[math.floor(min(p[0] for p in points)),math.floor(min(p[1] for p in points)),math.ceil(max(p[0] for p in points)),math.ceil(max(p[1] for p in points))]}
