/** Read OpenMW format 34 locally. No names, save metadata or file bytes persist. */
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
