// Lore is bundled reference material. It never becomes part of player progress.
const escapeHTML=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const normalize=value=>String(value??'').normalize('NFKC').trim().replace(/\s+/g,' ').toLowerCase();

export async function loadLore(){
 const response=await fetch('./lore.json');
 if(!response.ok)throw Error('Не удалось загрузить справочник лора.');
 const data=await response.json();
 if(data.schema!==1||!Array.isArray(data.entries)||!Array.isArray(data.contexts)||!data.sources)throw Error('Неподдерживаемый справочник лора.');
 return data;
}

export function resolveLore(location,data){
 if(!data)return null;
 const name=normalize(location.en),game=location.game;
 let best=null;
 for(const entry of data.entries){
  if(entry.game!==game)continue;
  for(const match of entry.matches){
   const root=normalize(match),exact=name===root;
   // Only explicit complex boundaries inherit history; never a fuzzy name match.
   if((exact||name.startsWith(root+',')||name.startsWith(root+':'))&&(!best||root.length>best.length))best={entry,scope:exact?'place':'complex',missing:false,length:root.length};
  }
 }
 if(best)return best;
 let key=game==='Tamriel Rebuilt'?'tamriel-rebuilt':game==='Bloodmoon'?'solstheim':game==='Tribunal'?'mournhold':'vvardenfell',scope='world';
 if(game==='Morrowind'){
  if(/\bancestral tomb$/.test(name)){key='ancestral-tomb';scope='tradition'}
  else if(/\begg mine(?:,|:|$)/.test(name)){key='egg-mine';scope='tradition'}
  else if(/\byurt$/.test(name)){key='ashlanders';scope='tradition'}
 }
 const entry=data.contexts.find(entry=>entry.key===key);
 return entry?{entry,scope,missing:true}:null;
}

function safeSource(source){
 try{const url=new URL(source.url);return url.protocol==='https:'&&((url.hostname==='en.uesp.net'&&url.pathname.startsWith('/wiki/'))||url.hostname==='www.tamriel-rebuilt.org')?source:null}catch{return null}
}

export function renderLore(location,data){
 const result=resolveLore(location,data);
 if(!result)return '<section class="lore-section"><h4>История и лор</h4><p class="lore-meta">Справочник лора недоступен. Отметки и заметки работают как обычно.</p></section>';
 const {entry,scope,missing}=result;
 const label=scope==='place'?'Об этом месте':scope==='complex'?`Контекст города или комплекса: ${entry.title}`:scope==='tradition'?`Контекст традиции: ${entry.title}`:`Общий контекст: ${entry.title}`;
 const sources=entry.sources.map(key=>data.sources[key]).filter(Boolean).map(safeSource).filter(Boolean);
 return `<section class="lore-section" aria-label="История и лор"><h4>История и лор</h4><p class="lore-meta">${escapeHTML(label)}</p>${missing?'<p class="lore-missing">Отдельная историческая справка об этой локации пока не добавлена.</p>':''}<p class="lore-text">${escapeHTML(entry.summary)}</p>${scope==='complex'?'<p class="lore-meta">Справка относится ко всему месту, а не отдельно к этой комнате.</p>':''}${entry.spoiler?`<details class="lore-spoilers"><summary>Сюжетные события — спойлеры</summary><p class="lore-text">${escapeHTML(entry.spoiler)}</p></details>`:''}<details class="lore-sources"><summary>Источники · ${sources.length}</summary><ul>${sources.map(source=>`<li><a href="${escapeHTML(source.url)}" target="_blank" rel="noopener noreferrer">${escapeHTML(source.title)}</a></li>`).join('')}</ul><p class="lore-meta">Краткий авторский пересказ. Ссылки открываются в интернете; текст справки доступен локально.</p></details></section>`;
}
