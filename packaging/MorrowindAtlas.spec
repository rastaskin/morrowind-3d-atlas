from pathlib import Path
from importlib import metadata
from PyInstaller.utils.hooks import collect_data_files

root=Path(SPECPATH).parent
data=[]
for name in ['index.html','app.js','map3d.js','progress.js','save-parser.js','catalog.json','style.css','game-ui.css']:
    data.append((str(root/'public'/name),'bundle-public'))
for name in ['three.module.js','three.core.js','OrbitControls.js','LICENSE-three.txt']:
    data.append((str(root/'public/vendor'/name),'bundle-public/vendor'))
for name in ['game_assets.py','build_3d.py','build_detail.py','prepare_ui.py']:
    data.append((str(root/'scripts'/name),'scripts'))
data += collect_data_files('pyffi')
data += [(str(root/'LICENSE'),'licenses'),(str(root/'PRIVACY.md'),'licenses')]
for distribution_name in ['numpy','Pillow','PyFFI','fonttools','Brotli','PyInstaller']:
    distribution=metadata.distribution(distribution_name)
    for entry in distribution.files or []:
        rel=Path(str(entry))
        if rel.name.lower().startswith(('license','copying')) or 'licenses' in [part.lower() for part in rel.parts]:
            source=distribution.locate_file(entry)
            if source.is_file() and source.suffix.lower() not in {'.py','.pyc'}:
                data.append((str(source),'licenses/third-party/'+distribution_name+'/'+str(rel.parent)))
a=Analysis([str(root/'desktop.py')],pathex=[str(root)],binaries=[],datas=data,
    hiddenimports=['numpy','PIL.DdsImagePlugin','PIL.TgaImagePlugin','PIL.PngImagePlugin','pyffi.formats.nif','fontTools.ttLib','fontTools.ttLib.woff2','brotli'],
    excludes=['matplotlib','pandas','scipy','torch','tensorflow','IPython','pytest'],noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='MorrowindAtlas',debug=False,
    bootloader_ignore_signals=False,strip=False,upx=False,console=False,
    icon=str(root/'packaging/atlas.ico'),version=str(root/'packaging/version.txt'))
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='MorrowindAtlas')
