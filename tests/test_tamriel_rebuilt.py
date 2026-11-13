from pathlib import Path
import importlib.util, json, os, struct, sys, tempfile, unittest

ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault('MORROWIND_DATA_DIR',str(ROOT))
sys.path.insert(0,str(ROOT/'scripts'))
from atlas_profile import resolve_profile, openmw_settings
from world_data import read_world, build_catalog
from game_assets import Assets

def sub(tag,value):return tag.encode()+struct.pack('<I',len(value))+value
def rec(tag,pairs):
    data=b''.join(sub(*pair) for pair in pairs)
    return tag.encode()+struct.pack('<III',len(data),0,0)+data
def header(*masters):return rec('TES3',[('MAST',m.encode()+b'\0') for m in masters])
def cell(name,x=0,y=0,inside=True,refs=()):
    return rec('CELL',[('NAME',name.encode('cp1251')+b'\0'),('DATA',struct.pack('<Iii',int(inside),x,y)),*refs])
def reference(number,name,**extra):
    return [('FRMR',struct.pack('<I',number)),('NAME',name.encode()+b'\0'),('DATA',struct.pack('<6f',8192,16384,0,0,0,0)),*extra.items()]

class TamrielTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        for name in ['Morrowind','Tribunal','Bloodmoon']:
            (self.root/(name+'.esm')).write_bytes(header(*(['Morrowind.esm'] if name!='Morrowind' else [])))
            (self.root/(name+'.bsa')).write_bytes(struct.pack('<III',256,0,0))
        (self.root/'Tamriel_Data.esm').write_bytes(header('Morrowind.esm'))
        (self.root/'TR_Mainland.esm').write_bytes(header('Morrowind.esm','Tamriel_Data.esm'))
    def tearDown(self):self.temp.cleanup()
    def test_missing_tr_is_reported_without_fallback(self):
        (self.root/'Tamriel_Data.esm').unlink()
        with self.assertRaisesRegex(ValueError,'Tamriel_Data'):resolve_profile(self.root,tamriel_rebuilt=True)
        self.assertEqual(len(resolve_profile(self.root)['plugins']),3)
    def test_loose_tamriel_data_overrides_archives_and_invalidating_bsa_is_ignored(self):
        name=b'textures/test.dds\0';data=b'archive'
        (self.root/'Morrowind.bsa').write_bytes(struct.pack('<III',256,12+len(name),1)+struct.pack('<II',len(data),0)+struct.pack('<I',0)+name+bytes(8)+data)
        (self.root/'Invalidation.bsa').write_bytes(b'BSA\0'+bytes(79))
        mods=self.root/'mods';(mods/'textures').mkdir(parents=True);(mods/'textures/test.dds').write_bytes(b'Tamriel Data')
        p=resolve_profile(self.root,tamriel_rebuilt=True,data_dirs=[mods])
        self.assertFalse(any(Path(a).name=='Invalidation.bsa' for a in p['archives']))
        self.assertEqual(Assets(p).read('textures\\TEST.dds'),b'Tamriel Data')
        self.assertEqual(Assets(resolve_profile(self.root)).read('textures/test.dds'),b'archive')
    def test_config_only_includes_tr_and_required_masters_in_load_order(self):
        (self.root/'MFR.esm').write_bytes(header('Morrowind.esm'))
        (self.root/'MFR_TR_patch.esp').write_bytes(header('TR_Mainland.esm','MFR.esm'))
        cfg=self.root/'openmw.cfg';cfg.write_text('encoding=win1251\ndata="'+str(self.root)+'"\ncontent=MFR.esm\ncontent=TR_Mainland.esm\ncontent=MFR_TR_patch.esp\ncontent=TR_Mainland_Grass.esp\ncontent=Sky_Main.esm',encoding='utf8')
        p=resolve_profile(self.root,tamriel_rebuilt=True,openmw_config=cfg)
        names=[i['name'] for i in p['plugins']]
        self.assertLess(names.index('MFR.esm'),names.index('TR_Mainland.esm'))
        self.assertNotIn('Sky_Main.esm',names);self.assertNotIn('TR_Mainland_Grass.esp',names)
        self.assertEqual(p['plugins'][-1]['encoding'],'cp1251')
    def test_reference_numbers_are_scoped_to_master_and_deletions_apply(self):
        base=self.root/'Morrowind.esm';base.write_bytes(header()+cell('Base',inside=False,refs=reference(1,'base')))
        tr=self.root/'TR_Mainland.esm';tr.write_bytes(header('Morrowind.esm','Tamriel_Data.esm')+cell('Mainland',inside=False,refs=reference(1,'tr')))
        patch=self.root/'TR_Factions.esp';patch.write_bytes(header('TR_Mainland.esm')+cell('Mainland',inside=False,refs=[('FRMR',struct.pack('<I',0x01000001)),('DELE',b'\0'*4)]))
        profile=resolve_profile(self.root,tamriel_rebuilt=True)
        profile['plugins'].append({'name':patch.name,'path':str(patch),'encoding':'cp1251','masters':['TR_Mainland.esm']})
        w=read_world(profile)
        self.assertEqual(set(w['refs']),{('morrowind.esm',1)})
    def test_localized_catalog_uses_confirmed_doors_and_keeps_old_ids(self):
        tr=self.root/'TR_Mainland.esm'
        tr.write_bytes(header('Morrowind.esm','Tamriel_Data.esm')+cell('Порт',1,2,False,reference(1,'door',DNAM='Дом'.encode('cp1251')+b'\0',DODT=struct.pack('<6f',0,0,0,0,0,0)))+cell('Дом')+cell('Закрытая комната'))
        tr.with_suffix('.cel').write_text('Port\tПорт\nHouse\tДом\nHidden Room\tЗакрытая комната\n',encoding='cp1251')
        p=resolve_profile(self.root,tamriel_rebuilt=True,encoding='cp1251');w=read_world(p)
        base={'locations':[{'id':'loc-0000000000000001','name':'База','en':'Base','position':None}]}
        catalog=build_catalog(w,base);self.assertEqual(catalog['locations'][0],base['locations'][0])
        rows={r['en']:r for r in catalog['locations'][1:]}
        self.assertEqual(rows['House']['position'],[1,2]);self.assertEqual(rows['House']['name'],'Дом')
        self.assertEqual(rows['Port']['position'],[1,2])
        self.assertIsNone(rows['Hidden Room']['position'])
        self.assertIn('Дом',rows['House']['aliases'])
        self.assertEqual(build_catalog(w,base)['locations'],catalog['locations'])
    def test_partial_land_override_keeps_height_and_master_texture_palette(self):
        base=self.root/'Morrowind.esm';xy=struct.pack('<ii',1,2)
        base.write_bytes(header()+rec('LTEX',[('INTV',struct.pack('<I',0)),('DATA',b'base.dds\0')])+rec('LAND',[('INTV',xy),('VHGT',b'height'),('VTEX',b'base indices')]))
        tr=self.root/'TR_Mainland.esm';tr.write_bytes(header('Morrowind.esm','Tamriel_Data.esm')+rec('LTEX',[('INTV',struct.pack('<I',1)),('DATA',b'mainland.dds\0')])+rec('LAND',[('INTV',xy),('VTEX',b'mod indices')])+rec('LAND',[('INTV',struct.pack('<ii',3,4)),('WNAM',b'ocean preview')]))
        w=read_world(resolve_profile(self.root,tamriel_rebuilt=True))
        self.assertEqual(w['lands'][(1,2)][0]['VHGT'],b'height');self.assertEqual(w['lands'][(1,2)][1],'TR_Mainland.esm')
        self.assertNotIn((3,4),w['lands'])
        self.assertEqual(w['palettes']['TR_Mainland.esm'],{1:'base.dds',2:'mainland.dds'})

if __name__=='__main__':unittest.main()
