import test from 'node:test';
import assert from 'node:assert/strict';
import {isEditorModel, hideEditorModels} from '../public/world-models.js';

test('hide editor helpers, preserving real road markers and ship geometry', () => {
  for (const name of ['EditorMarker.NIF', 'meshes\\EditorMarker_box_01.NIF', 'Marker_Divine.nif', 'Marker_Prison.nif', 'Marker_Temple.nif']) {
    assert.equal(isEditorModel(name), true, name);
  }
  for (const name of ['x\\Ex_Gnisis_roadmarker_01.nif', 'x/ex_de_ship.nif', 'my_editormarker_house.nif']) {
    assert.equal(isEditorModel(name), false, name);
  }
});

test('old prepared worlds lose only helper models and their placements', () => {
  const world = {terrain: [{}], models: {
    box: {name: 'EditorMarker_box_01.NIF'}, green: {name: 'Marker_Divine.nif'},
    ship: {name: 'x/ex_de_ship.nif'}, road: {name: 'x/Ex_Gnisis_roadmarker_01.nif'},
  }, instances: [['box', 1], ['ship', 2], ['green', 3], ['road', 4], ['ship', 5]]};
  const result = hideEditorModels(world);
  assert.deepEqual(Object.keys(result.models), ['ship', 'road']);
  assert.deepEqual(result.instances, [['ship', 2], ['road', 4], ['ship', 5]]);
  assert.equal(result.terrain, world.terrain);
  assert.equal(world.instances.length, 5);
  assert.equal(Object.keys(world.models).length, 4);
});
