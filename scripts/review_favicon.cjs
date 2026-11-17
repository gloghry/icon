// Optional authoring tool: render the actual SVG at favicon sizes in both themes.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { chromium, webkit } = require('playwright');
const root = path.resolve(__dirname, '..');
const output = path.join(root, 'generated/original/review');
const directory = path.join(root, 'gl_assets/variants/original');
const uri = name => 'data:image/svg+xml;base64,' + fs.readFileSync(path.join(directory, name)).toString('base64');
const before = uri('reference/favicon-before.svg');
const after = uri('favicon.svg');
const sizes = [16, 24, 32, 48];

async function main() {
  fs.mkdirSync(output, { recursive: true });
  const results = [];
  for (const [engine, type] of [['chromium', chromium], ['webkit', webkit]]) {
    const browser = await type.launch();
    try {
      for (const scheme of ['light', 'dark']) {
        const context = await browser.newContext({ viewport: { width: 720, height: 430 }, deviceScaleFactor: 1, colorScheme: scheme });
        try {
          const page = await context.newPage();
          const row = (name, source) => `<div class="row"><strong>${name}</strong>${sizes.map(size => `<span><img class="native" src="${source}" width="${size}" height="${size}" alt="${name} GL at ${size} pixels"></span>`).join('')}</div>`;
          await page.setContent(`<!doctype html><meta charset="utf-8"><title>GL favicon review</title><style>
            *{box-sizing:border-box}body{margin:0;padding:24px;font:14px Arial,sans-serif;background:${scheme === 'light' ? '#EDF1F3' : '#080C11'};color:${scheme === 'light' ? '#202A30' : '#EDF1F3'};color-scheme:${scheme}}
            h1{font-size:18px;margin:0 0 20px}.row{display:grid;grid-template-columns:140px repeat(4,1fr);align-items:center;min-height:64px}.row span{text-align:center}img{vertical-align:middle}.inspect{display:flex;gap:70px;align-items:start;margin-top:14px}.inspect figure{margin:0}.inspect figcaption{margin-bottom:8px}
            </style><h1>GL favicon — ${scheme} background</h1><div class="row" style="min-height:24px"><span>Actual size (1×)</span>${sizes.map(s => `<span>${s} px</span>`).join('')}</div>
            ${row('Before: diagonal foot', before)}${row('New: flat GL', after)}
            <div class="inspect"><figure><figcaption>Before — 128 px inspection</figcaption><img src="${before}" width="128" height="128" alt="Old favicon enlarged"></figure><figure><figcaption>New — 128 px inspection</figcaption><img src="${after}" width="128" height="128" alt="Flat favicon enlarged"></figure></div>`);
          await page.locator('img').evaluateAll(images => Promise.all(images.map(i => i.decode())));
          const dimensions = await page.locator('.native').evaluateAll(images => images.map(i => ({ width: i.getBoundingClientRect().width, height: i.getBoundingClientRect().height })));
          if (dimensions.some((d, i) => d.width !== sizes[i % 4] || d.height !== sizes[i % 4])) throw new Error('Native favicon preview was resized');
          if (engine === 'chromium') await page.screenshot({ path: path.join(output, `favicon-${scheme}.png`) });
          // A transparent 32px browser raster also verifies the embedded SVG's media query.
          await page.setContent(`<style>html,body{margin:0;background:transparent;color-scheme:${scheme}}</style><img src="${after}" width="32" height="32" alt="GL">`);
          await page.locator('img').evaluate(i => i.decode());
          await page.locator('img').screenshot({ path: path.join(output, `favicon-${engine}-${scheme}-32.png`), omitBackground: true });
          results.push({ engine, version: browser.version(), scheme, sizes, deviceScaleFactor: 1, passed: true });
        } finally { await context.close(); }
      }
    } finally { await browser.close(); }
  }
  fs.writeFileSync(path.join(output, 'favicon-validation.json'), JSON.stringify({ results }, null, 2) + '\n');
  const manifestPath = path.join(root, 'generated/original/manifest.json');
  const manifest = JSON.parse(fs.readFileSync(manifestPath));
  for (const name of ['favicon-light.png', 'favicon-dark.png', 'favicon-validation.json',
    ...['chromium', 'webkit'].flatMap(engine => ['light', 'dark'].map(scheme => `favicon-${engine}-${scheme}-32.png`))]) {
    manifest.sha256['review/' + name] = crypto.createHash('sha256').update(fs.readFileSync(path.join(output, name))).digest('hex');
  }
  manifest.sha256 = Object.fromEntries(Object.entries(manifest.sha256).sort(([a], [b]) => a.localeCompare(b)));
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + '\n');
  console.log('Favicon native sizes checked in Chromium and WebKit, light and dark.');
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
