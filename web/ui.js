// =========================================================== browser IO ===
const W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main";

function paraText(node) {
  let out = "";
  const walk = (n) => {
    for (const c of n.childNodes) {
      if (c.nodeType !== 1) continue;
      const ln = c.localName;
      if (ln === "t") out += c.textContent || "";
      else if (ln === "tab") out += "\t";
      else if (ln === "br" || ln === "cr") out += "\n";
      else walk(c);
    }
  };
  walk(node);
  return out;
}

function blockText(root) {
  const blocks = [];
  const walk = (node) => {
    for (const child of node.children) {
      const ln = child.localName;
      if (ln === "p") {
        let t = paraText(child);
        // A correctly built Word bullet stores the glyph as a numbering
        // property, not as text, so nothing in the runs looks like a bullet.
        const pr = child.getElementsByTagNameNS(W_NS, "numPr");
        if (t.trim() && pr.length) t = "- " + t.replace(/^\s+/, "");
        blocks.push(t);
      }
      else if (ln === "tbl") {
        for (const row of child.children) {
          if (row.localName !== "tr") continue;
          const cells = [];
          for (const cell of row.children) {
            if (cell.localName !== "tc") continue;
            const parts = [];
            for (const p of cell.children) if (p.localName === "p") parts.push(paraText(p).trim());
            cells.push(parts.filter(Boolean).join(" "));
          }
          const line = cells.filter(Boolean).join("  ");
          if (line.trim()) blocks.push(line);
        }
      } else if (ln === "sdt" || ln === "sdtContent" || ln === "body") walk(child);
    }
  };
  walk(root);
  return blocks;
}


/* Minimal ZIP reader. A .docx is a zip archive, and browsers can inflate
   deflate-raw natively, so the whole format is reachable with no library --
   which keeps the most useful feature on this page working even if a CDN is
   blocked or offline. */
