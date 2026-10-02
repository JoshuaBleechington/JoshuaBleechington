# ATS-safe resume template

Copy this structure into Word or Google Docs as **plain body text**. Everything
here is chosen because it survives parsing, not because it looks impressive in
a preview pane.

## Non-negotiable rules

1. **One column.** No side panels, no "skills sidebar". Parsers read straight
   across the page and interleave columns into nonsense.
2. **No tables, no text boxes, no headers/footers.** Text boxes are usually
   skipped entirely; header/footer content is routinely discarded before
   parsing. Your contact details belong in the body of page one.
3. **No graphics carrying information.** Skill rating bars, icons and logos
   extract as nothing. If a fact only exists inside an image, it does not exist.
4. **Standard section headings**, spelled the boring way: `Summary`,
   `Skills`, `Experience`, `Education`, `Certifications`.
5. **A date range on the same line as every job title**, in one consistent
   format: `Mar 2022 - Present` or `2019 - 2022`.
6. **Export as .docx**, or a PDF saved directly from your editor. Never a scan,
   a photo, or a "print to image" PDF.
7. **Standard fonts** (Calibri, Arial, Georgia, Times). No symbol fonts, no
   letter-spacing typed as `E X P E R I E N C E`.

## The skeleton

```
Firstname Lastname
City, ST | you@example.com | (555) 010-2233
linkedin.com/in/your-handle | github.com/your-handle

SUMMARY
One or two lines naming the role you are targeting, your years of experience,
and your two strongest, most relevant capabilities. Use the posting's own job
title here if it is close to yours.

SKILLS
Group them plainly, comma separated, using the exact words the posting uses:
Tools: Splunk, Microsoft Sentinel, CrowdStrike, Tenable
Cloud: AWS, Azure, Entra ID
Frameworks: NIST CSF, ISO 27001, MITRE ATT&CK
Languages: Python, PowerShell, KQL, SQL

EXPERIENCE

Job Title | Company Name | Mar 2022 - Present
- Action verb + what you did + the tool you used + the measured result.
- Led vulnerability management across 1,200 endpoints, cutting critical
  findings 63% in nine months.
- Built threat hunting playbooks in Microsoft Sentinel using KQL, surfacing 14
  previously undetected exfiltration attempts.

Job Title | Company Name | Jun 2019 - Feb 2022
- Administered Entra ID and Active Directory for 800 users across three sites.
- Automated patch remediation with PowerShell, reducing mean time to patch
  from 21 days to 6.

EDUCATION
B.S. Information Technology | Metro State University | 2019

CERTIFICATIONS
CISSP | CompTIA Security+ | 2023
```

## Writing the bullets

Every bullet should survive this test: **verb, object, tool, number.**

- Weak: `Responsible for vulnerability management.`
- Strong: `Led vulnerability management across 1,200 endpoints with Tenable,
  cutting critical findings 63% in nine months.`

The strong version scores better on every axis this tool measures: it opens
with an action verb, it quantifies, and it places the keyword
(`vulnerability management`, `Tenable`) inside demonstrated work rather than a
keyword list.

## Spell out acronyms once

Write `Security Information and Event Management (SIEM)` the first time. A
keyword index matches literal strings, and different postings search for
different halves of that pair. The same goes for
`Certified Information Systems Security Professional (CISSP)`.

## What not to do

Do not paste hidden keywords in white text, in a 1pt font, or behind an image.
Every mainstream ATS extracts text without styling, so the recruiter sees a
block of unrelated keywords in the plain-text view, and it reads exactly like
what it is. It is one of the few things that reliably gets an application
discarded outright.
