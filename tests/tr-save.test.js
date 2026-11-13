import test from 'node:test';
import assert from 'node:assert/strict';
import {matchVisitedLocations} from '../public/save-parser.js';
import {ProgressStore} from '../public/progress.js';
test('TR names and exact localization aliases import without losing old progress',()=>{
 const old={id:'loc-0000000000000001',en:'Balmora',name:'Балмора',kind:'Интерьер'};
 const tr={id:'loc-0000000000000002',en:'Port, House',name:'Порт, Дом',aliases:['Порт, Дом'],kind:'Интерьер'};
 const catalog=[old,tr];const match=matchVisitedLocations({source:'OpenMW',visited:['Порт, Дом']},catalog);
 assert.deepEqual(match.ids,[tr.id]);
 const values=new Map();const store=new ProgressStore({getItem:k=>values.get(k),setItem:(k,v)=>values.set(k,v)});
 store.bindCatalog([old]);store.edit(old.id,{visited:true,cleared:true,notes:'Keep this'});
 store.bindCatalog(catalog);store.markVisited(match.ids);
 assert.deepEqual(store.records[old.id],{visited:true,cleared:true,notes:'Keep this'});
 assert.equal(store.records[tr.id].visited,true);
});
test('ambiguous translated TR aliases are skipped',()=>{
 const match=matchVisitedLocations({source:'OpenMW',visited:['Общее имя']},[
  {id:'loc-0000000000000001',en:'One',name:'Общее имя',kind:'Интерьер'},
  {id:'loc-0000000000000002',en:'Two',name:'Общее имя',kind:'Интерьер'},
 ]);
 assert.deepEqual(match.ids,[]);assert.equal(match.skipped,1);
});
