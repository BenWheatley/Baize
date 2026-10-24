// Puts the icons listed in ICONS into baize.html as an SVG sprite, between the icons:start and icons:end markers.
// The icons are Google's Material Symbols (outlined, weight 500), Apache License 2.0; see NOTICE.
import fs from 'fs';

const ICONS = ['close', 'lightbulb', 'menu', 'undo', 'visibility'];

const symbol = name => {
  const svg = fs.readFileSync(new URL(`./node_modules/@material-symbols/svg-500/outlined/${name}.svg`, import.meta.url), 'utf8');
  const [, viewBox] = svg.match(/viewBox="([^"]+)"/);
  const [, paths] = svg.match(/<svg[^>]*>(.*)<\/svg>/s);
  return `<symbol id="i-${name}" viewBox="${viewBox}">${paths.trim()}</symbol>`;
};

const sprite = `<!-- icons:start -->\n<svg width="0" height="0" style="position:absolute" aria-hidden="true">\n${ICONS.map(symbol).join('\n')}\n</svg>\n<!-- icons:end -->`;
const file = new URL('../../baize.html', import.meta.url);
const html = fs.readFileSync(file, 'utf8');
const pattern = /<!-- icons:start -->[\s\S]*<!-- icons:end -->/;
if (!pattern.test(html)) throw new Error('icons markers not found in baize.html');
fs.writeFileSync(file, html.replace(pattern, () => sprite));
