'use strict';
/* Measures the C search on Spider deals: how many it wins, and how fast.
     node tools/wasm/measure.js <suits> <positions> <deals> <first seed> ['{"knob": value}' ...]
   Each knob setting (the index into `tuning` in core.h, and the value) is tried on the same deals, over the game's own
   defaults; with none, the defaults are measured. Used for docs/spider-four-suits.md. Needs solver.wasm (build.sh). */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const html = fs.readFileSync(path.join(__dirname, '..', '..', 'baize.html'), 'utf8');
const grab = id => html.match(new RegExp(`<script id="${id}">([\\s\\S]*?)</script>`))[1];
const ctx = vm.createContext({ structuredClone, console, atob });
const CardSim = vm.runInContext(`${grab('engine')}\n;CardSim`, ctx);
vm.runInContext(grab('solver-wasm'), ctx);
const wasm = new WebAssembly.Instance(new WebAssembly.Module(fs.readFileSync(path.join(__dirname, 'solver.wasm'))), {}).exports;

const [suits, positions, deals, first, ...settings] = process.argv.slice(2);
const options = { suits: Number(suits), gaps: 1 };
const images = Array.from({ length: Number(deals) }, (_, i) =>
  CardSim.fast.spider.image(CardSim.spider.setup(options, CardSim.mulberry32(Number(first) + i))));

for (const setting of settings.length ? settings : ['{}']) {
  let won = 0;
  const started = Date.now();
  for (const image of images) {
    new Uint8Array(wasm.memory.buffer, wasm.image_address(), 256).set(image);
    new Int32Array(wasm.memory.buffer, wasm.gaps_address(), 1)[0] = options.gaps;
    wasm.load_position(1);                                                    // puts the game's defaults in `tuning`
    const tuning = new Int32Array(wasm.memory.buffer, wasm.tuning_address(), 32);
    for (const [index, value] of Object.entries(JSON.parse(setting))) tuning[Number(index)] = value;
    if (wasm.solve_tuned(1, Number(positions)) >= 0) won++;
  }
  const seconds = (Date.now() - started) / 1000;
  console.log(`${setting}  ${suits} suits, ${positions} positions: ${won} of ${deals} won, ${(seconds / deals).toFixed(2)} s a deal`);
}
