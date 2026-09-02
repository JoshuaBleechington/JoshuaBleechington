# resume-ats

Score a resume against a job description the way an applicant tracking system
would, and get back a ranked list of what to fix.

Most "ATS checkers" count keywords. Keyword gaps are real, but they are not the
most common reason an application dies. A resume laid out in a two-column
template, or with contact details in the page header, can be a perfect match on
paper and still reach the recruiter as scrambled fragments. This tool checks
that first, then the keywords, then whether those keywords appear in
demonstrated work rather than in a keyword blob.

```
$ resume-ats score resume.docx job-posting.txt
```

## What it checks

| Component | Weight | What it measures |
|---|---:|---|
| `parseability` | 22 | Can an ATS read the file at all — columns, tables, text boxes, headers, images, fonts, sections, dates, contact fields |
| `keywords` | 30 | Weighted coverage of terms mined from the posting, with alias and acronym resolution |
| `context` | 14 | Whether requirements are evidenced in real bullets, not just listed |
| `title` | 10 | Overlap between your job titles and the requisition title |
| `experience` | 10 | Years evidenced by your date ranges against the stated minimum (a threshold, so exceeding it is a full pass) |
| `education` | 6 | Degree level and certifications against stated minimums |
| `writing` | 8 | Quantified results, strong action verbs, bullet hygiene |

**Hard requirements are a gate, not a weight.** A stated minimum — years,
degree, clearance — that your resume does not evidence *caps* the total score,
because that is how a knockout question behaves. No amount of keyword coverage
compensates for a missing mandatory credential.

## Install

The scorer runs on the standard library alone. PDF resumes need one reader:

```bash
git clone https://github.com/JoshuaBleechington/JoshuaBleechington.git
cd JoshuaBleechington
pip install -e ".[pdf]"      # or: pip install pdfminer.six
```

Without installing, run it straight from the repository:

```bash
python -m resume_ats score resume.docx job.txt
```

`.docx`, `.pdf`, `.txt` and `.md` are supported. `.doc`, `.rtf` and `.pages` are
rejected with an explanation — they are not formats an ATS reliably parses, so
the honest answer is to re-save the file.

## Commands

### `score` — the main event

```bash
resume-ats score resume.docx job.txt
resume-ats score resume.docx job.txt --format html -o report.html
resume-ats score resume.pdf --jd-text "$(pbpaste)"      # posting from clipboard
resume-ats score resume.docx job.txt --min-score 70      # exit 2 if below
```

Formats: `text` (default), `markdown`, `json`, `html`. The HTML report is a
single self-contained file with no external assets, so it opens offline and
prints cleanly.

### `audit` — format check, no posting needed

```bash
resume-ats audit resume.docx
```

Answers one question: can a parser read this file? Run it once on your base
resume and fix everything before you tailor anything. Exits `2` if there are
blockers.

### `keywords` — see what the posting actually asks for

```bash
resume-ats keywords job.txt --top 40
```

Shows the mined terms with their weights and whether they came from a required
or preferred block. Useful for sanity-checking the tool's reading of a posting
before you trust its gaps.

### `tailor` — rebuild the resume as an ATS-aligned Word document

```bash
resume-ats tailor resume.docx job.txt -o tailored.docx
resume-ats tailor resume.docx job.txt -o tailored.txt        # plain text instead
resume-ats tailor resume.docx job.txt --headline "VP, Solutions" -o out.docx
```

Applies the findings from `score` that can be applied mechanically, and writes
a `.docx` with no third-party dependency.

**What it changes.** It repairs layout damage (symbol-font bullets, tab
pseudo-columns, repeated page banners, a cover letter bound into the file),
rebuilds the document single-column with standard headings, native Word bullets
and dates on the title line, sets a headline to the posting's title, and adds
the posting's wording for a skill your resume already evidences under a
different name — "solution consulting" where your resume says "presales".
Where the two names are an acronym and its expansion, it writes both —
`SIEM (Security Information and Event Management)` — because two postings
routinely search for opposite halves of the same pair. Competencies are ordered
so the terms this posting weights most heavily come first.

**What it will not change.** It never writes an achievement, number, employer,
credential or skill you did not write yourself. A tool that invents "increased
revenue 40%" because a posting asked for revenue growth produces a document you
have to defend in an interview. Terms the posting wants and your resume shows
no evidence of are reported to *you*, separately, and never appear in the file.

**Working across many postings.**

```bash
resume-ats tailor resume.docx --jobs postings/ --outdir applications/
```

Writes one tailored `.docx` per posting plus a `-notes.md` working list for
each, and ranks them so you know which to apply to first:

```
posting                       before  after  band
wns_vp_procurement              78.2   88.4  Strong
zones_practice_director         77.6   84.9  Good
accenture_strategy_principal    70.7   78.4  Good
```

**The working list (`--notes`).** The one thing the tool cannot do is write
your accomplishments. What it can do is tell you exactly where the holes are:
which stated requirements have no counterpart anywhere in your resume, which
keywords the posting leans on hardest and the sentence each appears in, and
which of your bullets carry no numbers. Every entry is a prompt to answer from
your own history. The file is for you and is never part of the document you
send.

**When it refuses.** Tailoring can only rearrange what came out of the file. If
the source is a graphic-led layout whose dates and headings never became text,
the rebuild would be faithful to a parse that already lost most of the resume,
so the command stops and asks for a readable source instead of confidently
producing something worse. `--force` overrides this.

