import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { optimize } from 'svgo';
import * as deck from './cards.mjs';
import fs from 'fs';

const suits = { S: 'spades', H: 'hearts', D: 'diamonds', C: 'clubs' };  // keys match the package's export names
const ranks = ['a','2','3','4','5','6','7','8','9','10','j','q','k'];
const art = {};
let raw = 0;
for (const L of Object.keys(suits)) ranks.forEach((r, i) => {
  const C = deck[L + (r === 'a' ? 'a' : r)];
  if (!C) throw new Error('missing ' + L + r);
  const svg = renderToStaticMarkup(React.createElement(C));
  raw += svg.length;
  const out = optimize(svg, {
    multipass: true,
    plugins: [
      { name: 'preset-default', params: { overrides: { cleanupIds: false, removeViewBox: false } } },
      { name: 'removeAttrs', params: { attrs: ['svg:(class|height|width)'] } },
    ],
  }).data;
  art[`${L.toLowerCase()}${i + 1}`] = out;
});
console.log('raw', raw, 'optimised', Object.values(art).reduce((n, s) => n + s.length, 0));
fs.writeFileSync('art.json', JSON.stringify(art));
const ids = Object.values(art).join('').match(/ id="[^"]+"/g) || [];
console.log('ids', ids.length, 'unique', new Set(ids).size);
console.log('style tags', Object.values(art).filter(s => s.includes('<style')).length, 'xlink', Object.values(art).filter(s => s.includes('xlink:href')).length);
