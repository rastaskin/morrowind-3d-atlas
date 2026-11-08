import { loadLore, renderLore } from './lore.js';
import { Atlas3D } from './map3d.js';
import { ProgressStore } from './progress.js';
import { parseMorrowindSave, matchVisitedLocations } from './save-parser.js';
const demo=new URLSearchParams(location.search).has('demo');
const store=new ProgressStore(localStorage);
const $=id=>document.getElementById(id),canvas=$('map');
let lore=null;
let data,filtered=[],selected=null,limit=150,view;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function kind(r){let s=(r.en+' '+r.name).toLowerCase();if(/tomb|гробниц/.test(s))return 'tomb';if(/cave|mine|cavern|grotto|шахт|пещер/.test(s))return 'cave';if(/ruin|shrine|daedr|dwemer|святилищ|руины|двемер/.test(s))return 'ruin';if(/house|shop|guild|temple|hall|дом|гильд|лавк|храм/.test(s))return 'town';return 'other'}
function toast(s){$('toast').textContent=s;$('toast').classList.add('show');clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('toast').classList.remove('show'),4200)}
function resize(){view?.resize()}
function fit(){view?.fit()}
function zoom(f){view?.zoom(f)}
function draw(){view?.setLocations(filtered,selected,data)}
function filter(){if(!data)return;let s=$('search').value.toLowerCase().trim(),g=$('game').value,status=$('status').value,cat=$('category').value;filtered=data.locations.filter(r=>(!s||(r.name+' '+r.en).toLowerCase().includes(s))&&(!g||r.game===g)&&(!cat||kind(r)===cat)&&(!status||status==='new'&&!r.visited||status==='visited'&&r.visited||status==='cleared'&&r.cleared||status==='unmapped'&&!r.position));filtered.sort((a,b)=>a.name.localeCompare(b.name,'ru'));renderList();draw()}
function renderList(){let n=filtered.filter(r=>r.position).length;$('resultCount').textContent=`${filtered.length.toLocaleString('ru')} · на карте ${n}`;$('results').replaceChildren();for(let r of filtered.slice(0,limit)){let b=document.createElement('button');b.className='location'+(selected?.id===r.id?' active':'');b.innerHTML=`<span class="dot ${r.visited&&r.cleared?'cleared':r.visited?'visited':''}"></span><span><b>${esc(r.name)}</b><small>${esc(r.en)}</small></span>${!r.position?'<span class="nomap" title="Нет подтверждённых координат">◇</span>':''}`;b.onclick=()=>select(r,true);$('results').append(b)}if(filtered.length>limit){let b=document.createElement('button');b.className='location';b.textContent=`Показать ещё (${filtered.length-limit})`;b.onclick=()=>{limit+=150;renderList()};$('results').append(b)}if(!filtered.length)$('results').innerHTML='<div class="empty">Локации не найдены. Измените запрос или фильтры.</div>'}
function stats(){$('visited').textContent=data.locations.filter(r=>r.visited).length;$('cleared').textContent=data.locations.filter(r=>r.cleared).length;$('total').textContent=data.locations.length.toLocaleString('ru');$('progress').style.width=100*data.locations.filter(r=>r.visited).length/data.locations.length+'%';$('sync').textContent=demo?'Демонстрация · отметки вымышлены':'Прогресс хранится в этом браузере';}
function edit(r,patch){try{if(demo)throw Error('В режиме демонстрации изменения не сохраняются. Откройте карту без ?demo.');store.edit(r.id,patch);Object.assign(r,patch);stats();filter();toast('Сохранено в этом браузере.')}catch(e){toast(e.message);card(r)}}
function select(r,center=false){selected=r;if(center&&r.position)view?.focus(r);card(r);$('detail').scrollTop=0;renderList();draw()}
function card(r){let panel=$('detail');panel.hidden=false;panel.innerHTML=`<button class="close" aria-label="Закрыть карточку">×</button><div class="tag">${esc(r.game)} · ${esc(r.kind)}</div><h3>${esc(r.name)}</h3><div class="en">${esc(r.en)}</div><div class="checks"><label><input id="vcheck" type="checkbox" ${r.visited?'checked':''}>Посещено</label><label><input id="ccheck" type="checkbox" ${r.cleared?'checked':''}>Зачищено</label></div>${renderLore(r,lore)}<label for="notes">Моя заметка</label><textarea id="notes" placeholder="Что осталось найти или сделать…">${esc(r.notes)}</textarea><button class="save-note">Сохранить заметку</button><div class="position">${esc(r.positionNote)}${r.position?` · ячейка ${Math.floor(r.position[0])}, ${Math.floor(r.position[1])}`:''}</div><p class="small-note">Отметки и заметки хранятся в этом браузере. Экспортируйте прогресс для резервной копии.</p><div class="siblings" id="siblings"></div>`;panel.querySelector('.close').onclick=()=>{panel.hidden=true;selected=null;renderList();draw()};$('vcheck').onchange=e=>edit(r,{visited:e.target.checked});$('ccheck').onchange=e=>edit(r,{cleared:e.target.checked});panel.querySelector('.save-note').onclick=()=>edit(r,{notes:$('notes').value});let sibs=r.position?data.locations.filter(q=>q.id!==r.id&&q.position&&q.position[0]===r.position[0]&&q.position[1]===r.position[1]):[];if(sibs.length){let t=document.createElement('div');t.className='small-note';t.textContent=`Связанные помещения: ${sibs.length}`;$('siblings').append(t);for(let s of sibs.slice(0,40)){let b=document.createElement('button');b.textContent=(s.visited?'✓ ':'')+s.name;b.onclick=()=>select(s);$('siblings').append(b)}}}
$('zoomIn').onclick=()=>zoom(1.4);$('zoomOut').onclick=()=>zoom(1/1.4);$('fit').onclick=fit;for(let id of ['search','game','status','category'])$(id).addEventListener('input',()=>{limit=150;filter()});$('reset').onclick=()=>{for(let id of ['search','game','status','category'])$(id).value='';limit=150;filter();fit()};

