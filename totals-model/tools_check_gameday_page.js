const { chromium } = require('playwright');
const path = require('path'); const fs = require('fs');
const FIX = JSON.parse(fs.readFileSync('cases.json', 'utf8'));
(async () => {
  const b = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
  const pg = await b.newPage({ viewport: { width: 1240, height: 1400 } });
  const errs = []; pg.on('pageerror', e => errs.push(String(e)));
  pg.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text()); });
  await pg.goto('file://' + path.join(__dirname, 'gameday.html'));
  await pg.waitForTimeout(400);
  let fails = 0;
  const chk = (ok, m, d) => { if (!ok) fails++; console.log(`${ok?'PASS':'FAIL'}  ${m}${ok?'':'\n        '+d}`); };

  for (const [name, c] of Object.entries(FIX.cases)) {
    for (const mode of ['strict', 'trial']) {
      const want = FIX.expect[`${name}|${mode}`];
      const got = await pg.evaluate(async ([c, mode]) => {
        const ids = ["away","home","open","line","mph","dir","temp","uo","uu","tick","cash",
                     "fa","fh","fg","h2h","h2hn","spa","spai","sph","sphi","bpa","bpai","bph","bphi"];
        ids.forEach(id => { const e = document.getElementById(id); e.value = ''; });
        document.getElementById('dome').checked = false;
        document.getElementById(mode === 'trial' ? 'm-trial' : 'm-strict').click();
        for (const [k, v] of Object.entries(c)) {
          if (k === 'dome') { document.getElementById('dome').checked = !!v; }
          else { const e = document.getElementById(k); if (e) e.value = String(v); }
        }
        ids.forEach(id => document.getElementById(id)
          .dispatchEvent(new Event('input', { bubbles: true })));
        document.getElementById('dome').dispatchEvent(new Event('change', { bubbles: true }));
        await new Promise(r => setTimeout(r, 120));
        const band = document.querySelector('#verdict .band').textContent.trim();
        const pick = document.querySelector('#verdict .pick');
        const netTxt = document.querySelectorAll('#verdict .nums .v')[0].textContent.trim();
        return { band, side: pick ? pick.textContent.trim().split(' ')[0] : null,
                 net: parseFloat(netTxt), bars: document.querySelectorAll('#chart .bar').length,
                 go: document.getElementById('verdict').classList.contains('go') };
      }, [c, mode]);
      const tag = `${name}|${mode}`;
      chk(got.band === want.verdict, `${tag}: ${want.verdict}`, `page said ${got.band}`);
      chk(Math.abs(got.net - want.net) < 0.011, `${tag}: net ${want.net.toFixed(2)}`, `page said ${got.net}`);
      chk(got.bars === want.n, `${tag}: ${want.n} bars`, `page drew ${got.bars}`);
      if (want.side) chk(got.side === want.side, `${tag}: side ${want.side}`, `page said ${got.side}`);
      chk(got.go === (want.verdict !== 'PASS'),
          `${tag}: green only when it is a call`, `go=${got.go} verdict=${want.verdict}`);
    }
  }
  if (errs.length) { console.log('PAGE ERRORS:\n' + errs.join('\n')); fails++; }
  console.log(fails ? `\n${fails} FAILED` : '\nall checks passed');
  await b.close(); process.exit(fails ? 1 : 0);
})();
