/** Read supported Morrowind saves locally. Never persist metadata or file bytes. */
const decoder=new TextDecoder('utf-8',{fatal:true});
const tag=(b,p)=>String.fromCharCode(...b.subarray(p,p+4));
function* sections(bytes,headerSize){
 const view=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);let p=0;
 while(p<bytes.length){if(bytes.length-p<headerSize)throw Error('Сохранение обрезано: неполный заголовок.');const name=tag(bytes,p),size=view.getUint32(p+4,true),end=p+headerSize+size;if(end>bytes.length)throw Error('Сохранение обрезано: неверная длина записи.');yield [name,bytes.subarray(p+headerSize,end)];p=end;}
}
function pngHeader(bytes){const sig=[137,80,78,71,13,10,26,10];if(bytes.length<33||!sig.every((v,i)=>bytes[i]===v)||tag(bytes,12)!=='IHDR')throw Error('Неизвестный формат тумана карты.');const v=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength),w=v.getUint32(16),h=v.getUint32(20);if(!w||!h||w>256||h>256)throw Error('Недопустимый размер тумана карты.');}
export async function pngHasRevealed(bytes){
 pngHeader(bytes);const bitmap=await createImageBitmap(new Blob([bytes],{type:'image/png'}));
 try{const canvas=document.createElement('canvas');canvas.width=bitmap.width;canvas.height=bitmap.height;const ctx=canvas.getContext('2d',{willReadFrequently:true});ctx.drawImage(bitmap,0,0);const rgba=ctx.getImageData(0,0,bitmap.width,bitmap.height).data;for(let i=3;i<rgba.length;i+=4)if(rgba[i]<255)return true;return false;}finally{bitmap.close();}
}
export async function parseOpenMWSave(buffer,{decodeFog=pngHasRevealed,onProgress=()=>{}}={}){
 if(buffer.byteLength>512*1024*1024)throw Error('Сохранение больше 512 МБ.');
 const bytes=new Uint8Array(buffer);if(tag(bytes,0)!=='TES3')throw Error('Это не сохранение OpenMW. Поддерживается .omwsave, формат 34.');
 let format=null,cells=0;const visited=new Set();
 for(const [type,body]of sections(bytes,16)){
  if(type==='TES3'){
   if(format!==null)throw Error('Повторный заголовок сохранения.');
   for(const [name,value]of sections(body,8))if(name==='FORM'){if(value.length!==4)throw Error('Неверный формат заголовка.');format=new DataView(value.buffer,value.byteOffset,4).getUint32(0,true);}
   if(format!==34)throw Error('Поддерживается только формат OpenMW 34. Найден: '+(format??'неизвестный')+'.');
  }else if(type==='CSTA'){
   if(format!==34)throw Error('Сначала требуется заголовок OpenMW 34.');
   let interior=null;const fog=[];
   for(const [name,value]of sections(body,8)){
    if(name==='OBJE')break;
    if(name==='NAME'&&value[0]===2)interior=decoder.decode(value.subarray(1)).replace(/\0+$/,'');
    if(name==='FTEX')fog.push(value);
   }
   if(!interior)continue;
   cells++;for(const value of fog){if(value.length<8)throw Error('Обрезанная текстура карты.');const png=value.subarray(8);pngHeader(png);if(await decodeFog(png)){visited.add(interior);break;}}
   if(cells%20===0){onProgress(cells);await new Promise(resolve=>setTimeout(resolve,0));}
  }
 }
 if(format!==34)throw Error('Заголовок OpenMW не найден.');
 return {format,interiorsChecked:cells,visited:[...visited]};
}

const legacyDecoders=[new TextDecoder('windows-1252'),new TextDecoder('windows-1251')];
function legacyNames(bytes){
 const end=bytes.indexOf(0);if(end!==-1)bytes=bytes.subarray(0,end);
 if(bytes.length>4096)throw Error('Слишком длинное название ячейки в .ess.');
 return [...new Set(legacyDecoders.map(decoder=>decoder.decode(bytes)))].filter(Boolean);
}
function classicHeader(body){
 let version=null,type=null,current=null,hasGameData=false;
 for(const [name,value]of sections(body,8)){
  if(name==='FORM')throw Error('Это сохранение OpenMW; выберите правильный обработчик.');
  if(name==='HEDR'){
   if(version!==null||value.length!==300)throw Error('Неверный заголовок классического .ess.');
   const view=new DataView(value.buffer,value.byteOffset,value.byteLength);version=view.getFloat32(0,true);type=view.getUint32(4,true);
  }
  if(name==='GMDT'){
   if(hasGameData||value.length!==124)throw Error('Неподдерживаемый блок GMDT в .ess.');
   hasGameData=true;current=value.subarray(24,88);
  }
 }
 if(type!==32||!hasGameData)throw Error('Это не классическое сохранение Morrowind .ess: ESM/ESP не поддерживаются.');
 if(![1.2,1.3].some(expected=>Math.abs(expected-version)<0.000001))throw Error('Неподдерживаемая версия классического .ess.');
 return {version:Math.abs(version-1.2)<0.000001?'1.2':'1.3',current};
}