let catalog=[];
function reloadProgress(){data.locations=store.apply(catalog);stats();filter();if(selected){selected=data.locations.find(r=>r.id===selected.id);if(selected)card(selected)}}
function ensureEditable(){if(demo)throw Error('В режиме демонстрации импорт и сброс отключены. Откройте карту без ?demo.');}
$('saveFile').addEventListener('change',async event=>{
 const input=event.target,file=input.files?.[0];if(!file)return;
 input.disabled=true;
 try{
  ensureEditable();if(file.size>512*1024*1024)throw Error('Сохранение больше 512 МБ.');
  $('saveInfo').textContent='Читаю сохранение локально…';
  const report=await parseMorrowindSave(await file.arrayBuffer(),{onProgress:n=>$('saveInfo').textContent=`Проверено интерьеров: ${n}`});
  const {ids,skipped}=matchVisitedLocations(report,catalog);
  const added=store.markVisited(ids);reloadProgress();
  $('saveInfo').textContent=`${report.source==='Morrowind'?'Morrowind .ess':'OpenMW .omwsave'} · Новых посещений: ${added} · найдено в каталоге: ${ids.length} · без соответствия: ${skipped}`;
  toast('Посещения импортированы. Зачистки и заметки сохранены.');
 }catch(e){$('saveInfo').textContent='Импорт не выполнен. Прогресс сохранён.';toast(e.message)}
 finally{input.disabled=false;input.value=''}
});
$('exportProgress').onclick=()=>{try{ensureEditable();const blob=new Blob([JSON.stringify(store.export(),null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download='morrowind-atlas.progress.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(e){toast(e.message)}};
$('importProgress').addEventListener('change',async event=>{const input=event.target,file=input.files?.[0];if(!file)return;try{ensureEditable();if(file.size>5*1024*1024)throw Error('Файл прогресса больше 5 МБ.');const count=store.import(JSON.parse(await file.text()));reloadProgress();toast(`Импортированы отметки для ${count} локаций.`)}catch(e){toast(e.message)}finally{input.value=''}});
$('resetProgress').onclick=()=>{try{ensureEditable();if(confirm('Удалить все отметки и заметки в этом браузере? Сначала можно экспортировать резервную копию.')){store.clear();reloadProgress();$('saveInfo').textContent='Morrowind .ess / OpenMW .omwsave · локально';toast('Прогресс очищен.')}}catch(e){toast(e.message)}};
view=new Atlas3D(canvas,{onSelect:r=>select(r),onStatus:toast});
new ResizeObserver(resize).observe($('maparea'));
(async()=>{try{const [response,loreResult]=await Promise.all([fetch('./catalog.json'),loadLore().catch(()=>null)]);lore=loreResult;if(!response.ok)throw Error('Каталог локаций недоступен.');data=await response.json();catalog=data.locations;store.bindCatalog(catalog);
 if(demo){data.locations=catalog.map((r,i)=>({...r,visited:i%4===0||i%11===0,cleared:i%11===0,notes:''}));$('demoBanner').hidden=false;$('saveInfo').textContent='Демо-прогресс · сохранение не загружено';}
 else data.locations=store.apply(catalog);
 stats();filter();resize();if(store.loadWarning&&!demo)toast(store.loadWarning);
 }catch(e){$('resultCount').textContent='Не удалось загрузить каталог';toast(e.message)}})();
window.addEventListener('storage',()=>{if(!demo)location.reload()});