```
Score against this posting: 77.2 -> 90.7

CHANGES APPLIED
  [layout] 54 bullet(s) used a symbol font that exports as a stray letter...
  [terminology] Added the posting's wording for skills the resume already
      evidences under another name: Solution Consulting, Deal Shaping, CXO, OEM.

ONLY YOU CAN DO THESE (deliberately not written into the file)
  - The posting asks for these and the resume shows no evidence of them...
  - Your current role has no numbers in any of its 7 bullets...
```

### `compare` — rank your drafts

```bash
resume-ats compare v1.docx v2.docx v3.docx --jd job.txt
resume-ats tailor resume.docx job.txt -o tailored.docx
```

This is the intended workflow: change one thing, re-score, keep what helped.

## Use it as a library

```python
from resume_ats import score_text, score_files

report = score_text(resume_text, job_description_text)
print(report.total, report.band)

for match in report.missing(10):
    print(match.requirement.display, match.requirement.weight)

for step in report.suggestions:
    print(step)
```

`score_files(resume_path, jd_path)` does the same from disk. Every renderer in
`resume_ats.report` takes the `ScoreReport` object.

## How the matching works

**Alias resolution.** `CISSP` and `Certified Information Systems Security
Professional` are the same credential; `Azure AD` and `Entra ID` are the same
product. The lexicon in `resume_ats/data/aliases.json` maps roughly 120 surface
forms onto canonical terms. Add your own field's vocabulary there, or pass
`--aliases my-terms.json` to merge a file in.

**Three matching signals, deliberately not merged into one.**

- *Exact and alias matches* — what a boolean recruiter search does.
- *Fuzzy matches* — scored lower on purpose. A literal string index does not
  credit a paraphrase, so a near miss is reported as a near miss, with the
  posting's exact wording to copy.
- *BM25 and TF-IDF cosine* — Okapi BM25 is the ranking function behind the
  Lucene indexes many ATS products search over, so ranking the resume the same
  way approximates where it lands in a recruiter's result list rather than just
  whether a word is present.

**Noise filtering.** Terms are mined only from responsibility and requirement
blocks. Benefits, EEO statements and company blurbs are excluded, so the tool
never tells you to add `401k` or `equal opportunity employer` to your resume. The hiring company's own name is excluded too, unless it is also a product you could genuinely have used.
Requirement language (`must have`, `minimum`, `expertise in`) is stripped from
phrases, and fragments that only ever appear inside a stronger term are
suppressed, so `security operations center` is reported once rather than as
four overlapping gaps.

## Reading the score

| Band | Score | Meaning |
|---|---:|---|
| Strong | 85+ | Competitive on keyword screening |
| Good | 70–84 | Likely to clear automated filters |
| Borderline | 55–69 | Could go either way |
| Weak | 40–54 | Likely filtered out |
| Poor | <40 | Very unlikely to reach a human |

**These bands are calibrated judgement, not measurement.** No ATS vendor
publishes its thresholds, behaviour differs between products and between
customers of the same product, and most postings are also screened by a human
who is not running any of this. Use the score to compare drafts of your own
resume against one posting — the *direction* of change is the reliable signal.
Treat the missing-keyword list and the parsing audit as the real output; the
number is a summary of them.

## A note on keyword stuffing

The tool rewards putting a keyword inside a real accomplishment bullet and
explicitly discounts terms that appear only in a skills list. That is not
moralising, it is scoring what actually works: mainstream systems extract text
without styling, so hidden white-text keyword blocks show up plainly in the
recruiter's view, and increasingly the second-stage screen is a language model
being asked whether the experience is real. Claiming skills you do not have
fails at the interview at best, so the tool is built to help you surface work
you actually did in the words the posting uses.

## Output formats

`tailor` writes `.docx` (or `.txt`/`.md` by extension). For a posting that wants
a PDF, export from Word after opening the `.docx` — with one thing to check:
**the bullets must survive as text.** A PDF whose bullets are drawn by the
layout engine rather than written as characters extracts as unstructured prose,
and every quantified achievement stops reading as an accomplishment. Run
`resume-ats audit resume.pdf` on the exported file; if the writing score
collapses and the audit reports no bullet points, the export dropped them.

## Development

```bash
python -m pytest tests -q
```

128 tests cover extraction, section parsing, requirement mining, matching
precision, the parsing audit, scoring behaviour, document generation and the
CLI. The tailoring tests pin the integrity guarantees hardest: no invented
numbers, no unevidenced skills in the file, and advice to the candidate never
leaking into the document sent to an employer.

Module map:

| Module | Responsibility |
|---|---|
| `text.py` | Normalization, tokenization, stemming, n-grams |
| `aliases.py` | Canonical skill lexicon and alias resolution |
| `extract.py` | File → text plus layout fingerprint (`.docx` read directly from its XML) |
| `resume.py` | Sections, contact fields, roles, dates, bullets |
| `jd.py` | Posting → weighted requirements and hard gates |
| `match.py` | Exact/alias/fuzzy matching, BM25, TF-IDF cosine |
| `parseability.py` | The ATS-readability audit |
| `score.py` | Component weights, gates, suggestions |
| `tailor.py` | Rebuilds a resume as an ATS-aligned document |
| `docx_writer.py` | Minimal stdlib OOXML writer (no dependencies) |
| `report.py` | Terminal, Markdown, JSON, HTML renderers |
| `cli.py` | Argument parsing and subcommands |

## Also here

`samples/ats_safe_template.md` — a resume skeleton built to survive parsing,
with the reasoning for each rule.
