import * as THREE from 'three';
import { OrbitControls } from './vendor/OrbitControls.js';
import { hideEditorModels } from './world-models.js';
const $=id=>document.getElementById(id),UNIT=819.2;
export class Atlas3D {
 constructor(canvas,options){
  this.canvas=canvas;this.options=options;this.rows=[];this.selected=null;this.tiles=new Map();this.modelCache=new Map();this.textureCache=new Map();this.loading=new Set();this.modelQueue=[];this.tileQueue=[];this.activeLoads=0;this.quality='ultra';this.dirty=true;this.ready=false;this.start=performance.now();
  try{this.renderer=new THREE.WebGLRenderer({canvas,antialias:true,powerPreference:'high-performance'});}catch(e){$('load3d').textContent='WebGL недоступен. Откройте плоскую карту или включите аппаратное ускорение браузера.';throw e}
  this.renderer.setPixelRatio(Math.min(devicePixelRatio,2));this.renderer.setClearColor(0x152c34);this.renderer.outputColorSpace=THREE.SRGBColorSpace;this.renderer.toneMapping=THREE.ACESFilmicToneMapping;this.renderer.toneMappingExposure=1.35;this.renderer.shadowMap.enabled=true;this.renderer.shadowMap.type=THREE.PCFSoftShadowMap;
  this.scene=new THREE.Scene();this.scene.background=new THREE.Color(0x233c46);this.scene.fog=new THREE.FogExp2(0x233c46,.0011);
  this.camera=new THREE.PerspectiveCamera(43,1,.025,3500);this.camera.position.set(-35,90,130);
  this.controls=new OrbitControls(this.camera,canvas);this.controls.enableDamping=true;this.controls.dampingFactor=.09;this.controls.minDistance=.35;this.controls.maxDistance=1500;this.controls.maxPolarAngle=Math.PI*.495;this.controls.target.set(-25,0,20);this.controls.screenSpacePanning=false;this.controls.zoomToCursor=true;
  this.scene.add(new THREE.HemisphereLight(0xb8d9e5,0x3a3024,2.1));this.sun=new THREE.DirectionalLight(0xffe9ba,3.4);this.sun.position.set(-80,150,70);this.sun.castShadow=true;this.sun.shadow.mapSize.set(2048,2048);this.sun.shadow.bias=-.0003;this.sun.shadow.normalBias=.025;this.scene.add(this.sun,this.sun.target);
  this.terrainRoot=new THREE.Group();this.scene.add(this.terrainRoot);this.objectRoot=new THREE.Group();this.scene.add(this.objectRoot);this.overlayRoot=new THREE.Group();this.scene.add(this.overlayRoot);
  this.addSea();this.raycaster=new THREE.Raycaster();this.pointer=new THREE.Vector2();this.down=null;this.canvas.addEventListener('pointerdown',e=>{this.down=[e.clientX,e.clientY]});this.canvas.addEventListener('pointerup',e=>{if(this.down&&Math.hypot(e.clientX-this.down[0],e.clientY-this.down[1])<5)this.pick(e)});this.canvas.addEventListener('dblclick',e=>this.retarget(e));
  canvas.addEventListener('keydown',e=>{if(e.key==='+'||e.key==='='){e.preventDefault();this.zoom(1.4)}if(e.key==='-'){e.preventDefault();this.zoom(1/1.4)}if(e.key==='Home'){e.preventDefault();this.fit()}});
  $('quality').onchange=e=>{this.quality=e.target.value;this.renderer.setPixelRatio(Math.min(devicePixelRatio,this.quality==='low'?1:this.quality==='high'?1.5:2));this.lastObjects=null;this.dirty=true};$('objects').onchange=e=>{this.objectRoot.visible=e.target.checked;this.lastObjects=null};$('markers').onchange=e=>{this.overlayRoot.visible=e.target.checked};$('topView').onclick=()=>{let d=this.camera.position.distanceTo(this.controls.target);this.camera.position.copy(this.controls.target).add(new THREE.Vector3(0,d,.001));this.controls.update()};
  this.pointSize=8;
  try{let saved=localStorage.getItem('morrowind-atlas-marker-size');if(saved!==null&&Number.isFinite(Number(saved)))this.pointSize=Math.max(2,Math.min(24,Math.round(Number(saved))))}catch{}
  $('markerSize').value=this.pointSize;$('markerSizeValue').textContent=this.pointSize+' пкс';
  $('markerSize').addEventListener('input',e=>{this.pointSize=Number(e.target.value);$('markerSizeValue').textContent=this.pointSize+' пкс';this.applyPointSize();try{localStorage.setItem('morrowind-atlas-marker-size',String(this.pointSize))}catch{}});
  this.controls.addEventListener('change',()=>this.dirty=true);this.resize();this.loadWorld();this.animate();
 }
 addSea(){
  this.waterUniforms={time:{value:0},sunDirection:{value:new THREE.Vector3(-.5,.8,.4).normalize()}};
  this.water=new THREE.Mesh(new THREE.PlaneGeometry(2400,2400),new THREE.ShaderMaterial({
   uniforms:this.waterUniforms,transparent:false,depthWrite:true,
   vertexShader:`varying vec3 wp;
    void main(){vec4 p=modelMatrix*vec4(position,1.);wp=p.xyz;gl_Position=projectionMatrix*viewMatrix*p;}`,
   fragmentShader:`
    uniform float time;uniform vec3 sunDirection;varying vec3 wp;
    // Integrate each ripple over its pixel footprint. Unresolved waves fade
    // smoothly instead of aliasing into moving bright stripes and sparkles.
    float filteredWave(float phase){
     vec2 footprint=vec2(dFdx(phase),dFdy(phase));
     float resolved=1.-smoothstep(.15,.8,length(footprint));
     return sin(phase)*resolved;
    }
    void main(){
     vec2 p=wp.xz;
     float a=filteredWave(p.x*2.1+p.y*.85+time*.45);
     float b=filteredWave(p.y*2.8-p.x*.75-time*.32);
     vec3 n=normalize(vec3(a*.015,1.,b*.015));
     vec3 v=normalize(cameraPosition-wp);
     float fres=pow(1.-max(v.y,0.),3.);
     // Broad, subdued highlights remain stable while orbiting the camera.
     float spec=pow(max(dot(reflect(-sunDirection,n),v),0.),18.);
     vec3 col=mix(vec3(.025,.115,.14),vec3(.18,.30,.32),fres);
     col+=vec3(.85,.75,.5)*spec*.12;
     gl_FragColor=vec4(col,1.);
     #include <tonemapping_fragment>
     #include <colorspace_fragment>
    }`
  }));
  this.water.rotation.x=-Math.PI/2;this.water.position.y=-.025;this.scene.add(this.water);
 }
 async loadWorld(){try{
  let res=await fetch('./assets3d/world.json');if(!res.ok)throw Error('Данные 3D ещё не собраны');this.world=hideEditorModels(await res.json());this.detail=await fetch('./assets3d/detail.json').then(r=>r.ok?r.json():{});this.detailAtlas=await this.texture('terrain-atlas.webp');this.detailAtlas.generateMipmaps=true;
  for(let t of this.world.terrain){let tile={...t,geometry:null,mesh:null,full:false};tile.mesh=this.makeTerrain(tile,9,new Float32Array(t.h),t.c);this.terrainRoot.add(tile.mesh);this.tiles.set(t.key,tile)}
  this.instancesByCell=new Map();for(let r of this.world.instances){let key=r[8]+','+r[9];if(!this.instancesByCell.has(key))this.instancesByCell.set(key,[]);this.instancesByCell.get(key).push(r)}
  this.ready=true;$('load3d').hidden=true;this.updatePoints();this.lastObjects=null;this.dirty=true;if(this.selected?.position)this.focus(this.selected);else this.flyTo(new THREE.Vector3(-25,1.5,22),38);
 }catch(e){$('load3d').textContent=e.message;this.options.onStatus?.('Не удалось загрузить 3D: '+e.message)}}
 makeTerrain(tile,n,heights,colors=null){
  const pos=new Float32Array(n*n*3),uv=new Float32Array(n*n*2),col=new Float32Array(n*n*3),indices=[];
  for(let y=0;y<n;y++)for(let x=0;x<n;x++){let i=y*n+x;pos[i*3]=tile.x*10+x/(n-1)*10;pos[i*3+1]=heights[i];pos[i*3+2]=-tile.y*10-y/(n-1)*10;uv[i*2]=x/(n-1);uv[i*2+1]=y/(n-1);let c=colors?.[i]??[150,140,110];col[i*3]=(c[0]/255)**2.2;col[i*3+1]=(c[1]/255)**2.2;col[i*3+2]=(c[2]/255)**2.2;if(x<n-1&&y<n-1){let a=i,b=i+1,c=i+n,d=c+1;indices.push(a,b,c,b,d,c)}}
  let g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.BufferAttribute(pos,3));g.setAttribute('uv',new THREE.BufferAttribute(uv,2));g.setAttribute('color',new THREE.BufferAttribute(col,3));g.setIndex(indices);g.computeVertexNormals();g.computeBoundingSphere();let m=new THREE.MeshStandardMaterial({vertexColors:true,roughness:1,metalness:0});let mesh=new THREE.Mesh(g,m);mesh.receiveShadow=true;mesh.castShadow=false;return mesh;
 }
 async loadTile(tile){if(tile.loading||tile.full)return;tile.loading=true;try{
  let res=await fetch(`./assets3d/terrain/${tile.key}.bin`);if(!res.ok)throw Error('Tile unavailable');let h=new Float32Array(await res.arrayBuffer());if(h.length!==4225)throw Error('Invalid height tile');for(let i=0;i<h.length;i++)h[i]/=UNIT;tile.heights=h;let mesh=this.makeTerrain(tile,65,h);
  let indexMap=await new THREE.TextureLoader().loadAsync(`./assets3d/terrain/${tile.key}-index.png`),tintMap=await this.texture(`terrain/${tile.key}-tint.png`);indexMap.colorSpace=THREE.NoColorSpace;indexMap.magFilter=indexMap.minFilter=THREE.NearestFilter;indexMap.generateMipmaps=false;
  mesh.material.vertexColors=false;mesh.material.map=this.detailAtlas;mesh.material.onBeforeCompile=shader=>{
   shader.uniforms.landIndex={value:indexMap};shader.uniforms.landTint={value:tintMap};shader.uniforms.landGrid={value:this.detail.grid||16};shader.uniforms.landIndexChannels={value:this.detail.indexChannels||1};
   shader.fragmentShader='uniform sampler2D landIndex;\nuniform sampler2D landTint;\nuniform float landGrid;\nuniform float landIndexChannels;\n'+shader.fragmentShader;
   shader.fragmentShader=shader.fragmentShader.replace('#include <map_fragment>',`vec2 lp=vMapUv*16.-.5;vec2 lb=floor(lp);vec2 lf=smoothstep(0.,1.,fract(lp));vec2 lt=fract(vMapUv*16.);vec4 samples[4];for(int k=0;k<4;k++){vec2 corner=vec2(float(k-k/2*2),float(k/2));vec4 encoded=texture2D(landIndex,(clamp(lb+corner,vec2(0.),vec2(15.))+.5)/16.);float li=floor(encoded.r*255.+.5)+(landIndexChannels>1.?floor(encoded.g*255.+.5)*256.:0.);vec2 auv=(vec2(mod(li,landGrid),landGrid-1.-floor(li/landGrid))+mix(vec2(.002),vec2(.998),lt))/landGrid;samples[k]=texture2D(map,auv);}diffuseColor*=mix(mix(samples[0],samples[1],lf.x),mix(samples[2],samples[3],lf.x),lf.y)*texture2D(landTint,vMapUv);`);
  };mesh.material.customProgramCacheKey=()=> 'morrowind-land-v2';mesh.material.needsUpdate=true;tile.indexMap=indexMap;this.terrainRoot.remove(tile.mesh);tile.mesh.geometry.dispose();tile.mesh.material.dispose();tile.mesh=mesh;tile.full=true;tile.used=performance.now();this.terrainRoot.add(mesh);this.updatePoints();
 }catch(e){console.warn('Terrain:',tile.key,e.message)}finally{tile.loading=false}}
 texture(path){if(!this.textureCache.has(path)){let p=new THREE.TextureLoader().loadAsync('./assets3d/'+path).then(t=>{t.colorSpace=THREE.SRGBColorSpace;if(path.startsWith('textures/'))t.wrapS=t.wrapT=THREE.RepeatWrapping;t.anisotropy=Math.min(8,this.renderer.capabilities.getMaxAnisotropy());return t});this.textureCache.set(path,p)}return this.textureCache.get(path)}
 height(x,y){let cx=Math.floor(x),cy=Math.floor(y),t=this.tiles.get(cx+'_'+cy);if(!t)return 0;let n=t.heights?65:9,h=t.heights||t.h,fx=(x-cx)*(n-1),fy=(y-cy)*(n-1),ix=Math.min(n-2,Math.floor(fx)),iy=Math.min(n-2,Math.floor(fy)),dx=fx-ix,dy=fy-iy;return h[iy*n+ix]*(1-dx)*(1-dy)+h[iy*n+ix+1]*dx*(1-dy)+h[(iy+1)*n+ix]*(1-dx)*dy+h[(iy+1)*n+ix+1]*dx*dy}
 applyPointSize(){if(this.points)this.points.material.uniforms.size.value=this.pointSize*this.renderer.getPixelRatio()}
 setLocations(rows,selected,data){this.rows=rows;this.selected=selected;this.data=data;if(this.ready)this.updatePoints()}
 updatePoints(){if(!this.ready)return;let values=[],colors=[];this.pointRows=[];for(let r of this.rows){if(!r.position)continue;let [x,y]=r.position;values.push(x*10,Math.max(0,this.height(x,y))+.2,-y*10);let c=new THREE.Color(r.visited?(r.cleared?0x32ff48:0xffe600):0x168bff);colors.push(c.r,c.g,c.b);this.pointRows.push(r)}
  if(!this.points){let g=new THREE.BufferGeometry();let m=new THREE.ShaderMaterial({vertexColors:true,transparent:true,depthTest:false,depthWrite:false,toneMapped:false,uniforms:{size:{value:8}},vertexShader:`varying vec3 c;uniform float size;void main(){c=color;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);gl_PointSize=size;}`,fragmentShader:`varying vec3 c;void main(){float d=length(gl_PointCoord-.5);if(d>.5)discard;gl_FragColor=vec4(c,smoothstep(.5,.35,d));\n#include <tonemapping_fragment>\n#include <colorspace_fragment>}`});this.points=new THREE.Points(g,m);this.points.renderOrder=20;this.overlayRoot.add(this.points)}
  this.applyPointSize();this.points.geometry.dispose();this.points.geometry=new THREE.BufferGeometry();this.points.geometry.setAttribute('position',new THREE.Float32BufferAttribute(values,3));this.points.geometry.setAttribute('color',new THREE.Float32BufferAttribute(colors,3));this.points.geometry.computeBoundingSphere();
  if(!this.selectionRing){this.selectionRing=new THREE.Mesh(new THREE.RingGeometry(.15,.21,48),new THREE.MeshBasicMaterial({color:0xffe6a0,side:THREE.DoubleSide,depthTest:false,transparent:true}));this.selectionRing.rotation.x=-Math.PI/2;this.selectionRing.renderOrder=21;this.overlayRoot.add(this.selectionRing)}this.selectionRing.visible=!!this.selected?.position;if(this.selected?.position){let [x,y]=this.selected.position;this.selectionRing.position.set(x*10,Math.max(0,this.height(x,y))+.3,-y*10)}
 }
 resize(){let r=this.canvas.parentElement.getBoundingClientRect();if(!r.width||!r.height)return;this.renderer.setSize(r.width,r.height,false);this.camera.aspect=r.width/r.height;this.camera.updateProjectionMatrix();this.dirty=true}
 fit(){if(!this.ready)return;let box=new THREE.Box3().setFromObject(this.terrainRoot),c=box.getCenter(new THREE.Vector3()),size=box.getSize(new THREE.Vector3());let dist=Math.max(size.x/Math.max(.7,this.camera.aspect),size.z)*.85;this.flyTo(new THREE.Vector3(c.x,0,c.z),dist)}
 focus(r){if(r.position){let [x,y]=r.position;this.flyTo(new THREE.Vector3(x*10,Math.max(0,this.height(x,y))+.25,-y*10),12)}}
 flyTo(target,distance){let offset=new THREE.Vector3(-.35,.7,.8).normalize().multiplyScalar(distance);this.flight={start:performance.now(),from:this.camera.position.clone(),to:target.clone().add(offset),targetFrom:this.controls.target.clone(),targetTo:target.clone()};this.lastObjects=null;this.dirty=true}
 zoom(f){this.flight=null;this.camera.position.sub(this.controls.target).multiplyScalar(1/f).add(this.controls.target);this.controls.update();this.dirty=true}
 pointerCoords(e){let rect=this.canvas.getBoundingClientRect();return {x:e.clientX-rect.left,y:e.clientY-rect.top,w:rect.width,h:rect.height}}
 pick(e){if(!this.ready||!$('markers').checked)return;let {x,y,w,h}=this.pointerCoords(e),best=null,dist=Math.max(12,this.pointSize/2+5);this.camera.updateMatrixWorld();let p=this.points.geometry.attributes.position;for(let i=0;i<p.count;i++){let v=new THREE.Vector3().fromBufferAttribute(p,i).project(this.camera);if(v.z>1||v.z< -1)continue;let d=Math.hypot((v.x+1)*w/2-x,(1-v.y)*h/2-y);if(d<dist){dist=d;best=this.pointRows[i]}}if(best)this.options.onSelect(best)}
 retarget(e){if(!this.ready)return;let p=this.pointerCoords(e);this.pointer.set(p.x/p.w*2-1,1-p.y/p.h*2);this.raycaster.setFromCamera(this.pointer,this.camera);let hit=this.raycaster.intersectObjects(this.terrainRoot.children,false)[0];if(hit)this.flyTo(hit.point,Math.min(25,this.camera.position.distanceTo(hit.point)*.5))}
 async loadModel(key){if(this.modelCache.has(key))return this.modelCache.get(key);let p=(async()=>{let r=await fetch(`./assets3d/models/${key}.json`);if(!r.ok)throw Error('Mesh metadata missing');let d=await r.json(),binary=await(await fetch(`./assets3d/models/${key}.bin`)).arrayBuffer(),parts=[];for(let part of d.parts){let a=new Float32Array(binary,part.v,part.n*8),g=new THREE.BufferGeometry(),inter=new THREE.InterleavedBuffer(a,8);g.setAttribute('position',new THREE.InterleavedBufferAttribute(inter,3,0));g.setAttribute('normal',new THREE.InterleavedBufferAttribute(inter,3,3));g.setAttribute('uv',new THREE.InterleavedBufferAttribute(inter,2,6));g.setIndex(new THREE.BufferAttribute(new Uint32Array(binary,part.i,part.count),1));g.computeBoundingSphere();let mat=new THREE.MeshStandardMaterial({color:part.texture?0xffffff:new THREE.Color(...part.color),roughness:1,metalness:0,side:THREE.DoubleSide,alphaTest:part.alpha?.45:0});if(part.texture)mat.map=await this.texture(part.texture);parts.push({geometry:g,material:mat})}return parts})();this.modelCache.set(key,p);return p}
 refreshObjects(){if(!this.world||!$('objects').checked)return;let target=this.controls.target,d=this.camera.position.distanceTo(target),step=this.quality==='low'?15:this.quality==='high'?25:35;if(d>210){this.objectRoot.visible=false;return}this.objectRoot.visible=true;if(this.lastObjects&&this.lastObjects.distanceTo(target)<4&&!this.modelDirty)return;this.lastObjects=target.clone();this.modelDirty=false;let by=new Map(),cx=Math.floor(target.x/10),cy=Math.floor(-target.z/10),radius=Math.ceil(step/10);for(let x=cx-radius;x<=cx+radius;x++)for(let y=cy-radius;y<=cy+radius;y++)for(let r of this.instancesByCell.get(x+','+y)||[]){let key=r[0];if(!this.world.models[key]||Math.hypot(r[1]/UNIT-target.x,r[2]/UNIT+target.z)>step)continue;if(!by.has(key))by.set(key,[]);by.get(key).push(r)}let entries=[...by.entries()].sort((a,b)=>Math.min(...a[1].map(r=>Math.hypot(r[1]/UNIT-target.x,r[2]/UNIT+target.z)))-Math.min(...b[1].map(r=>Math.hypot(r[1]/UNIT-target.x,r[2]/UNIT+target.z)))).slice(0,this.quality==='ultra'?220:this.quality==='high'?120:50);for(let child of this.objectRoot.children)child.dispose();this.objectRoot.clear();let generation=(this.generation||0)+1;this.generation=generation;this.modelQueue=entries.map(([key,rs])=>async()=>{try{let parts=await this.loadModel(key);if(this.generation!==generation)return;let convert=new THREE.Matrix4().makeRotationX(-Math.PI/2);for(let part of parts){let mesh=new THREE.InstancedMesh(part.geometry,part.material,rs.length);mesh.castShadow=true;mesh.receiveShadow=true;let tmp=new THREE.Object3D(),m=new THREE.Matrix4();rs.forEach((r,i)=>{tmp.position.set(r[1]/UNIT,r[2]/UNIT,r[3]/UNIT);tmp.rotation.set(-r[4],-r[5],-r[6],'ZYX');tmp.scale.setScalar(r[7]);tmp.updateMatrix();m.multiplyMatrices(convert,tmp.matrix);mesh.setMatrixAt(i,m)});mesh.instanceMatrix.needsUpdate=true;mesh.computeBoundingSphere();this.objectRoot.add(mesh)}}catch(e){console.warn('Model:',key,e.message)}});this.pump()}
 pump(){while(this.activeLoads<5&&(this.tileQueue.length||this.modelQueue.length)){let job=this.tileQueue.shift()||this.modelQueue.shift();this.activeLoads++;job().finally(()=>{this.activeLoads--;this.pump()})}}
 updateLOD(){if(!this.ready)return;let target=this.controls.target,d=this.camera.position.distanceTo(target),threshold=this.quality==='low'?30:this.quality==='high'?65:95;this.tileQueue=[];if(d<230){let nearby=[...this.tiles.values()].filter(t=>Math.hypot(t.x*10+5-target.x,-t.y*10-5-target.z)<threshold).sort((a,b)=>Math.hypot(a.x*10-target.x,-a.y*10-target.z)-Math.hypot(b.x*10-target.x,-b.y*10-target.z));for(let t of nearby.slice(0,this.quality==='ultra'?100:49)){t.used=performance.now();if(!t.full&&!t.loading)this.tileQueue.push(()=>this.loadTile(t))}}
  let full=[...this.tiles.values()].filter(t=>t.full).sort((a,b)=>a.used-b.used);for(let t of full.slice(0,Math.max(0,full.length-150))){this.terrainRoot.remove(t.mesh);t.mesh.geometry.dispose();t.mesh.material.dispose();t.mesh=this.makeTerrain(t,9,new Float32Array(t.h),t.c);t.full=false;t.heights=null;this.terrainRoot.add(t.mesh)}this.pump();this.refreshObjects();
  let radius=Math.max(14,Math.min(55,d*.6)),c=this.sun.shadow.camera;c.left=c.bottom=-radius;c.right=c.top=radius;c.near=.5;c.far=400;c.updateProjectionMatrix();this.sun.target.position.copy(target);this.sun.position.copy(target).add(new THREE.Vector3(-75,140,65));this.sun.shadow.autoUpdate=d<200;this.sun.castShadow=d<200&&this.quality!=='low';
  this.scene.fog.density=d>200?.0008:.003;this.applyPointSize();$('sceneStats').textContent=`${this.world.terrain.length.toLocaleString('ru')} ячеек · ${Object.keys(this.world.models).length.toLocaleString('ru')} моделей · ${this.renderer.info.render.triangles.toLocaleString('ru')} треугольников`;
 }
 animate(){requestAnimationFrame(()=>this.animate());let now=performance.now();if(this.flight){let f=this.flight,t=Math.min(1,(now-f.start)/900),s=t*t*(3-2*t);this.camera.position.lerpVectors(f.from,f.to,s);this.controls.target.lerpVectors(f.targetFrom,f.targetTo,s);if(t===1)this.flight=null}this.controls.update();
  // Keep useful depth precision at both street and island viewing distances.
  // A fixed 0.025 near plane made sea/shore depths compete at overview scale.
  let clipDistance=this.camera.position.distanceTo(this.controls.target);
  let near=Math.max(.02,clipDistance/250),far=Math.max(1200,clipDistance*3);
  if(Math.abs(near-this.camera.near)>.0001||Math.abs(far-this.camera.far)>1){this.camera.near=near;this.camera.far=far;this.camera.updateProjectionMatrix()}
  this.waterUniforms.time.value=(now-this.start)/1000;if(this.ready&&(!this.lastLOD||now-this.lastLOD>1000)){this.updateLOD();this.lastLOD=now}this.renderer.render(this.scene,this.camera)}
}
