const KEY='morrowind-atlas-progress-v1';
const ID=/^loc-[0-9a-f]{16}$/;
export function validateProgress(input){
 if(!input||input.version!==1||!input.locations||typeof input.locations!=='object'||Array.isArray(input.locations))throw Error('Неверный формат файла прогресса.');
 const result={};
 for(const [id,p] of Object.entries(input.locations)){
  if(!ID.test(id)||!p||typeof p!=='object'||Array.isArray(p))throw Error('Неверная запись прогресса.');
  const out={};for(const [key,value] of Object.entries(p)){
   if(key==='notes'){if(typeof value!=='string'||value.length>10000)throw Error('Заметка должна содержать не более 10 000 символов.');}
   else if(!['visited','cleared'].includes(key)||typeof value!=='boolean')throw Error('Неверное свойство прогресса.');
   out[key]=value;
  }result[id]=out;
 }return result;
}
export class ProgressStore{
 constructor(storage){this.storage=storage;this.records={};try{const saved=storage.getItem(KEY);if(saved)this.records=validateProgress(JSON.parse(saved));}catch{this.loadWarning='Сохранённый прогресс недоступен или повреждён. Попробуйте импортировать резервную копию.';}}
 bindCatalog(locations){this.known=new Set(locations.map(r=>r.id));}
 commit(next){this.storage.setItem(KEY,JSON.stringify({version:1,locations:next}));this.records=next;}
 edit(id,patch){if(!this.known?.has(id))throw Error('Неизвестная локация.');const checked=validateProgress({version:1,locations:{[id]:patch}});this.commit({...this.records,[id]:{...this.records[id],...checked[id]}});}
 import(input){const checked=validateProgress(input),next={...this.records};let count=0;for(const [id,patch]of Object.entries(checked)){if(!this.known?.has(id))continue;next[id]={...next[id],...patch};count++;}this.commit(next);return count;}
 markVisited(ids){const next={...this.records};let count=0;for(const id of ids){if(!this.known?.has(id))continue;if(!next[id]?.visited)count++;next[id]={...next[id],visited:true};}this.commit(next);return count;}
 apply(locations){return locations.map(r=>({...r,visited:false,cleared:false,notes:'',...this.records[r.id]}));}
 export(){return {version:1,locations:structuredClone(this.records)};}
 clear(){this.storage.removeItem(KEY);this.records={};}
}
