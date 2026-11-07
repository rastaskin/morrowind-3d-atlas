import test from 'node:test';
import assert from 'node:assert/strict';
import {parseOpenMWSave} from '../public/save-parser.js';
const u32=n=>{let b=Buffer.alloc(4);b.writeUInt32LE(n);return b};
const sub=(tag,b)=>Buffer.concat([Buffer.from(tag),u32(b.length),b]);
const record=(tag,b)=>Buffer.concat([Buffer.from(tag),u32(b.length),Buffer.alloc(8),b]);
const header=(version=34)=>record('TES3',sub('FORM',u32(version)));
const png=()=>{let b=Buffer.alloc(33);Buffer.from([137,80,78,71,13,10,26,10]).copy(b);b.write('IHDR',12);b.writeUInt32BE(32,16);b.writeUInt32BE(32,20);return b};
const cell=(name,{type=2,fog=true,opaque=false,tail=false}={})=>{
 let blocks=[sub('NAME',Buffer.concat([Buffer.from([type]),Buffer.from(name)]))];
 if(fog){let p=png();p[32]=opaque?1:0;blocks.push(sub('FTEX',Buffer.concat([Buffer.alloc(8),p])))}
 if(tail)blocks.push(sub('OBJE',Buffer.alloc(0)),Buffer.from('unparsed object payload'));
 return record('CSTA',Buffer.concat(blocks));
};
const buffer=(...parts)=>{let b=Buffer.concat(parts);return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength)};
test('only revealed named interiors count; metadata and exterior cells are excluded',async()=>{
 let calls=0;const input=buffer(header(),record('SAVE',sub('PLNA',Buffer.from('Example'))),cell('Addamasartus'),cell('Fogged',{opaque:true}),cell('Exterior',{type:6}),cell('Loaded only',{fog:false}));
 const r=await parseOpenMWSave(input,{decodeFog:async b=>{calls++;return b[32]===0}});
 assert.deepEqual(r.visited,['Addamasartus']);assert.equal(calls,2);assert.equal(r.interiorsChecked,3);assert.equal(r.character,undefined);
});
test('deduplicates interiors and stops header parsing at OBJE',async()=>{
 let r=await parseOpenMWSave(buffer(header(),cell('Test',{tail:true}),cell('Test')),{decodeFog:async()=>true});assert.deepEqual(r.visited,['Test']);
});
test('refuses unsupported versions',async()=>{await assert.rejects(parseOpenMWSave(buffer(header(35))),/34/)});
test('refuses an original ESS without OpenMW FORM',async()=>{await assert.rejects(parseOpenMWSave(buffer(record('TES3',sub('HEDR',Buffer.alloc(300))))),/34/)});
test('rejects truncated record and subrecord bounds',async()=>{
 await assert.rejects(parseOpenMWSave(buffer(header(),Buffer.from('CSTA'))),/обрезано/);
 await assert.rejects(parseOpenMWSave(buffer(header(),record('CSTA',Buffer.concat([Buffer.from('NAME'),u32(99),Buffer.from([2])])))),/обрезано/);
});
test('rejects oversized PNG before invoking native decoder',async()=>{
 let p=png();p.writeUInt32BE(100000,16);let called=false;
 await assert.rejects(parseOpenMWSave(buffer(header(),record('CSTA',Buffer.concat([sub('NAME',Buffer.from('\x02Test')),sub('FTEX',Buffer.concat([Buffer.alloc(8),p]))]))),{decodeFog:async()=>{called=true;return true}}),/размер/);assert.equal(called,false);
});