export async function parseClassicSave(buffer,{onProgress=()=>{}}={}){
 if(buffer.byteLength>512*1024*1024)throw Error('Сохранение больше 512 МБ.');
 const bytes=new Uint8Array(buffer);let header=null,cells=0;
 const entries=new Map();
 for(const [type,body]of sections(bytes,16)){
  if(!header){if(type!=='TES3')throw Error('Это не сохранение Morrowind .ess.');header=classicHeader(body);continue;}
  if(type==='TES3')throw Error('Повторный заголовок сохранения.');
  if(type!=='CELL')continue;
  let name=null,flags=null,deleted=false,reference=false;const fog=[];
  // Reference NAME/DATA and NAM8 must never be mistaken for cell metadata.
  // Keep validating subrecord bounds after FRMR, without interpreting objects.
  for(const [sub,value]of sections(body,8)){
   if(sub==='FRMR')reference=true;
   if(reference)continue;
   if(sub==='NAME'){
    if(name!==null)throw Error('Повторное название ячейки в .ess.');name=value;
   }
   if(sub==='DATA'){
    if(flags!==null||value.length!==12)throw Error('Неверный блок CELL.DATA в .ess.');
    flags=new DataView(value.buffer,value.byteOffset,value.byteLength).getUint32(0,true);
   }
   if(sub==='DELE')deleted=true;
   if(sub==='NAM8'){
    if(value.length!==32&&value.length!==36)throw Error('Неверный размер карты тумана NAM8 в .ess.');
    fog.push(value.subarray(value.length-32));
   }
  }
  if(flags===null)throw Error('Не найден CELL.DATA в .ess.');
  if(deleted||!(flags&1)||!name?.length)continue;
  cells++;
  const current=header.current.subarray(0,header.current.indexOf(0)===-1?header.current.length:header.current.indexOf(0));
  const cellName=name.subarray(0,name.indexOf(0)===-1?name.length:name.indexOf(0));
  const isCurrent=cellName.length===current.length&&cellName.every((byte,i)=>byte===current[i]);
  // NAM8 stores a 16x16 one-bit exploration mask, optionally preceded by a tile index.
  // Merely having a CELL or a zero-filled NAM8 is not evidence of a visit.
  if(isCurrent||fog.some(mask=>mask.some(byte=>byte!==0))){
   const variants=legacyNames(name);if(variants.length)entries.set(variants.join('\0'),variants);
  }
  if(cells%20===0){onProgress(cells);await new Promise(resolve=>setTimeout(resolve,0));}
 }
 if(!header)throw Error('Пустое или неподдерживаемое сохранение.');
 return {source:'Morrowind',format:'TES3 ESS '+header.version,interiorsChecked:cells,visited:[...entries.values()].map(names=>names[0]),nameVariants:[...entries.values()]};
}

export async function parseMorrowindSave(buffer,options={}){
 if(buffer.byteLength>512*1024*1024)throw Error('Сохранение больше 512 МБ.');
 const bytes=new Uint8Array(buffer);
 if(bytes.length<4||tag(bytes,0)!=='TES3')throw Error('Поддерживаются только сохранения Morrowind .ess и OpenMW .omwsave.');
 const first=sections(bytes,16).next().value;
 if(!first||first[0]!=='TES3')throw Error('Поддерживаются только сохранения Morrowind .ess и OpenMW .omwsave.');
 const names=[...sections(first[1],8)].map(([name])=>name);
 if(names.includes('FORM'))return {...await parseOpenMWSave(buffer,options),source:'OpenMW'};
 return parseClassicSave(buffer,options);
}

/** Exact, case-insensitive matching only; ambiguous translations/codepages are skipped. */
export function matchVisitedLocations(report,catalog){
 const byName=new Map();
 for(const row of catalog){
  if(row.kind!=='Интерьер')continue;
  for(const name of [row.en,row.name,...(row.aliases??[])]){
   if(!name)continue;const key=name.toLowerCase();if(!byName.has(key))byName.set(key,new Set());byName.get(key).add(row.id);
  }
 }
 const ids=new Set();let skipped=0,matched=0;
 for(const variants of report.nameVariants??report.visited.map(name=>[name])){
  const matches=new Set();for(const name of variants)for(const id of byName.get(name.toLowerCase())??[])matches.add(id);
  if(matches.size!==1){skipped++;continue;}
  ids.add([...matches][0]);matched++;
 }
 return {ids:[...ids],matched,skipped};
}
