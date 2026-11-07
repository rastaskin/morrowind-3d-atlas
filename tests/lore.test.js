import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {resolveLore,renderLore} from '../public/lore.js';
const lore=JSON.parse(fs.readFileSync(new URL('../public/lore.json',import.meta.url),'utf8'));
const catalog=JSON.parse(fs.readFileSync(new URL('../public/catalog.json',import.meta.url),'utf8')).locations;
const location=(en,game='Morrowind')=>({en,game});

test('rooms receive explicitly labelled complex context; names never match fuzzily',()=>{
 assert.equal(resolveLore(location('Balmora'),lore).scope,'place');
 assert.equal(resolveLore(location('Balmora, Council Club'),lore).scope,'complex');
 assert.equal(resolveLore(location('Balmora Cavern'),lore).scope,'world');
 assert.equal(resolveLore(location('Balmora','Bloodmoon'),lore).scope,'world');
 assert.match(renderLore(location('Balmora, Council Club'),lore),/не отдельно к этой комнате/);
});
test('more specific histories win over city names and support colon-separated cells',()=>{
 assert.equal(resolveLore(location('Vivec, Puzzle Canal, Level 3'),lore).entry.title,'Канал Загадок');
 assert.equal(resolveLore(location('Sadrith Mora, Wolverine Hall: Mage\'s Guild'),lore).entry.title,'Волверин Холл');
 assert.equal(resolveLore(location('Mournhold, Royal Palace: Jail','Tribunal'),lore).entry.title,'Королевский дворец Морнхолда');
 assert.equal(resolveLore(location('Old Mournhold: Residential Ruins','Tribunal'),lore).entry.title,'Старый Морнхолд');
 assert.equal(resolveLore(location('Solstheim, Castle Karstaag, Tower','Bloodmoon'),lore).entry.title,'Замок Карстааг');
});
test('uncatalogued histories are honest; tomb traditions do not invent a family biography',()=>{
 const row=location('Unknown Ancestral Tomb'),result=resolveLore(row,lore);
 assert.equal(result.scope,'tradition');assert.equal(result.missing,true);
 assert.match(renderLore(row,lore),/Отдельная историческая справка об этой локации пока не добавлена/);
 assert.equal(resolveLore(location('Random Cave'),lore).scope,'world');
});
test('spoilers are in closed native details and unavailable lore does not break cards',()=>{
 const html=renderLore(location('Dagoth Ur'),lore);
 assert.match(html,/<details class="lore-spoilers"><summary>/);
 assert.doesNotMatch(html,/<details[^>]*\bopen\b/);
 assert.match(renderLore(location('Dagoth Ur'),null),/Справочник лора недоступен/);
});
test('reference data and location progress stay untouched when resolving and rendering',()=>{
 const row={...location('Sandas Ancestral Tomb'),visited:true,cleared:false,notes:'Keep this note'};
 const before=JSON.stringify(row),reference=JSON.stringify(lore);
 renderLore(row,lore);assert.equal(JSON.stringify(row),before);assert.equal(JSON.stringify(lore),reference);
});
test('all bundled sources have verified host URLs and every entry has text and references',()=>{
 const aliases=new Set(),keys=new Set();
 for(const entry of [...lore.entries,...lore.contexts]){
  assert.ok(!keys.has(entry.key));keys.add(entry.key);
  assert.ok(entry.summary.length>80);assert.ok(entry.sources.length);
  for(const key of entry.sources){
   assert.ok(lore.sources[key]);const url=new URL(lore.sources[key].url);
   assert.equal(url.protocol,'https:');assert.equal(url.hostname,'en.uesp.net');assert.ok(url.pathname.startsWith('/wiki/'));
  }
  for(const name of entry.matches||[]){const key=entry.game+':'+name.toLowerCase();assert.ok(!aliases.has(key),key);aliases.add(key)}
 }
 for(const row of catalog)assert.ok(resolveLore(row,lore)?.entry.summary,row.en);
});
test('reference markup is escaped and unsafe external links are rejected',()=>{
 const data={entries:[{game:'Morrowind',title:'<img>',matches:['Example'],summary:'<script>alert(1)</script>',spoiler:'<b>hidden</b>',sources:['evil','safe']}],contexts:[],sources:{evil:{title:'bad',url:'javascript:alert(1)'},safe:{title:'<svg>',url:'https://en.uesp.net/wiki/Morrowind:Example'}}};
 const html=renderLore(location('Example'),data);
 assert.ok(!html.includes('<script>'));assert.ok(!html.includes('javascript:'));
 assert.ok(html.includes('&lt;script&gt;'));assert.ok(html.includes('&lt;svg&gt;'));
});
