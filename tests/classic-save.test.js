import test from 'node:test';
import assert from 'node:assert/strict';
import {parseClassicSave,parseMorrowindSave,matchVisitedLocations} from '../public/save-parser.js';
const u32=n=>{const b=Buffer.alloc(4);b.writeUInt32LE(n);return b};
const sub=(name,b)=>Buffer.concat([Buffer.from(name),u32(b.length),b]);
const rec=(name,b)=>Buffer.concat([Buffer.from(name),u32(b.length),Buffer.alloc(8),b]);
const buf=(...parts)=>{const b=Buffer.concat(parts);return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength)};
const text=s=>Buffer.isBuffer(s)?s:Buffer.from(s);
function header({version=1.3,type=32,current='',gameSize=124}={}){
 const h=Buffer.alloc(300);h.writeFloatLE(version);h.writeUInt32LE(type,4);
 const g=Buffer.alloc(gameSize);text(current).copy(g,24,0,64);
 return rec('TES3',Buffer.concat([sub('HEDR',h),sub('GMDT',g)]));
}
function cell(name,{interior=true,fog=[],deleted=false,tail=[]}={}){
 const data=Buffer.alloc(12);data.writeUInt32LE(interior?1:0);
 return rec('CELL',Buffer.concat([sub('NAME',Buffer.concat([text(name),Buffer.from([0])])),sub('DATA',data),...fog.map(v=>sub('NAM8',v)),...(deleted?[sub('DELE',u32(0))]:[]),...tail]));
}
function mask(bits=true,prefix=true){const b=Buffer.alloc(prefix?36:32);if(prefix)b.writeUInt32LE(1234);if(bits)b[b.length-1]=1;return b}
const catalog=[{id:'one',en:'Balmora, Guild of Mages',name:'Балмора, Гильдия Магов',kind:'Интерьер'},{id:'outside',en:'Balmora',name:'Балмора',kind:'На открытом воздухе'}];
const cp1251=s=>Buffer.from([...s].map(c=>{const n=c.codePointAt(0);return c==='ё'?0xb8:c==='Ё'?0xa8:n>=0x410&&n<=0x44f?n-0x350:n}));

test('classic ESS counts revealed interiors, not loaded cells, tile indices or exterior neighbours',async()=>{
 const report=await parseMorrowindSave(buf(header(),cell('Visited',{fog:[mask()]}),cell('Loaded only'),cell('Empty fog',{fog:[mask(false)]}),cell('Outside',{interior:false,fog:[mask()]}),cell('Deleted',{deleted:true,fog:[mask()]})));
 assert.equal(report.source,'Morrowind');assert.equal(report.format,'TES3 ESS 1.3');assert.deepEqual(report.visited,['Visited']);assert.equal(report.interiorsChecked,3);
});
test('current interior is explicit evidence, current exterior is excluded',async()=>{
 let report=await parseClassicSave(buf(header({current:'Current'}),cell('Current')));assert.deepEqual(report.visited,['Current']);
 report=await parseClassicSave(buf(header({current:'Outside'}),cell('Outside',{interior:false,fog:[mask()]})));assert.deepEqual(report.visited,[]);
});
test('supports 32/36-byte masks and multiple interior tiles, with no duplicate visits',async()=>{
 const report=await parseClassicSave(buf(header({version:1.2}),cell('One',{fog:[mask(false),mask(true,false)]}),cell('One',{fog:[mask()]})));
 assert.equal(report.format,'TES3 ESS 1.2');assert.deepEqual(report.visited,['One']);
});
test('reference metadata cannot spoof a visit or overwrite the cell name and flags',async()=>{
 const objects=[sub('FRMR',u32(7)),sub('NAME',Buffer.from('Balmora, Guild of Mages')),sub('DATA',Buffer.alloc(24)),sub('NAM8',mask())];
 const report=await parseClassicSave(buf(header(),cell('Loaded only',{tail:objects}),cell('True name',{fog:[mask()],tail:objects})));
 assert.deepEqual(report.visited,['True name']);
});
test('recognizes localized CP1251 names by exact catalog names without translation guessing',async()=>{
 const report=await parseClassicSave(buf(header(),cell(cp1251('Балмора, Гильдия Магов'),{fog:[mask()]})));
 assert.equal(report.nameVariants[0].length,2);assert.deepEqual(matchVisitedLocations(report,catalog),{ids:['one'],matched:1,skipped:0});
});
test('matching deduplicates aliases and skips ambiguous, unknown and exterior-only names',()=>{
 const report={source:'Morrowind',nameVariants:[['Balmora, Guild of Mages','Балмора, Гильдия Магов'],['Balmora'],['Unknown'],['Balmora, Guild of Mages','Other']]};
 const rows=[...catalog,{id:'other',en:'Other',name:'Другое',kind:'Интерьер'}];
 assert.deepEqual(matchVisitedLocations(report,rows),{ids:['one'],matched:1,skipped:3});
 const duplicate=[...catalog,{...catalog[0],id:'duplicate'}];assert.equal(matchVisitedLocations({visited:['Balmora, Guild of Mages']},duplicate).skipped,1);
});
test('OpenMW detection still uses FORM and its existing format checks',async()=>{
 const input=buf(rec('TES3',sub('FORM',u32(34))));assert.equal((await parseMorrowindSave(input)).source,'OpenMW');
 await assert.rejects(parseMorrowindSave(buf(rec('TES3',sub('FORM',u32(35))))),/34/);
});
test('rejects plugins, other TES save formats and unsupported or damaged classic headers',async()=>{
 await assert.rejects(parseMorrowindSave(buf(header({type:0}))),/ESM\/ESP/);
 await assert.rejects(parseMorrowindSave(buf(Buffer.from('TES4SAVEGAME'))),/Morrowind/);
 await assert.rejects(parseClassicSave(buf(header({version:2}))),/версия/);
 await assert.rejects(parseClassicSave(buf(header({gameSize:123}))),/GMDT/);
 await assert.rejects(parseClassicSave(buf(header(),header())),/Повторный/);
});
test('rejects invalid masks, truncated later records and malformed reference subrecord lengths',async()=>{
 for(const n of [0,31,35,37])await assert.rejects(parseClassicSave(buf(header(),cell('Bad',{fog:[Buffer.alloc(n)]}))),/NAM8/);
 await assert.rejects(parseClassicSave(buf(header(),cell('Visited',{fog:[mask()]}),Buffer.from('CELL'))),/обрезано/);
 const tail=Buffer.concat([Buffer.from('NAME'),u32(9999),Buffer.alloc(1)]);
 await assert.rejects(parseClassicSave(buf(header(),cell('Visited',{fog:[mask()],tail:[sub('FRMR',u32(7)),tail]}))),/обрезано/);
});
test('parsing and matching do not mutate catalog or persist personal metadata',async()=>{
 const data=JSON.stringify(catalog);const report=await parseMorrowindSave(buf(header({current:'Balmora, Guild of Mages'}),cell('Balmora, Guild of Mages')));
 matchVisitedLocations(report,catalog);assert.equal(JSON.stringify(catalog),data);
 for(const key of ['character','playerName','level','savePath','filename','bytes'])assert.equal(report[key],undefined);
});
