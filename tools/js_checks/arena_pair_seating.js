/**
 * Scenario A2/A4 - a pair bound by an accepted challenge sits together.
 *
 * There is no JS test runner in this repo and adding one for four assertions
 * would be a bigger change than the rule itself, so this is a plain node
 * script:  node tools/js_checks/arena_pair_seating.js
 *
 * It does NOT re-implement the rule. It loads static/js/arena_render.js and
 * calls the real buildAssignments, which is the only way an assertion here can
 * still mean something after somebody edits the renderer.
 *
 * Expected output - all four true:
 *   SAME RING  ... adjacent: true
 *   STABLE     same cells after reorder: true
 *   TWO RINGS  ... own rings: true   (angle gap under ~0.01 of the way round)
 *   UNPAIRED   ... NOT adjacent: true
 */
const fs = require('fs');
const path = require('path').join(__dirname, '..', '..', 'static', 'js', 'arena_render.js');
const src = fs.readFileSync(path, 'utf8');

// The file is an IIFE over `global`/document. Give it just enough to load.
const sandbox = {
  window: {location: {search: ''}, addEventListener(){}, matchMedia: () => ({matches:false, addEventListener(){}})},
  document: {
    getElementById: () => null, querySelector: () => null,
    querySelectorAll: () => [], createElement: () => ({style:{}, setAttribute(){}, appendChild(){}, classList:{add(){},remove(){}}}),
    createElementNS: () => ({style:{}, setAttribute(){}, appendChild(){}, classList:{add(){},remove(){}}}),
    addEventListener(){}, body: {classList:{add(){},remove(){}}}
  },
  console,
};
sandbox.window.document = sandbox.document;
sandbox.globalThis = sandbox;

// Expose buildAssignments by appending an export line inside the IIFE scope.
const patched = src.replace(
  /\}\)\((?:typeof )?window[^)]*\);?\s*$/,
  match => match
).replace('function buildAssignments(payload, geometry) {',
          'module.exports.buildAssignments = buildAssignments;\n  function buildAssignments(payload, geometry) {');

const vm = require('vm');
const mod = {exports: {}};
const ctx = vm.createContext(Object.assign(sandbox, {module: mod, exports: mod.exports, require}));
try { vm.runInContext(patched, ctx); } catch (e) { console.log('LOAD ERROR:', e.message); }

const build = mod.exports.buildAssignments;
if (!build) { console.log('buildAssignments not exported'); process.exit(1); }

function ring(index, key, segments) { return {kind:'rank', index, key, segments}; }
const geometry = {rings: [
  ring(6, 'kitchen_porter', 40), ring(5, 'prep_cook', 36), ring(4, 'commis_chef', 32),
]};
function chef(slug, battle_id) {
  return {slug, name: slug, battle_id, in_battle: !!battle_id, is_online: true};
}

function seatsOf(payload) {
  const a = build(payload, geometry).filter(x => x.occupancy === 'chef');
  const out = {};
  a.forEach(x => { out[x.entity.slug] = {ring: x.ring, cell: x.cell}; });
  return out;
}

// 1. Same rank, same ring -> adjacent cells.
let p = {rings: {kitchen_porter: [chef('a', 16), chef('b', 16), chef('idle', null)],
                 prep_cook: [], commis_chef: []}, spectators: [], center: {}};
let s = seatsOf(p);
const cap = 40;
const d = Math.abs(s.a.cell - s.b.cell) % cap;
console.log('SAME RING  a=', JSON.stringify(s.a), 'b=', JSON.stringify(s.b),
            '=> adjacent:', d === 1 || d === cap - 1);

// 2. Stability across polls with a different chef order and an extra idle chef.
let p2 = {rings: {kitchen_porter: [chef('b', 16), chef('zzz', null), chef('a', 16)],
                  prep_cook: [], commis_chef: []}, spectators: [], center: {}};
let s2 = seatsOf(p2);
console.log('STABLE     same cells after reorder:',
            s.a.cell === s2.a.cell && s.b.cell === s2.b.cell);

// 3. One rank apart -> each keeps his own ring, aligned by angle.
let p3 = {rings: {kitchen_porter: [chef('low', 21)], prep_cook: [chef('high', 21)],
                  commis_chef: []}, spectators: [], center: {}};
let s3 = seatsOf(p3);
const fracLow = s3.low.cell / 40, fracHigh = s3.high.cell / 36;
console.log('TWO RINGS  low=', JSON.stringify(s3.low), 'high=', JSON.stringify(s3.high),
            '=> own rings:', s3.low.ring === 6 && s3.high.ring === 5,
            '| angle gap:', Math.abs(fracLow - fracHigh).toFixed(4));

// 4. Unpaired chefs are still scattered, not glued.
let p4 = {rings: {kitchen_porter: [chef('x', null), chef('y', null)],
                  prep_cook: [], commis_chef: []}, spectators: [], center: {}};
let s4 = seatsOf(p4);
const d4 = Math.abs(s4.x.cell - s4.y.cell) % cap;
console.log('UNPAIRED   x=', s4.x.cell, 'y=', s4.y.cell,
            '=> NOT adjacent:', !(d4 === 1 || d4 === cap - 1));