async function unzip(buffer) {
  const view = new DataView(buffer);
  const bytes = new Uint8Array(buffer);
  // Locate the end-of-central-directory record by scanning back from the tail.
  let eocd = -1;
  for (let i = bytes.length - 22; i >= Math.max(0, bytes.length - 65558); i--) {
    if (view.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
  }
  if (eocd < 0) throw new Error("That file is not a valid .docx archive.");
  const count = view.getUint16(eocd + 10, true);
  let ptr = view.getUint32(eocd + 16, true);

  const out = {};
  for (let n = 0; n < count; n++) {
    if (view.getUint32(ptr, true) !== 0x02014b50) break;
    const method = view.getUint16(ptr + 10, true);
    const compSize = view.getUint32(ptr + 20, true);
    const nameLen = view.getUint16(ptr + 28, true);
    const extraLen = view.getUint16(ptr + 30, true);
    const commentLen = view.getUint16(ptr + 32, true);
    const localOffset = view.getUint32(ptr + 42, true);
    const name = new TextDecoder("utf-8").decode(bytes.subarray(ptr + 46, ptr + 46 + nameLen));
    ptr += 46 + nameLen + extraLen + commentLen;

    if (view.getUint32(localOffset, true) !== 0x04034b50) continue;
    const lNameLen = view.getUint16(localOffset + 26, true);
    const lExtraLen = view.getUint16(localOffset + 28, true);
    const start = localOffset + 30 + lNameLen + lExtraLen;
    const raw = bytes.subarray(start, start + compSize);

    if (method === 0) { out[name] = raw; continue; }
    if (method !== 8) continue;  // only stored and deflate appear in practice
    if (typeof DecompressionStream === "undefined") {
      throw new Error("This browser cannot decompress .docx files. Paste the text instead.");
    }
    const stream = new Blob([raw]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
    out[name] = new Uint8Array(await new Response(stream).arrayBuffer());
  }
  return out;
}

/* .docx is a zip of XML, read directly so the layout constructs that actually
   break ATS parsers -- tables, text boxes, columns, headers -- are visible. */
async function extractDocx(buffer, name) {
  let files;
  try {
    files = await unzip(buffer);
  } catch (e) {
    throw new Error(e.message && e.message.includes("decompress") ? e.message
      : "That file is not a valid .docx. A legacy .doc must be re-saved as .docx.");
  }
  if (!files["word/document.xml"]) throw new Error("No Word document found inside that file.");
  const dec = new TextDecoder("utf-8");
  const parser = new DOMParser();
  const xml = parser.parseFromString(dec.decode(files["word/document.xml"]), "application/xml");
  if (xml.querySelector("parsererror")) throw new Error("The Word document XML could not be read.");

  const body = xml.getElementsByTagNameNS(W_NS, "body")[0] || xml.documentElement;
  const text = blockText(body).join("\n");

  const tbls = xml.getElementsByTagNameNS(W_NS, "tbl");
  let tableChars = 0;
  for (const t of tbls) for (const p of t.getElementsByTagNameNS(W_NS, "p")) tableChars += paraText(p).length;

  const boxContents = xml.getElementsByTagNameNS(W_NS, "txbxContent");
  let boxChars = 0;
  for (const b of boxContents) for (const p of b.getElementsByTagNameNS(W_NS, "p")) boxChars += paraText(p).length;

  let columns = 1;
  for (const c of xml.getElementsByTagNameNS(W_NS, "cols")) {
    const n = parseInt(c.getAttributeNS(W_NS, "num") || "1", 10);
    if (!Number.isNaN(n)) columns = Math.max(columns, n);
  }

  let images = 0, headerFooterChars = 0, fonts = [];
  for (const fname of Object.keys(files)) {
    if (fname.startsWith("word/media/")) images++;
    if (/^word\/(header|footer)\d*\.xml$/.test(fname)) {
      try {
        const hx = parser.parseFromString(dec.decode(files[fname]), "application/xml");
        for (const p of hx.getElementsByTagNameNS(W_NS, "p")) headerFooterChars += paraText(p).length;
      } catch (e) { /* an unreadable header simply contributes nothing */ }
    }
  }
  if (files["word/fontTable.xml"]) {
    try {
      const fx = parser.parseFromString(dec.decode(files["word/fontTable.xml"]), "application/xml");
      for (const f of fx.getElementsByTagNameNS(W_NS, "font")) {
        const n = f.getAttributeNS(W_NS, "name");
        if (n) fonts.push(n);
      }
    } catch (e) { /* font table is advisory only */ }
  }

  return { text, source: name, kind: "docx", tables: tbls.length, tableTextChars: tableChars,
           textBoxes: boxContents.length, textBoxChars: boxChars, headerFooterChars,
           images, columns, fonts, pages: null, warnings: [], extractor: "browser-ooxml" };
}

async function extractPdf(buffer, name) {
  if (typeof pdfjsLib === "undefined") {
    throw new Error("The PDF reader did not load. Export your resume as .docx, or paste the text.");
  }
  try {
    const doc = await pdfjsLib.getDocument({ data: new Uint8Array(buffer) }).promise;
    const parts = [];
    for (let i = 1; i <= doc.numPages; i++) {
      const page = await doc.getPage(i);
      const content = await page.getTextContent();
      let last = null, line = [];
      for (const item of content.items) {
        const y = item.transform[5];
        if (last !== null && Math.abs(y - last) > 3) { parts.push(line.join("")); line = []; }
        line.push(item.str);
        last = y;
      }
      if (line.length) parts.push(line.join(""));
    }
    const text = parts.join("\n");
    const warnings = [];
    if (text.trim().length < 200 && buffer.byteLength > 20000) {
      warnings.push("Almost no selectable text was recovered. This resume is probably a scan or an image export -- most ATS parsers will read it as blank.");
    }
    return { text, source: name, kind: "pdf", pages: doc.numPages, images: 0, warnings,
             tables: null, tableTextChars: 0, textBoxes: null, textBoxChars: 0,
             headerFooterChars: 0, columns: null, fonts: [], extractor: "pdf.js" };
  } catch (e) {
    throw new Error("That PDF could not be read here (" + (e.message || e) + "). Export as .docx, or paste the text.");
  }
}

// ============================================================= rendering ===
const $ = (id) => document.getElementById(id);
const LEX = new SkillLexicon(ALIAS_DATA);
const esc = (s) => String(s).replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

let currentDoc = null;     // structural metadata from an uploaded file
let lastTotal = null;
let debounceTimer = null;

function toneFor(v) { return v >= 75 ? "good" : v >= 50 ? "warn" : "crit"; }
function toneVar(v) { return `var(--${toneFor(v)})`; }

function renderComponents(report) {
  $("components").innerHTML = report.components.map((c) => `
    <div class="comp">
      <div class="comp-name">${esc(c.name)}<small>${c.points.toFixed(1)} / ${c.weight} pts</small></div>
      <div class="meter"><i style="width:${Math.max(0, Math.min(100, c.score)).toFixed(0)}%;background:${toneVar(c.score)}"></i></div>
      <div class="comp-num">${c.score.toFixed(0)}</div>
      <div class="comp-detail">${esc(c.detail)}</div>
    </div>`).join("");
}

function renderGates(report) {
  const el = $("gates");
  if (!report.gates.length) { el.innerHTML = ""; return; }
  el.innerHTML = report.gates.map((g) => `
    <div class="gate ${g.satisfied ? "pass" : "fail"}">
      <b>${g.satisfied ? "MET" : "NOT MET"}</b>
      <span>${esc(g.detail)} — ${esc(g.evidence)}</span>
    </div>`).join("")
    + (report.gatePenalty > 0
      ? `<div class="gate fail"><b>CAPPED</b><span>An unmet hard requirement caps the score
         (−${report.gatePenalty.toFixed(1)} points). Knockout filters do not average out.</span></div>`
      : "");
}

function renderChips(id, items, cls, empty) {
  const el = $(id);
  if (!items.length) { el.innerHTML = `<p class="empty">${esc(empty)}</p>`; return; }
  el.innerHTML = items.map((m) => {
    const req = m.requirement;
    const extra = cls === "gap" && req.required ? " req" : "";
    let title = "";
    if (req.contexts && req.contexts.length) title = ` title="${esc(req.contexts[0])}"`;
    else if (m.matchedForm) title = ` title="matched as: ${esc(m.matchedForm)}"`;
    return `<span class="chip ${cls}${extra}"${title}>${esc(req.term)}</span>`;
  }).join("");
}

function renderWeak(report) {
  const items = report.weak(14);
  const el = $("weak");
  if (!items.length) { el.innerHTML = `<p class="empty">Nothing weak — every match is demonstrated in context.</p>`; return; }
  el.innerHTML = items.map((m) => {
    const why = m.inSkillsOnly ? "in your skills list only" : `near miss: “${m.matchedForm}”`;
    return `<span class="chip soft" title="${esc(why)}">${esc(m.requirement.term)}</span>`;
  }).join("");
}

function renderFindings(report) {
  const el = $("findings");
  if (!report.parse.findings.length) {
    el.innerHTML = `<li class="empty">No parsing problems detected.</li>`;
    return;
  }
  el.innerHTML = report.parse.findings.map((f) => `
    <li class="finding ${f.severity}">
      <span class="sev">${f.severity}</span>
      <p>${esc(f.message)}</p>
      ${f.fix ? `<p class="fix">${esc(f.fix)}</p>` : ""}
    </li>`).join("");
}

function renderTicks() {
  $("ticks").innerHTML = [[40, "weak"], [55, "borderline"], [70, "good"], [85, "strong"]]
    .map(([v, label]) => `<span class="tick" style="left:${v}%">${label}</span>`).join("");
}

function render(report) {
  const tone = toneFor(report.total);
  $("score").innerHTML = `${report.total.toFixed(0)}<span class="den">/100</span>`;
  $("score").className = `scorenum s-${tone}`;
  $("band").textContent = report.band;
  $("band").className = `band s-${tone}`;
  $("verdict").textContent = report.verdict;
  $("scale-fill").style.width = `${Math.max(0, Math.min(100, report.total))}%`;
  $("scale-fill").style.background = toneVar(report.total);

  const d = $("delta");
  if (lastTotal !== null && Math.abs(report.total - lastTotal) >= 0.1) {
    const diff = report.total - lastTotal;
    d.textContent = `${diff > 0 ? "▲ +" : "▼ "}${diff.toFixed(1)} since last run`;
    d.className = `delta ${diff > 0 ? "s-good" : "s-crit"}`;
  } else if (lastTotal === null) { d.textContent = ""; }

  renderGates(report);
  renderComponents(report);
  renderChips("missing", report.missing(20), "gap", "Nothing missing — the posting's terms are all present.");
  renderWeak(report);
  renderChips("matched", report.matched(22), "hit", "No matches yet.");
  renderFindings(report);

  $("fixes").innerHTML = report.suggestions.length
    ? report.suggestions.map((s) => `<li><span>${esc(s)}</span></li>`).join("")
    : `<li class="empty">Nothing pressing to fix.</li>`;

  $("readout").classList.add("on");
  $("live-note").hidden = false;
}

// ============================================================== tailoring ===
let lastReport = null;
let tailored = null;
let downloads = null;   // resolved later, or stays null

// Skills the viewer has ticked off as genuinely theirs. Reset whenever a new
// posting or resume is scored, so a confirmation never carries silently from
// one application to the next.
let confirmedSkills = [];

function renderTailored(report) {
  const doc = report.document;
  const result = buildTailored(doc, report.jd, LEX, null, confirmedSkills);
  tailored = result;

  if (result.sourceWarnings.length) {
    $("tailor-output").classList.add("gone");
    $("tailor-intro").innerHTML =
      "<strong>This file cannot be rebuilt faithfully.</strong> "
      + result.sourceWarnings.map(esc).join(" ")
      + " Tailoring can only rearrange what came out of the file. Export the resume as .docx, "
      + "or paste its text above, and try again.";
    return;
  }

  const after = scoreResume({ ...doc, text: result.text, kind: "txt" }, report.jd, LEX);
  const diff = after.total - report.total;
  const chip = $("tailor-delta");
  chip.textContent = `${report.total.toFixed(1)} → ${after.total.toFixed(1)}`
    + (diff > 0 ? ` (+${diff.toFixed(1)})` : "");
  chip.classList.remove("gone");

  $("tailor-changes").innerHTML = result.changes.map((c) =>
    `<li><span class="cat">${esc(c.category)}</span>${esc(c.detail)}</li>`).join("");
  $("tailor-manual").innerHTML = result.manual.length
    ? result.manual.map((m) => `<li>${esc(m.detail)}</li>`).join("")
    : `<li class="empty">Nothing outstanding.</li>`;
  renderGaps(result);
  $("tailored").value = result.text;
  $("tailor-output").classList.remove("gone");
  $("tailor-intro").textContent =
    "Rebuilt around this posting. Read it before you send it — this is your resume, "
    + "reorganised and re-worded, with nothing added that you did not write.";
}


/* The gap list is the one place the tool will write a term it found no
   evidence for -- and only after a person says it is true of them. Ticking is
   the whole mechanism: no default is on, and the copy says what a tick means. */
function renderGaps(result) {
  const box = $("gap-box");
  // A confirmed term drops out of absentTerms, so it has to be added back to
  // the list -- ticked -- or there is no way to change your mind about it.
  const seen = new Set();
  const terms = [];
  for (const t of [...confirmedSkills, ...(result.absentTerms || [])]) {
    const key = t.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    terms.push(t);
  }
  if (!terms.length) { box.classList.add("gone"); return; }
  const chosen = new Set(confirmedSkills.map((t) => t.toLowerCase()));
  $("gap-terms").innerHTML = terms.slice(0, 24).map((t, i) =>
    `<label><input type="checkbox" data-term="${esc(t)}" id="gap-${i}"`
    + `${chosen.has(t.toLowerCase()) ? " checked" : ""}> ${esc(t)}</label>`).join("");
  box.classList.remove("gone");
}

function gapBoxes() {
  return [...document.querySelectorAll("#gap-terms input[type=checkbox]")];
}

$("gap-all").addEventListener("click", () => {
  gapBoxes().forEach((b) => { b.checked = true; });
});
$("gap-none").addEventListener("click", () => {
  gapBoxes().forEach((b) => { b.checked = false; });
});
$("gap-apply").addEventListener("click", () => {
  confirmedSkills = gapBoxes().filter((b) => b.checked).map((b) => b.dataset.term);
  if (lastReport) renderTailored(lastReport);
});

function safeFilename(name, ext) {
  const base = (name || "resume").replace(/[^A-Za-z0-9 _-]/g, "").trim().replace(/\s+/g, "_");
  return `${base || "resume"}_ATS.${ext}`;
}

async function saveTailoredDocx() {
  if (!tailored || !downloads) return;
  const note = $("tailor-note");
  try {
    const bytes = buildDocxBytes(tailored.blocks, {
      title: `${tailored.name || "Resume"} - Resume`, author: tailored.name || "",
    });
    await downloads.save({
      filename: safeFilename(tailored.name, "docx"),
      data: bytes.buffer,
    });
    note.className = "save-note";
    note.textContent = "Saved. Open it in Word once before sending, and export to PDF from there "
      + "if the application asks for one.";
  } catch (err) {
    const code = (err && err.code) || "unavailable";
    note.className = "save-note err";
    if (code === "declined") {
      note.textContent = "Save cancelled. The text above is the same document — copy it instead.";
    } else if (code === "rate_limited") {
      note.textContent = "A save prompt is already open. Try again in a moment.";
    } else {
      note.textContent = "Saving is not available in this view. Copy the text above instead.";
      $("tailor-save").classList.add("gone");
    }
  }
}

function wordCount(s) { return s.trim() ? s.trim().split(/\s+/).length : 0; }

function updateStats() {
  $("resume-stat").textContent = `${wordCount($("resume").value)} words`;
  $("jd-stat").textContent = `${wordCount($("jd").value)} words`;
}

function runScreen(isRerun) {
  const resumeText = $("resume").value;
  const jdText = $("jd").value;
  if (!resumeText.trim() || !jdText.trim()) {
    $("file-err").hidden = false;
    $("file-err").textContent = "Add both a resume and a job posting to run the screen.";
    return;
  }
  $("file-err").hidden = true;

  // Keep an uploaded file's layout facts, but always score the text on screen
  // so edits made here are what gets measured.
  const doc = currentDoc
    ? Object.assign({}, currentDoc, { text: resumeText })
    : { text: resumeText, source: "pasted text", kind: "txt", warnings: [],
        tables: null, tableTextChars: 0, textBoxes: null, textBoxChars: 0,
        headerFooterChars: 0, images: null, columns: null, fonts: [], pages: null };

  const jd = parseJD(jdText, LEX);
  confirmedSkills = [];   // a new scoring run is a new application
  const report = scoreResume(doc, jd, LEX);
  report.jd = jd;
  report.document = doc;
  lastReport = report;
  render(report);
  // A new score invalidates any resume built from the previous one.
  tailored = null;
  $("tailor-output").classList.add("gone");
  $("tailor-delta").classList.add("gone");
  lastTotal = report.total;
  if (!isRerun) $("readout").scrollIntoView({ behavior: "smooth", block: "start" });
}

function scheduleRerun() {
  updateStats();
  if (!$("readout").classList.contains("on")) return;
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => runScreen(true), 450);
}

async function loadFile(file) {
  const err = $("file-err");
  err.hidden = true;
  const name = file.name.toLowerCase();
  try {
    if (name.endsWith(".docx")) {
      currentDoc = await extractDocx(await file.arrayBuffer(), file.name);
    } else if (name.endsWith(".pdf")) {
      currentDoc = await extractPdf(await file.arrayBuffer(), file.name);
    } else if (/\.(txt|md|markdown)$/.test(name)) {
      currentDoc = { text: await file.text(), source: file.name, kind: "txt", warnings: [],
                     tables: null, tableTextChars: 0, textBoxes: null, textBoxChars: 0,
                     headerFooterChars: 0, images: null, columns: null, fonts: [], pages: null };
    } else if (name.endsWith(".doc") || name.endsWith(".rtf") || name.endsWith(".pages")) {
      throw new Error("That format is not one applicant tracking systems reliably parse. Re-save it as .docx or paste the text.");
    } else {
      currentDoc = { text: await file.text(), source: file.name, kind: "txt", warnings: [],
                     tables: null, tableTextChars: 0, textBoxes: null, textBoxChars: 0,
                     headerFooterChars: 0, images: null, columns: null, fonts: [], pages: null };
    }
    $("resume").value = currentDoc.text;
    updateStats();
    const note = currentDoc.kind === "docx"
      ? " — layout audit enabled" : currentDoc.kind === "pdf" ? " — text only" : "";
    $("drop").querySelector("p").innerHTML =
      `<span class="filechip">${esc(currentDoc.source)}</span> `
      + `<span style="color:var(--ink-2)">read${esc(note)}. The text below is what an ATS sees — edit it and the score follows.</span>`;
    if (($("resume").value || "").trim() && ($("jd").value || "").trim()) runScreen(false);
  } catch (e) {
    currentDoc = null;
    err.hidden = false;
    err.textContent = e.message || String(e);
  }
}

// ================================================================ events ===
const EXAMPLE_RESUME = `Joshua Bleechington
Denver, CO | josh@example.com | (555) 010-2233
linkedin.com/in/example | github.com/example

PROFESSIONAL SUMMARY
Security analyst with hands-on experience in vulnerability management, threat
hunting, and identity monitoring across cloud and hybrid environments.

TECHNICAL SKILLS
Splunk, Microsoft Sentinel, Entra ID, Tenable, Wireshark, Python, PowerShell, KQL,
NIST CSF, ISO 27001, MITRE ATT&CK, Azure, incident response

PROFESSIONAL EXPERIENCE

Security Analyst | Contoso Financial | Mar 2022 - Present
- Led vulnerability management program across 1,200 endpoints, reducing critical
  findings by 63% in nine months.
- Built threat hunting playbooks in Microsoft Sentinel using KQL, uncovering 14
  previously undetected Tor-based exfiltration attempts.
- Responsible for weekly reporting to the security manager.

IT Support Specialist | Northwind Health | Jun 2019 - Feb 2022
- Administered Active Directory and Entra ID accounts for 800 users.
- Assisted with endpoint patching and remediation tickets.

EDUCATION
B.S. Information Technology, Metro State University, 2019

CERTIFICATIONS
CISSP, CompTIA Security+`;

const EXAMPLE_JD = `Cybersecurity Analyst II

About Us
Contoso is a leading financial services firm. We are an equal opportunity employer
and offer competitive salary, 401k matching, dental and vision insurance, and
unlimited PTO.

Responsibilities
- Monitor and triage security alerts in Splunk Enterprise Security and escalate
  confirmed incidents.
- Lead incident response investigations end to end, including containment and
  root cause analysis.
- Perform threat hunting across endpoint and network telemetry using MITRE ATT&CK.
- Run the vulnerability management lifecycle with Tenable, tracking remediation SLAs.
- Support cloud security posture management in AWS.

Minimum Qualifications
- Bachelor's degree in Computer Science, Information Security, or related field.
- Minimum of 4 years of experience in a security operations center.
- Must have hands-on experience with SIEM platforms, required expertise in Splunk.
- Strong knowledge of incident response and digital forensics.
- Experience with Python scripting for automation.
- Familiarity with NIST CSF and ISO 27001.

Preferred Qualifications
- CISSP or GCIH certification preferred.
- Experience with SOAR platforms and playbook automation is a plus.
- Kubernetes security experience is nice to have.
- Terraform and infrastructure as code a plus.

Benefits
We offer stock options, remote flexibility, and a generous 401k.`;

renderTicks();
updateStats();

$("run").addEventListener("click", () => runScreen(false));
$("resume").addEventListener("input", () => { currentDoc = null; scheduleRerun(); });
$("jd").addEventListener("input", scheduleRerun);

$("example").addEventListener("click", () => {
  currentDoc = null;
  lastTotal = null;
  $("resume").value = EXAMPLE_RESUME;
  $("jd").value = EXAMPLE_JD;
  updateStats();
  runScreen(false);
});

$("clear").addEventListener("click", () => {
  currentDoc = null; lastTotal = null; lastReport = null; tailored = null;
  $("tailor-output").classList.add("gone");
  $("tailor-delta").classList.add("gone");
  $("resume").value = ""; $("jd").value = "";
  $("readout").classList.remove("on");
  $("live-note").hidden = true;
  $("file-err").hidden = true;
  $("delta").textContent = "";
  $("drop").querySelector("p").innerHTML =
    'Drop a <code>.docx</code>, <code>.pdf</code> or <code>.txt</code> here — or just paste below.'
    + '<br>A <code>.docx</code> also gets the full layout audit.';
  updateStats();
  $("resume").focus();
});

$("tailor-run").addEventListener("click", () => {
  if (!lastReport) return;
  renderTailored(lastReport);
  $("tailor-output").scrollIntoView({ behavior: "smooth", block: "nearest" });
});

$("tailor-copy").addEventListener("click", async () => {
  const box = $("tailored");
  const note = $("tailor-note");
  try {
    await navigator.clipboard.writeText(box.value);
    note.className = "save-note";
    note.textContent = "Copied. Paste into Word or Google Docs, then export to PDF if asked.";
  } catch (e) {
    // Clipboard permission varies by host; selecting the text always works.
    box.focus();
    box.select();
    note.className = "save-note";
    note.textContent = "Selected — press Ctrl+C (or Cmd+C) to copy.";
  }
});

$("tailor-save").addEventListener("click", saveTailoredDocx);

$("browse").addEventListener("click", () => $("file").click());
$("file").addEventListener("change", (e) => { if (e.target.files[0]) loadFile(e.target.files[0]); });

const drop = $("drop");
["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => {
  e.preventDefault(); drop.classList.add("over");
}));
["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => {
  e.preventDefault(); drop.classList.remove("over");
}));
drop.addEventListener("drop", (e) => {
  if (e.dataTransfer.files && e.dataTransfer.files[0]) loadFile(e.dataTransfer.files[0]);
});

if (typeof pdfjsLib !== "undefined") {
  try {
    pdfjsLib.GlobalWorkerOptions.workerSrc =
      "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";
  } catch (e) { /* falls back to main-thread parsing */ }
}

// The save button appears only when this view can actually run a save.
if (window.claude && typeof window.claude.use === "function") {
  window.claude.use("downloads").then((ns) => {
    if (!ns) return;
    downloads = ns;
    $("tailor-save").classList.remove("gone");
  }).catch(() => { /* absent is the normal case; the copy panel covers it */ });
}
