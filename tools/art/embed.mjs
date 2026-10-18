// Replaces the KENNARD_ART object in baize.html with the contents of art.json.
import fs from 'fs';

const art = fs.readFileSync(new URL('./art.json', import.meta.url), 'utf8').trim();
const file = new URL('../../baize.html', import.meta.url);
const html = fs.readFileSync(file, 'utf8');
const pattern = /const KENNARD_ART = .*;\n/;
if (!pattern.test(html)) throw new Error('KENNARD_ART not found in baize.html');
fs.writeFileSync(file, html.replace(pattern, () => `const KENNARD_ART = ${art};\n`));
