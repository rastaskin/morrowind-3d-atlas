// Construction Set helpers are present in ESM files but hidden during gameplay.
const editorModels = new Set([
  'editormarker.nif', 'editormarker_box_01.nif',
  'marker_divine.nif', 'marker_prison.nif', 'marker_temple.nif',
]);

export function isEditorModel(name) {
  return editorModels.has(String(name).replaceAll('\\', '/').split('/').pop().toLowerCase());
}

export function hideEditorModels(world) {
  const hidden = new Set(Object.entries(world.models)
    .filter(([, model]) => isEditorModel(model.name)).map(([key]) => key));
  return {...world,
    models: Object.fromEntries(Object.entries(world.models).filter(([key]) => !hidden.has(key))),
    instances: world.instances.filter(instance => !hidden.has(instance[0])),
  };
}
