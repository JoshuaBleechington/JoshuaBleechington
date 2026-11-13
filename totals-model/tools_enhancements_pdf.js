// Print tools_enhancements.py's page to PDF with the pre-installed Playwright.
// Usage: NODE_PATH=/opt/node22/lib/node_modules node tools_enhancements_pdf.js in.html out.pdf
const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const [inp, out] = process.argv.slice(2);
  if (!inp || !out) { console.error('usage: node tools_enhancements_pdf.js in.html out.pdf'); process.exit(2); }
  const b = await chromium.launch();
  const pg = await b.newPage();
  await pg.goto('file://' + path.resolve(inp));
  await pg.emulateMedia({ media: 'print' });
  await pg.pdf({ path: out, format: 'Letter', printBackground: true, margin: { top: '14mm', bottom: '14mm', left: '13mm', right: '13mm' },
                 displayHeaderFooter: true, headerTemplate: '<div></div>',
                 footerTemplate: '<div style="font: 8pt Helvetica, Arial, sans-serif; color: #5b6270; width: 100%; padding: 0 13mm; display: flex; justify-content: space-between;"><span>The Super Model: the enhancements to date</span><span class="pageNumber"></span></div>' });
  await b.close();
  console.log('wrote', out);
})();
