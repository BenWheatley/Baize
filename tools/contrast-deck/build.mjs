// Optimises the faces made by prepare.py and puts them into baize.html between the contrast-art markers.
// usage: node build.mjs PREPARED_DIR
import fs from 'fs';
import { optimize } from 'svgo';

const dir = process.argv[2].replace(/\/?$/, '/');
const rank = { Ace: 1, Jack: 11, Queen: 12, King: 13 };
const art = {};
for (const suit of ['spade', 'heart', 'diamond', 'club']) {
  for (const name of ['Ace', 2, 3, 4, 5, 6, 7, 8, 9, 10, 'Jack', 'Queen', 'King']) {
    const key = `${suit[0]}${rank[name] ?? name}`;
    const { data } = optimize(fs.readFileSync(`${dir}${suit}${name}.svg`, 'utf8'), { multipass: true, floatPrecision: 1, plugins: [
      { name: 'preset-default', params: { overrides: { removeViewBox: false, cleanupIds: false } } },
      { name: 'removeDimensions' },
      { name: 'prefixIds', params: { prefix: key } },        // every card lives in one page: ids must not clash
    ] });
    art[key] = data.replace('<svg ', '<svg preserveAspectRatio="none" ');
  }
}
const block = `<!-- contrast-art:start -->\n<script id="deck-art-contrast">\nconst CONTRAST_ART = ${JSON.stringify(art)};\n</script>\n<!-- contrast-art:end -->`;
const file = new URL('../../baize.html', import.meta.url);
const html = fs.readFileSync(file, 'utf8');
const pattern = /<!-- contrast-art:start -->[\s\S]*<!-- contrast-art:end -->/;
if (!pattern.test(html)) throw new Error('contrast-art markers not found in baize.html');
fs.writeFileSync(file, html.replace(pattern, () => block));
console.log('bytes', block.length);
