/* ATS scoring engine - browser port of the resume_ats Python package.
   Same weights, same mining rules, same gates. Kept in one file so the page
   runs with no build step and no network calls. */

// ---------------------------------------------------------------- text ----
/* Includes the dingbat arrows, checks, diamonds and squares that word
   processors offer in the bullet gallery -- a resume using any of them read
   as having no bullets at all, which cost it the whole writing component. */
const BULLET_CLASS = "\\-\u2022\u2023\u25aa\u25cf\u25e6\u2043\u2219\u00b7\u2027\u2013\u2014*+>"
  + "\u25ab\u25a0\u25a1\u25fe\u25c6\u25c7\u2666\u25b8\u25b9\u25b6\u25b7\u00bb\u203a"
  + "\u27a2\u27a4\u27a3\u2794\u2192\u21d2\u2713\u2714\u2751\u2756\u274b\u2726\u2727\u2605\u2606\u2731";
const BULLET_RE = new RegExp("^[\\s" + BULLET_CLASS + "]{0,6}[" + BULLET_CLASS + "]\\s+");
const TOKEN_RE = /[a-z0-9][a-z0-9+#&./_-]*/g;
const EDGE_TRIM = /^[./\-_&]+|[./\-_&]+$/g;

const STOPWORDS = new Set(`
a about above across after again against all almost along already also although always am among an and
another any anyone anything are around as at be because been before being below best better between both
but by can cannot could day did do does doing done down due during each either else enough etc even ever
every everyone excellent experience few for from further get give go good great had has have having he her
here hers herself him himself his how however i if in including into is it its itself just keep least less
let like ll made make many may me might more most much must my myself need needs neither never new next no
nor not nothing now of off often on once one only or other others otherwise ought our ours ourselves out
over own per perhaps please plus proven quite rather re really same seem several shall she should since so
some someone something strong such sure than that the their theirs them themselves then there these they
thing things this those though through throughout thus to together too toward towards under unless until
up upon us use used using various very via was way we well were what whatever when where whether which while
who whom whose why will with within without would year years yet you your yours yourself
ability able across additional adept applicant applicants apply candidate candidates company duties employee
employer employment ideal include includes join looking opportunity position responsibilities role seeking
successful team teams work working workplace
`.trim().split(/\s+/));

const KEEP_IN_PHRASE = new Set(["in", "of", "and", "as", "on", "for", "to"]);

const PUNCT_MAP = {
  "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201c": '"', "\u201d": '"', "\u201e": '"',
  "\u00a0": " ", "\u200b": "", "\ufeff": "",
  "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-", "\u2015": "-",
  "\u2212": "-",
};

function normalize(text) {
  if (!text) return "";
  let s = text.normalize("NFKC").replace(/[\u2018\u2019\u201a\u201c\u201d\u201e\u00a0\u200b\ufeff\u2010\u2011\u2012\u2013\u2014\u2015\u2212]/g,
    (c) => (c in PUNCT_MAP ? PUNCT_MAP[c] : c));
  s = s.normalize("NFKD").replace(/\p{M}/gu, "");
  return s.toLowerCase();
}

const SUFFIXES = [["ies", "y"], ["sses", "ss"], ["ches", "ch"], ["shes", "sh"], ["xes", "x"],
                  ["ing", ""], ["ed", ""], ["s", ""]];

function stem(token) {
  if (token.length <= 4 || !/^[a-z]+$/.test(token)) return token;
  // A word ending in -ss keeps it: stripping the final s gave "proces" for
  // "process" while "processes" reduced to "process", so a singular and its
  // own plural stopped matching.
  if (token.endsWith("ss")) return token;
  for (const [suffix, repl] of SUFFIXES) {
    if (token.endsWith(suffix) && token.length - suffix.length + repl.length >= 3) {
      return token.slice(0, token.length - suffix.length) + repl;
    }
  }
  return token;
}

function rawTokens(text) {
  const out = [];
  const matches = normalize(text).match(TOKEN_RE);
  if (!matches) return out;
  for (const m of matches) {
    const t = m.replace(EDGE_TRIM, "");
    if (t) out.push(t);
  }
  return out;
}

function tokenize(text, keepStopwords) {
  const out = [];
  for (const t of rawTokens(text)) {
    if (!keepStopwords && STOPWORDS.has(t)) continue;
    out.push(t);
  }
  return out;
}

const stems = (text) => tokenize(text).map(stem);
const canonical = (phrase) => tokenize(phrase).map(stem).join(" ");

const SEGMENT_RE = /[,;:()\[\]{}<>|\u2022]|\s+\/\s+|\s-\s|(?<=[.!?])\s/;
const segments = (text) => normalize(text).split(SEGMENT_RE).map((s) => (s || "").trim()).filter(Boolean);

function* phraseNgrams(text, lo, hi) {
  for (const segment of segments(text)) {
    const toks = [];
    const matches = segment.match(TOKEN_RE);
    if (matches) for (const m of matches) { const t = m.replace(EDGE_TRIM, ""); if (t) toks.push(t); }
    for (let size = lo; size <= hi; size++) {
      for (let i = 0; i + size <= toks.length; i++) {
        const gram = toks.slice(i, i + size);
        if (STOPWORDS.has(gram[0]) || STOPWORDS.has(gram[gram.length - 1])) continue;
        if (gram.some((t) => STOPWORDS.has(t) && !KEEP_IN_PHRASE.has(t))) continue;
        yield gram.join(" ");
      }
    }
  }
}

const isBullet = (line) => BULLET_RE.test(line);
const stripBullet = (line) => line.replace(BULLET_RE, "").trim();

/* difflib-style similarity, approximated with a longest-common-subsequence
   ratio. Used only for single-word typo detection above 0.86. */
function similarity(a, b) {
  if (!a.length || !b.length) return 0;
  const prev = new Array(b.length + 1).fill(0);
  let cur = new Array(b.length + 1).fill(0);
  for (let i = 1; i <= a.length; i++) {
    cur = new Array(b.length + 1).fill(0);
    for (let j = 1; j <= b.length; j++) {
      cur[j] = a[i - 1] === b[j - 1] ? prev[j - 1] + 1 : Math.max(prev[j], cur[j - 1]);
    }
    for (let j = 0; j <= b.length; j++) prev[j] = cur[j];
  }
  return (2 * prev[b.length]) / (a.length + b.length);
}

/* Glyphs a symbol font (Wingdings, Symbol) leaves behind when a decorative
   bullet is exported. A Wingdings checkmark becomes a literal u-umlaut, so a
   whole resume of bullets arrives as prose and no parser sees one. */
const BROKEN_BULLETS = "\u00fc\u00a7\u00d8\u00fe\u00a4\u00a8";
const BROKEN_BULLET_RE = new RegExp("^([ \\t]*)[" + BROKEN_BULLETS + "]([ \\t]+|(?=[A-Z]))");
const LONE_BROKEN_RE = new RegExp("^[ \\t]*[" + BROKEN_BULLETS + "][ \\t]*$");
/* Word writes Symbol- and Wingdings-font bullets into the private use area.
   U+F0B7 is the default Word bullet; extractors hand it straight through, and
   nothing downstream recognises it. The whole block is symbol-font output, so
   any of it at the head of a line is a bullet, never a word. */
const PUA_BULLET_RE = /^([ \t]*)[\uf020-\uf0ff]+([ \t]+|(?=[A-Z(]))/;
/* A second-level Word bullet exports as a bare lowercase "o". Only treated as
   a marker when the document does it more than once, so a line that genuinely
   opens with the word is left alone. */
const WORD_O_RE = /^([ \t]*)o([ \t]+)(?=[A-Z(])/;

function isLetterSpaced(line) {
  const s = line.trim();
  if (s.length < 7) return false;
  if (/^(?:[A-Za-z]\s){3,}[A-Za-z]$/.test(s)) return true;
  const parts = s.split(/\s+/);
  if (parts.length < 5) return false;
  const short = parts.filter((p) => p.length <= 2 && /^[a-z]+$/i.test(p)).length;
  return short / parts.length >= 0.6;
}

function repairLayout(text) {
  const notes = [];
  const out = [];
  let broken = 0, pua = 0;
  const lines = text.split("\n");
  // "o" is only a marker if the document uses it as one repeatedly.
  const wordO = lines.filter((raw) => WORD_O_RE.test(raw)).length;
  const useWordO = wordO >= 2;
  for (const raw of lines) {
    if (LONE_BROKEN_RE.test(raw)) { broken++; continue; }
    let line = raw;
    if (PUA_BULLET_RE.test(line)) { pua++; line = line.replace(PUA_BULLET_RE, "$1- "); }
    else if (useWordO) line = line.replace(WORD_O_RE, "$1- ");
    if (BROKEN_BULLET_RE.test(line)) { broken++; line = line.replace(BROKEN_BULLET_RE, "$1- "); }
    out.push(line);
  }
  if (broken) {
    notes.push(broken + " bullet(s) used a symbol font that exports as a stray letter, "
      + "so no parser would have recognised them as bullets");
  }
  if (pua) {
    notes.push(pua + " bullet(s) came through as a private-use symbol-font character "
      + "(Word's default bullet does this), which reads as an unprintable box "
      + "rather than a list marker");
  }
  if (useWordO) {
    notes.push(wordO + " second-level bullet(s) exported as a bare letter \"o\" "
      + "instead of a list marker");
  }
  return [out.join("\n"), notes];
}
const ALIAS_DATA = {"certifications":{"cissp":["certified information systems security professional"],"cisa":["certified information systems auditor"],"cism":["certified information security manager"],"ccsp":["certified cloud security professional"],"crisc":["certified in risk and information systems control"],"security+":["sec+","comptia security+","comptia security plus","security plus"],"network+":["comptia network+","net+"],"cysa+":["comptia cysa+","cybersecurity analyst+"],"oscp":["offensive security certified professional"],"ceh":["certified ethical hacker"],"gcih":["giac certified incident handler"],"gsec":["giac security essentials"],"gcia":["giac certified intrusion analyst"],"pmp":["project management professional"],"az-500":["azure security engineer associate","microsoft certified azure security engineer"],"sc-200":["security operations analyst associate"],"aws certified security":["aws security specialty","aws certified security specialty"],"cka":["certified kubernetes administrator"]},"security":{"siem":["security information and event management","security information event management"],"soar":["security orchestration automation and response","security orchestration and automation"],"edr":["endpoint detection and response"],"xdr":["extended detection and response"],"mdr":["managed detection and response"],"dlp":["data loss prevention","data leak prevention"],"iam":["identity and access management","identity access management"],"pam":["privileged access management","privileged account management"],"sso":["single sign on","single sign-on"],"mfa":["multi factor authentication","multifactor authentication","two factor authentication","2fa"],"rbac":["role based access control"],"zero trust":["zero trust architecture","zta","zero trust network access","ztna"],"soc":["security operations center","security operations centre"],"ir":["incident response","incident handling"],"threat hunting":["threat hunt","proactive threat detection"],"threat intelligence":["cti","cyber threat intelligence","threat intel"],"vulnerability management":["vuln management","vulnerability remediation","patch management"],"penetration testing":["pen testing","pentest","pentesting","ethical hacking"],"mitre att&ck":["mitre attack","att&ck framework","attck"],"casb":["cloud access security broker"],"waf":["web application firewall"],"ids/ips":["intrusion detection system","intrusion prevention system","ids","ips"],"pki":["public key infrastructure"],"grc":["governance risk and compliance","governance risk compliance"],"tprm":["third party risk management","vendor risk management"],"dfir":["digital forensics and incident response","digital forensics"],"opsec":["operational security"],"appsec":["application security"],"devsecops":["dev sec ops","secure devops"],"sast":["static application security testing","static analysis"],"dast":["dynamic application security testing"],"sca":["software composition analysis"],"cspm":["cloud security posture management"],"cnapp":["cloud native application protection platform"],"sbom":["software bill of materials"],"ueba":["user and entity behavior analytics","uba"]},"frameworks":{"nist csf":["nist cybersecurity framework","cybersecurity framework"],"nist 800-53":["nist sp 800-53","800-53"],"nist 800-171":["nist sp 800-171","800-171"],"nist ai rmf":["nist ai risk management framework","ai rmf"],"iso 27001":["iso/iec 27001","iso27001"],"iso 42001":["iso/iec 42001","iso42001"],"soc 2":["soc2","soc ii","service organization control 2"],"pci dss":["pci-dss","pci"],"hipaa":["health insurance portability and accountability act"],"gdpr":["general data protection regulation"],"fedramp":["federal risk and authorization management program"],"cmmc":["cybersecurity maturity model certification"],"cis benchmarks":["cis controls","center for internet security benchmarks"],"eu ai act":["european union ai act","ai act"],"sox":["sarbanes oxley","sarbanes-oxley"]},"tools":{"splunk":["splunk enterprise security","splunk es","spl"],"microsoft sentinel":["azure sentinel","sentinel"],"crowdstrike":["crowdstrike falcon","falcon"],"defender":["microsoft defender","defender for endpoint","mde","defender for cloud"],"entra id":["azure ad","azure active directory","aad","microsoft entra"],"active directory":["ad ds","windows active directory"],"okta":["okta workforce identity"],"qualys":["qualys vmdr"],"tenable":["nessus","tenable.io","tenable.sc"],"rapid7":["insightvm","nexpose"],"wireshark":["packet capture","pcap analysis"],"burp suite":["burpsuite","burp"],"metasploit":["msf"],"nmap":["network mapper"],"servicenow":["snow","service now"],"jira":["atlassian jira"],"terraform":["hashicorp terraform","iac terraform"],"kubernetes":["k8s","eks","aks","gke"],"docker":["containerization","containers"],"ansible":["red hat ansible"],"elastic":["elk stack","elasticsearch","elk"],"powershell":["power shell","ps1"],"kql":["kusto query language"],"sql":["structured query language","t-sql","mysql","postgresql"],"python":["python3"],"git":["github","gitlab","version control"],"ci/cd":["cicd","continuous integration","continuous delivery","continuous deployment","jenkins","github actions"],"aws":["amazon web services"],"azure":["microsoft azure"],"gcp":["google cloud platform","google cloud"],"linux":["unix","rhel","ubuntu","centos"],"vmware":["vsphere","esxi"],"sccm":["mecm","configuration manager","intune"]},"general":{"stakeholder management":["stakeholder engagement"],"risk assessment":["risk analysis","risk evaluation"],"root cause analysis":["rca"],"kpi":["key performance indicator","metrics reporting"],"sla":["service level agreement"],"agile":["scrum","kanban","sprint"],"documentation":["technical writing","runbook","playbook","sop","standard operating procedure"],"machine learning":["ml","deep learning"],"artificial intelligence":["ai","genai","generative ai","llm","large language model"],"data analysis":["data analytics","analytics"],"project management":["program management","pmo"],"business continuity":["bcp","disaster recovery","dr","bcdr"],"change management":["change control"],"audit":["auditing","internal audit","control testing"],"policy development":["policy writing","standards development"],"training":["security awareness training","user training","mentoring"]},"it_services":{"presales":["pre-sales","pre sales","presales engagement","solution consulting","sales engineering"],"solutioning":["solution design","solution development","solution architecture","solution shaping","deal shaping"],"managed services":["managed service","mps","managed services provider","msp"],"it outsourcing":["ito","outsourcing","infrastructure outsourcing","application outsourcing","ado"],"bpo":["business process outsourcing"],"tcv":["total contract value"],"acv":["annual contract value"],"arr":["annual recurring revenue"],"mrr":["monthly recurring revenue"],"rfp":["request for proposal","rfx","rfi","request for information","bid response"],"bid management":["bid manager","pursuit management","deal pursuit","pursuit lead","capture management"],"deal desk":["commercial constructs","pricing strategy","deal review"],"statement of work":["sow","msa","master service agreement","master services agreement"],"go to market":["gtm","go-to-market","route to market"],"account management":["account director","client partner","account governance","account planning"],"client relationship management":["client relations","customer relationship management","trusted advisor"],"consultative selling":["solution selling","value selling","challenger sale"],"service management":["itsm","it service management","service delivery management"],"service integration":["siam","service integration and management","multi-sourcing service integration"],"itil":["itil v3","itil v4","itil foundation","itil trained","itil certified"],"digital transformation":["business transformation","transformation program","transformation initiatives"],"change management":["organizational change management","ocm","change enablement","change adoption"],"process improvement":["continuous improvement","process optimization","process reengineering","business process reengineering","bpr","process standardization"],"program management":["programme management","pmo","portfolio management"],"p&l":["profit and loss","p and l","pnl","budget ownership"],"cxo":["c-suite","c suite","executive stakeholders","cio","cto","cfo","ciso"],"stakeholder management":["stakeholder engagement"],"net promoter score":["nps","customer satisfaction","csat"],"service level agreement":["sla","slas","kpi","key performance indicator"],"hyperscaler":["hyperscalers","cloud service provider","csp"],"cloud migration":["journey to cloud","cloud adoption","lift and shift","application modernization","app modernization"],"workplace services":["digital workplace","end user computing","euc","modern workplace"],"oem":["original equipment manufacturer","oems","alliances","partner ecosystem","channel partners"],"revenue growth":["revenue attainment","quota attainment","bookings","signings","pipeline development"],"cross sell":["cross-sell","upsell","up-sell","account expansion"],"delivery excellence":["service improvement plan","sip","back to green","account turnaround","remediation plan"],"shared services":["center of excellence","coe","centre of excellence"],"vendor management":["supplier management","third party management","procurement"],"business case":["value proposition","roi","return on investment","tco","total cost of ownership"],"sales enablement":["enablement","sales training","sales coaching","field enablement","seller enablement","sales readiness"],"cross functional leadership":["cross-functional leadership","cross functional teams","cross-functional teams","cross functional collaboration","cross-functional","matrix leadership"],"business planning":["account planning","strategic business plans","business plans","strategic planning","growth planning"],"strategic partners":["partner relationships","partner ecosystem","alliance partners","technology partners","joint go to market","partner strategy"],"practice leadership":["practice","practice management","capability leadership","service line leadership","practice director"],"executive leadership":["executive presence","executive communication","c-suite engagement","executive stakeholder management"],"operating model":["target operating model","tom","tom design","operating model design","org design"],"commercial acumen":["commercial constructs","commercial management","pricing strategy","deal economics","commercial strategy"],"business development":["new logo acquisition","new logo","revenue growth","bookings growth","signings growth","pipeline development"],"technology consulting":["it consulting","technology advisory","advisory services","management consulting"],"thought leadership":["industry forums","conference speaking","white papers","published articles"],"solution reviews":["solution review","deal reviews","design reviews","architecture reviews","bid reviews"],"technical resources":["solution architects","technical teams","technical staff","architects","engineering teams"],"customer workshops":["client workshops","discovery workshops","design workshops"],"mentoring":["coaching","mentorship","talent development","people development"]},"business_certs":{"mba":["master of business administration"],"pmp":["project management professional"],"prince2":["prince 2"],"six sigma":["lean six sigma","black belt","green belt"],"togaf":["the open group architecture framework"],"safe":["scaled agile framework","safe agilist"],"aws cloud practitioner":["aws certified cloud practitioner"],"azure fundamentals":["az-900"]}};

// ------------------------------------------------------------- lexicon ----
class SkillLexicon {
  constructor(mapping) {
    this.canonByKey = new Map();
    this.surfacesMap = new Map();
    this.categoryMap = new Map();
    for (const [category, entries] of Object.entries(mapping)) {
      if (category.startsWith("_")) continue;
      for (const [term, alts] of Object.entries(entries)) this.add(term, alts || [], category);
    }
  }
  add(term, alts, category) {
    if (!this.surfacesMap.has(term)) this.surfacesMap.set(term, []);
    this.categoryMap.set(term, category || "custom");
    const surfaces = this.surfacesMap.get(term);
    for (const form of [term, ...alts]) {
      const key = canonical(form);
      if (!key) continue;
      // A multi-word alias that collapses to one token has lost its meaning to
      // stopword stripping ("security plus" -> "security") and would hijack a
      // very generic term. Keep it as a surface form, never as a lookup key.
      if (form.split(/\s+/).length > 1 && key.split(" ").length === 1) {
        if (!surfaces.includes(form)) surfaces.push(form);
        continue;
      }
      if (!this.canonByKey.has(key)) this.canonByKey.set(key, term);
      if (!surfaces.includes(form)) surfaces.push(form);
    }
  }
  resolve(phrase) { return this.canonByKey.get(canonical(phrase)) || null; }
  surfaces(term) { return this.surfacesMap.get(term) || [term]; }
  category(term) { return this.categoryMap.get(term) || "custom"; }
  variantsOf(phrase) {
    const term = this.resolve(phrase);
    return term === null ? [phrase] : this.surfaces(term);
  }
}

// -------------------------------------------------------------- resume ----
const SECTION_ALIASES = {
  summary: ["summary", "professional summary", "profile", "professional profile", "objective",
    "career objective", "about", "about me", "overview", "executive summary", "career summary",
    "highlights", "qualifications summary", "summary of qualifications"],
  experience: ["experience", "work experience", "professional experience", "employment",
    "employment history", "work history", "relevant experience", "career history",
    "professional background", "industry experience"],
  education: ["education", "academic background", "academics", "education and training",
    "educational background"],
  skills: ["skills", "technical skills", "core competencies", "competencies",
    "technical proficiencies", "areas of expertise", "expertise", "technologies",
    "tools and technologies", "technical expertise", "key skills", "skill set"],
  certifications: ["certifications", "certification", "licenses", "licenses and certifications",
    "certifications and licenses", "professional certifications", "credentials"],
  projects: ["projects", "key projects", "selected projects", "portfolio", "personal projects",
    "technical projects"],
  awards: ["awards", "honors", "achievements", "recognition", "awards and honors"],
  publications: ["publications", "papers", "research", "speaking", "presentations"],
  volunteer: ["volunteer", "volunteering", "community involvement", "activities"],
  clearance: ["clearance", "security clearance", "clearances"],
  references: ["references"],
};

const HEADING_LOOKUP = [];
for (const [canon, aliases] of Object.entries(SECTION_ALIASES)) {
  for (const alias of aliases) HEADING_LOOKUP.push([alias, canon]);
}
HEADING_LOOKUP.sort((a, b) => b[0].length - a[0].length);

const EMAIL_RE = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/;
const PHONE_RE = /(?:\+?\d{1,3}[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]?\d{3}[\s.-]?\d{4}\b/;
const URL_RE = /(?:https?:\/\/|www\.)[^\s,;<>()\[\]]+/gi;
const LINKEDIN_RE = /linkedin\.com\/in\/[A-Za-z0-9_-]+/i;
const GITHUB_RE = /github\.com\/[A-Za-z0-9_-]+/i;

const MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"];
const MONTH_NUM = {}; MONTHS.forEach((m, i) => { MONTH_NUM[m] = i + 1; });
const DATE_TOKEN = "(?:(?:" + MONTHS.join("|") + ")[a-z]*\\.?\\s*(?:\\d{1,2},?\\s*)?)?(?:19|20)\\d{2}";
const PRESENT = "(?:present|current|now|to\\s*date|ongoing)";
const DATE_RANGE_RE = new RegExp(
  "(?<start>" + DATE_TOKEN + ")\\s*(?:-|to|through)\\s*(?<end>" + PRESENT + "|" + DATE_TOKEN + ")", "i");

const WEAK_OPENERS = new Set(["responsible", "duties", "tasked", "helped", "assisted", "worked",
  "participated", "involved", "familiar", "exposure", "handled", "various"]);

const STRONG_VERBS = new Set(`
achieved administered analyzed architected audited automated built centralized championed conducted
configured consolidated coordinated created cut decreased delivered deployed designed detected developed
directed drove eliminated engineered enhanced established executed expanded facilitated forged generated
hardened headed hunted identified implemented improved increased initiated instituted integrated introduced
investigated launched led managed mentored migrated mitigated modernized monitored negotiated optimized
orchestrated overhauled owned partnered performed pioneered prevented prioritized produced programmed
quantified rearchitected rebuilt reduced refactored remediated reorganized reported researched resolved
restructured revamped saved scaled secured shipped simplified spearheaded standardized streamlined
strengthened supervised supported tested tracked trained transformed triaged tuned uncovered unified
upgraded validated
lead drive build run win grow oversee hold keep rebuild undertake set shape
close sign retain position engage present negotiate expand advise partner
signed closed retained positioned engaged consulted presented negotiated won
grew expanded advised chaired forecast governed guided influenced instrumented
justified landed originated qualified quantified rescued restored safeguarded
sold sourced sponsored steered structured surfaced turned unblocked
`.trim().split(/\s+/));

/* Matched by stem so "design"/"designed" both count; irregulars are listed in
   both forms. Present tense matters: a current role is written in it. */
const STRONG_VERB_STEMS = new Set([...STRONG_VERBS].map(stem));
const WEAK_OPENER_STEMS = new Set([...WEAK_OPENERS].map(stem));

function openerStrength(bullet) {
  const first = (tokenize(bullet) || [])[0];
  if (!first) return "neutral";
  const root = stem(first);
  if (WEAK_OPENER_STEMS.has(root)) return "weak";
  if (STRONG_VERB_STEMS.has(root)) return "strong";
  return "neutral";
}

/* Lines repeated across the document are page banners, not job titles. */
function repeatedLines(text, minRepeats) {
  minRepeats = minRepeats || 3;
  const counts = new Map();
  for (const raw of text.split("\n")) {
    const line = raw.trim();
    if (line.length > 3 && line.length < 70) counts.set(line, (counts.get(line) || 0) + 1);
  }
  const out = new Set();
  for (const [line, n] of counts) if (n >= minRepeats) out.add(line);
  return out;
}

/* Units seen in real accomplishment bullets. The earlier list was short enough
   to miss genuine quantification -- "raising customer satisfaction 10 points"
   read as unquantified -- understating a resume's writing quality. */
const METRIC_UNITS = "x|hours?|hrs?|days?|weeks?|months?|years?|users?|endpoints?|servers?|"
  + "alerts?|incidents?|systems?|accounts?|devices?|tickets?|points?|pts?|bps|fte|headcount|"
  + "clients?|customers?|projects?|programs?|programmes?|sites?|countries|regions?|teams?|"
  + "engineers?|staff|seats?|licen[cs]es?|releases?|deals?|logos?|vendors?|partners?|"
  + "suppliers?|contracts?|k\\b|m\\b|mm\\b|bn\\b";
const SPELLED_NUMBERS = "one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve";
const METRIC_RE = new RegExp(
  "(?:\\$\\s?\\d"
  + "|\\d+(?:\\.\\d+)?\\s?(?:%|percent)"
  + "|\\b\\d{1,3}(?:,\\d{3})+\\b"
  + "|\\b\\d+(?:\\.\\d+)?\\s?(?:" + METRIC_UNITS + ")"
  + "|\\b(?:" + SPELLED_NUMBERS + ")\\s+(?:" + METRIC_UNITS + "))", "i");

function todayYM() { const d = new Date(); return [d.getFullYear(), d.getMonth() + 1]; }
const ymToInt = (ym) => ym[0] * 12 + ym[1];

function parseDateToken(tok) {
  if (!tok) return null;
  const low = tok.toLowerCase();
  const ym = low.match(/(19|20)\d{2}/);
  if (!ym) return null;
  let month = 1;
  for (const [name, num] of Object.entries(MONTH_NUM)) { if (low.includes(name)) { month = num; break; } }
  return [parseInt(ym[0], 10), month];
}

function parseDates(text) {
  const m = text.match(DATE_RANGE_RE);
  if (!m) return [null, null, false];
  const start = parseDateToken(m.groups.start);
  const endRaw = (m.groups.end || "").trim();
  if (new RegExp("^" + PRESENT + "$", "i").test(endRaw)) return [start, null, true];
  return [start, parseDateToken(endRaw), false];
}

function matchHeading(raw) {
  let line = normalize(raw).trim().replace(/^[:|\-–—•*\s\t]+|[:|\-–—•*\s\t]+$/g, "");
  line = line.replace(/\s+/g, " ");
  if (!line || line.length > 60) return null;
  for (const [alias, canon] of HEADING_LOOKUP) {
    if (line === alias || line.startsWith(alias + " ") || line.startsWith(alias + ":")) return canon;
    if (new RegExp("^" + alias.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "[\\s_=~.·|/-]*$").test(line)) return canon;
  }
  return null;
}

function looksLikeHeading(raw) {
  const line = raw.trim().replace(/:+$/, "").trim();
  if (!line || line.length > 60 || isBullet(raw)) return false;
  const words = line.split(/\s+/);
  if (words.length > 5) return false;
  if (/[.,;]$/.test(line)) return false;
  const letters = line.split("").filter((c) => /[a-zA-Z]/.test(c));
  if (!letters.length) return false;
  const upper = letters.filter((c) => c === c.toUpperCase()).length / letters.length;
  const titleCase = words.every((w) => !/^[a-zA-Z]/.test(w) || w[0] === w[0].toUpperCase());
  return upper > 0.7 || (titleCase && words.length <= 4);
}

function splitSections(text) {
  const sections = new Map([["_header", []]]);
  const order = ["_header"];
  const unrecognized = [];
  let current = "_header";
  for (const raw of text.split("\n")) {
    const canon = matchHeading(raw);
    if (canon) {
      current = canon;
      if (!sections.has(current)) { sections.set(current, []); order.push(current); }
      continue;
    }
    if (looksLikeHeading(raw) && raw.trim().length > 2) {
      const stripped = raw.trim().replace(/:+$/, "");
      if (!DATE_RANGE_RE.test(raw) && stripped === stripped.toUpperCase()
          && /[A-Z]/.test(stripped) && stripped.split(/\s+/).length <= 4) {
        unrecognized.push(stripped);
      }
    }
    sections.get(current).push(raw);
  }
  const out = {};
  for (const [k, v] of sections) out[k] = v.join("\n").trim();
  return [out, order, unrecognized];
}

function parseContact(text, headerHint) {
  const banners = repeatedLines(text);
  const head = headerHint || text.split("\n").slice(0, 12).join("\n");
  const scope = EMAIL_RE.test(head) ? head : text;
  const contact = { email: null, phone: null, linkedin: null, github: null, urls: [], nameGuess: null, location: null };
  let m = scope.match(EMAIL_RE); contact.email = m ? m[0] : null;
  m = scope.match(PHONE_RE); contact.phone = m ? m[0].trim() : null;
  m = text.match(LINKEDIN_RE); contact.linkedin = m ? m[0] : null;
  m = text.match(GITHUB_RE); contact.github = m ? m[0] : null;
  contact.urls = head.match(URL_RE) || [];

  for (const raw of text.split("\n").slice(0, 6)) {
    const line = raw.trim();
    if (!line || EMAIL_RE.test(line) || /(?:https?:\/\/|www\.)/i.test(line)) continue;
    const words = line.replace(/,/g, " ").split(/\s+/).filter(Boolean);
    if (banners.has(line)) continue;
    if (words.length > 1 && words.length <= 4
        && words.every((w) => !/^[a-zA-Z]/.test(w) || w[0] === w[0].toUpperCase())
        && !/\d/.test(line)) { contact.nameGuess = line; break; }
  }
  const loc = head.match(/\b([A-Z][a-zA-Z.\- ]{2,24}),\s*([A-Z]{2}|[A-Z][a-z]+)\b(?:\s+\d{5})?/);
  if (loc) contact.location = loc[0].trim();
  return contact;
}

function splitTitleOrg(line) {
  let cleaned = line.replace(new RegExp(DATE_RANGE_RE.source, "gi"), "");
  cleaned = cleaned.replace(/(19|20)\d{2}\s*(?:-|to)\s*(?:present|current)/gi, "");
  // An explicit delimiter wins. Also splitting on commas turned
  // "Senior Director, Sales and Solution Support | Pivot Technology Solutions"
  // into a title of "Senior Director" and an employer of "Sales and Solution
  // Support", losing the real employer.
  const pieces = /[|•·]/.test(cleaned)
    ? cleaned.split(/\s*[|•·]\s*/)
    : cleaned.split(/\s{2,}|\s+-\s+|,\s+/);
  const parts = pieces
    .map((p) => p.replace(/^[\s,|·\-\t]+|[\s,|·\-\t]+$/g, ""))
    .filter((p) => p && !/^[\d\s./-]*$/.test(p));
  if (!parts.length) return ["", ""];
  if (parts.length === 1) return [parts[0], ""];
  return [parts[0], parts[1]];
}

/* True when a line opens something new rather than continuing a bullet. */
function startsNewBlock(raw) {
  const line = raw.trim();
  if (!line) return false;
  if (matchHeading(line) || looksLikeHeading(line)) return true;
  if (line.includes("|") && line.length < 120) return true;
  return DATE_RANGE_RE.test(line) && !/^\s/.test(raw);
}


const ORG_LINE_RE = /^[A-Z0-9][A-Z0-9 &.,'()/\-\u2013\u2014]{3,}$/;
const ORG_SUFFIXES = new Set(["inc","inc.","llc","ltd","ltd.","corp","corp.","corporation",
  "company","co","co.","plc","gmbh","technologies","technology","solutions","systems","group",
  "services","consulting","partners","holdings","labs","software","industries","associates",
  "agency","university","college","hospital","bank","health","networks"]);
const TITLE_WORDS = new Set(`
analyst engineer manager director consultant architect specialist lead leader
president officer administrator developer scientist designer coordinator
supervisor head chief principal associate intern executive advisor strategist
vp svp evp cto cio ciso cfo ceo coo partner
`.trim().split(/\s+/));
const LOCATION_TAIL_RE = /\s*[-\u2013\u2014,|]\s*[A-Z][A-Za-z.\- ]{1,24},\s*(?:[A-Z]{2}|[A-Z][a-z]+)\s*$/;
const stripLocation = (t) => t.replace(LOCATION_TAIL_RE, "").replace(/^[\s,|-]+|[\s,|-]+$/g, "");

/* How strongly a heading line reads as the employer rather than the job.
   Positive means employer, negative means title: a legal suffix or a trailing
   location says employer, a role noun says title. */
function orgScore(line) {
  const text = line.split(/\s+/).filter(Boolean).join(" ").replace(/^[\s,|]+|[\s,|]+$/g, "");
  if (!text) return 0;
  const words = text.toLowerCase().split(/[\s,]+/);
  let score = 0;
  if (ORG_LINE_RE.test(text)) score += 2;
  if (words.some((w) => ORG_SUFFIXES.has(w.replace(/[.,]$/, "")))) score += 3;
  if (/,\s*[A-Z]{2}\s*$/.test(text) || /[-\u2013\u2014]\s*[A-Z][a-z]+,\s*[A-Z]{2}\b/.test(text)) score += 2;
  if (words.some((w) => TITLE_WORDS.has(w))) score -= 3;
  return score;
}

function looksLikeOrg(line) { return orgScore(line) > 0; }

/* Clean an employer name for display: the empty bracket a "(dates)" suffix
   leaves behind, and the location tail. Capitalisation is left exactly as the
   author wrote it -- case means nothing to an index, and title-casing cannot
   recover "CompuCom" from "COMPUCOM". */
function tidyOrg(text) {
  return stripLocation(text).replace(/\(\s*\)|\[\s*\]/g, "")
    .replace(/^[\s,|-]+|[\s,|-]+$/g, "").split(/\s+/).filter(Boolean).join(" ");
}

/* Which of a role's naming lines is the title and which the employer, decided
   by what each line looks like and never by the order they appear in: resumes
   put the employer first as often as the title, and reading position instead
   of content is what deleted one of the two. The index set says which inputs
   were consumed, so a line that contributed nothing is left where it was
   rather than silently dropped. */
function assignTitleOrg(parts) {
  const cleaned = [];
  parts.forEach((p, i) => {
    if (!p || !p.trim()) return;
    cleaned.push([i, p.split(/\s+/).filter(Boolean).join(" ").replace(/^[\s,|]+|[\s,|]+$/g, "")]);
  });
  if (!cleaned.length) return ["", "", new Set()];
  if (cleaned.length === 1) {
    const [idx, only] = cleaned[0];
    const [t, o] = splitTitleOrg(only);
    if (o) return [t, tidyOrg(o), new Set([idx])];
    if (looksLikeOrg(only)) return ["", tidyOrg(only), new Set([idx])];
    return [only, "", new Set([idx])];
  }
  const [iFirst, first] = cleaned[0], [iSecond, second] = cleaned[1];
  const both = new Set([iFirst, iSecond]);
  // The higher employer score is the employer; a tie keeps "title then org".
  if (orgScore(first) > orgScore(second)) return [second, tidyOrg(first), both];
  return [first, tidyOrg(second), both];
}

function hasDateRange(line) {
  return DATE_RANGE_RE.test(line)
    || /(19|20)\d{2}\s*(?:-|\u2013|\u2014|to)\s*(?:present|current|(19|20)\d{2})/i.test(line);
}

/* Resumes stack the block as employer / title / dates on separate lines, so
   the dated line carries no name at all. Reading only that line lost every job
   title and employer -- each role rendered as "Position". */
function borrowHeading(candidates, want) {
  const usable = [];
  for (const line of candidates) {
    const cleaned = line.split(/\s+/).filter(Boolean).join(" ");
    if (!cleaned || cleaned.length > 120 || isBullet(cleaned)) continue;
    usable.push(line);
    if (usable.length >= (want || 2)) break;
  }
  return usable;
}

function parseRoles(experienceText, banners) {
  banners = banners || new Set();
  const roles = [];
  let inTrailing = false;
  let current = null, buffer = [], recent = [];
  const flush = () => { if (current) { current.text = buffer.join("\n").trim(); roles.push(current); } };
  /* A line that turned out to name the NEXT position must not also survive as
     the previous one's content, or the rebuilt resume prints the same job
     twice -- once as a stray line, once as a heading. */
  const disown = (lines) => {
    for (const line of lines) {
      const stripped = line.trim();
      const at = buffer.indexOf(stripped);
      if (at !== -1) buffer.splice(at, 1);
      if (!current) continue;
      const ta = current.trailing.indexOf(stripped);
      if (ta !== -1) {
        current.trailing.splice(ta, 1);
        if (!current.trailing.length) inTrailing = false;
      }
      if (current.bullets.length) {
        const last = current.bullets[current.bullets.length - 1];
        if (last.endsWith(stripped) && last !== stripped) {
          current.bullets[current.bullets.length - 1] = last.slice(0, -stripped.length).trim();
        } else if (last === stripped) current.bullets.pop();
      }
    }
  };

  const sourceLines = experienceText.split("\n");
  const consumed = new Set();
  /* A right-aligned date often extracts onto the line ABOVE the job title,
     leaving nothing behind it to name the role. */
  const lookahead = (start) => {
    const out = [];
    for (let j = start + 1; j < Math.min(start + 4, sourceLines.length); j++) {
      const nxt = sourceLines[j].trim();
      if (!nxt) continue;
      if (isBullet(sourceLines[j]) || hasDateRange(nxt)) break;
      out.push(nxt);
      consumed.add(j);
      if (out.length === 2) break;
    }
    return out;
  };

  for (let index = 0; index < sourceLines.length; index++) {
    const raw = sourceLines[index];
    const line = raw.trim();
    if (!line || consumed.has(index)) continue;
    if (hasDateRange(line) && !isBullet(raw)) {
      let [title, org] = splitTitleOrg(line);
      if (org) org = tidyOrg(org);
      if (banners.has(title)) title = "";
      if (!title || !org) {
        /* Whatever naming material this role has, from the date line itself
           and from the lines around it, is pooled and then sorted into the two
           slots by what each line looks like. */
        const own = [title, org].filter(Boolean);
        let borrowed = [];
        if (own.length < 2) {
          const back = recent.slice().reverse();
          borrowed = borrowHeading(back.length ? back : lookahead(index), 2 - own.length);
        }
        const [t, o, used] = assignTitleOrg(own.concat(borrowed));
        title = banners.has(t) ? "" : t;
        org = o;
        /* Only lines the assignment actually consumed are taken off the
           previous role. Disowning one that contributed nothing deleted it
           from the resume altogether. */
        disown(borrowed.filter((_, offset) => used.has(own.length + offset)));
      }
      flush();
      buffer = [line];
      const [start, end, isCurrent] = parseDates(line);
      current = { heading: line, title, organization: org, start, end, isCurrent,
                  bullets: [], trailing: [], text: "", unmarkedBullets: false };
      recent = [];
      inTrailing = false;
      continue;
    }
    if (!current) {
      if (!isBullet(raw)) { recent.push(line); if (recent.length > 3) recent.shift(); }
      continue;
    }
    buffer.push(line);
    if (!isBullet(raw)) { recent.push(line); if (recent.length > 3) recent.shift(); }
    if (!isBullet(raw) && startsNewBlock(raw)) {
      inTrailing = true;
      current.trailing.push(line);
      continue;
    }
    if (inTrailing) {
      current.trailing.push(isBullet(raw) ? "- " + stripBullet(raw) : line);
      continue;
    }
    if (isBullet(raw)) current.bullets.push(stripBullet(raw));
    else if (current.bullets.length) {
      current.bullets[current.bullets.length - 1] =
        (current.bullets[current.bullets.length - 1] + " " + line).trim();
    } else current.trailing.push(line);
  }
  flush();
  for (const role of roles) promoteUnmarkedBullets(role);
  return roles;
}

/* A resume pasted out of Word often arrives with its list markers gone: Word
   stores them as numbering, not as text, so the glyph never reaches the
   clipboard. The accomplishment lines are still there and still counted for
   keywords, but with nothing marking them the writing component reported "no
   bullet points detected" on a resume full of them. */
const ACCOMPLISHMENT_MIN_CHARS = 40;

function promoteUnmarkedBullets(role) {
  if (role.bullets.length || role.trailing.length < 2) return;
  for (const line of role.trailing) {
    if (line.length < ACCOMPLISHMENT_MIN_CHARS) return;
    if (startsNewBlock(line) || looksLikeHeading(line)) return;
    if (hasDateRange(line) || line.endsWith(":")) return;
    if (line.slice(0, 1) !== line.slice(0, 1).toUpperCase()) return;
  }
  role.bullets = role.trailing.slice();
  role.trailing = [];
  role.unmarkedBullets = true;
}

function roleMonths(role) {
  if (!role.start) return 0;
  const end = role.end || todayYM();
  return Math.max(0, (end[0] - role.start[0]) * 12 + (end[1] - role.start[1]));
}

function collectBullets(text) {
  const out = [];
  let open = false;
  for (const raw of text.split("\n")) {
    if (isBullet(raw)) { out.push(stripBullet(raw)); open = true; continue; }
    const stripped = raw.trim();
    if (open && stripped && /^[ \t]/.test(raw) && !matchHeading(raw)) {
      out[out.length - 1] = (out[out.length - 1] + " " + stripped).trim();
    } else { open = false; }
  }
  return out.filter((b) => b.length > 15);
}

function parseResume(text) {
  const [sections, order, unrecognized] = splitSections(text);
  const resume = {
    text, sections,
    sectionOrder: order.filter((s) => s !== "_header"),
    unrecognizedHeadings: unrecognized,
    contact: parseContact(text, sections._header || ""),
    roles: [], bullets: [],
    section(name) { return this.sections[name] || ""; },
  };
  const banners = repeatedLines(text);
  const exp = sections.experience || "";
  resume.roles = exp ? parseRoles(exp, banners) : parseRoles(text, banners);
  resume.bullets = collectBullets(text);
  // Education and certification list items are not accomplishments.
  const roleBullets = [];
  for (const r of resume.roles) roleBullets.push(...r.bullets);
  resume.experienceBullets = roleBullets.length ? roleBullets : resume.bullets;

  const spans = resume.roles.filter((r) => r.start)
    .map((r) => [ymToInt(r.start), ymToInt(r.end || todayYM())])
    .sort((a, b) => a[0] - b[0]);
  const merged = [];
  for (const [s, e] of spans) {
    if (merged.length && s <= merged[merged.length - 1][1]) {
      merged[merged.length - 1][1] = Math.max(merged[merged.length - 1][1], e);
    } else merged.push([s, e]);
  }
  resume.totalExperienceMonths = merged.reduce((acc, [s, e]) => acc + Math.max(0, e - s), 0);
  resume.yearsExperience = Math.round((resume.totalExperienceMonths / 12) * 10) / 10;
  return resume;
}

// ------------------------------------------------- job description ----
const NOISE_SECTIONS = ["benefits", "perks", "what we offer", "our offer", "compensation", "salary",
  "pay range", "pay transparency", "equal opportunity", "eeo", "diversity", "e-verify",
  "accommodation", "accommodations", "about us", "about the company", "who we are", "our company",
  "our mission", "our values", "why join", "life at", "disclaimer", "legal", "privacy",
  "how to apply", "application process"];
const REQUIRED_SECTIONS = ["requirements", "required", "minimum qualifications",
  "basic qualifications", "qualifications", "what you need", "what you'll need", "you have",
  "must have", "required skills", "required qualifications", "minimum requirements", "essential",
  "essential functions", "skills", "experience required", "who you are", "we're looking for"];
const PREFERRED_SECTIONS = ["preferred", "preferred qualifications", "nice to have", "nice-to-have",
  "bonus", "bonus points", "desired", "desirable", "plus", "pluses", "additional qualifications",
  "a plus", "even better", "extra credit", "preferred skills", "good to have"];
const RESPONSIBILITY_SECTIONS = ["responsibilities", "what you'll do", "what you will do",
  "the role", "duties", "job duties", "day to day", "day-to-day", "your impact",
  "key responsibilities", "about the role", "role overview", "position summary"];

const MUST_MARKERS = /\b(must have|must be|must possess|is required|are required|required\b|requires\b|minimum of|at least|mandatory|non-negotiable|essential)\b/i;
const NICE_MARKERS = /\b(preferred|preferably|nice to have|a plus|bonus|desirable|ideally|would be great|not required|optional)\b/i;
const YEARS_RE = /(\d{1,2})\s*(?:\+|plus)?\s*(?:-|to)?\s*(\d{1,2})?\s*\+?\s*(?:years?|yrs?)\b/i;
const DEGREE_RE = /\b(ph\.?d|doctorate|master'?s?|m\.?s\.?c?\b|m\.?b\.?a|bachelor'?s?|b\.?s\.?c?\b|b\.?a\b|associate'?s?|high school diploma|ged)\b/i;
const CLEARANCE_RE = /\b(top secret\/sci|ts\/sci|top secret|secret clearance|security clearance|public trust|poly(?:graph)?|dod\s*8570|8140)\b/i;

const BOILERPLATE = new Set(`
401k 401 k pto health dental vision insurance equity stock options bonus salary compensation benefits
perks holiday vacation remote hybrid onsite office opportunity employer veteran disability gender race
religion orientation identity applicants qualified consideration background check drug screen resume
cover letter interview hiring recruiter application applicants apply click submit posting requisition
full time part time contract w2 c2c
`.trim().split(/\s+/));

const CONTAINER_NOUNS = new Set(`
platform platforms tool tools tooling solution solutions technology technologies product products
service services vendor vendors system systems suite suites environment environments capability
capabilities activity activities initiative initiatives effort efforts team teams stack stacks
offering offerings
`.trim().split(/\s+/));

const REQUIREMENT_LANGUAGE = new Set(`
required require requires requirement requirements minimum min must mandatory preferred prefer
preferably desired desirable essential plus bonus optional experience experienced knowledge
understanding familiarity familiar expertise proficiency proficient demonstrated proven hands-on hands
on strong solid excellent deep broad extensive significant relevant related equivalent ability able
capable skills skill background exposure track record years year degree qualification qualifications
comfortable passion passionate willingness bachelor bachelors master masters phd doctorate associate
associates diploma ged
`.trim().split(/\s+/));

const ALLOWED_SHORT = new Set(["ai", "ml", "qa", "ci", "cd", "go", "r", "c", "aws", "gcp", "sql",
  "api", "ir", "ad", "iam", "pam", "dlp", "edr", "xdr", "mdr", "siem", "soc", "grc", "pki", "sso",
  "mfa", "waf", "vpn", "dns", "tcp", "ssl", "tls", "sox", "pci"]);

/* Verb forms that begin or end a mid-sentence fragment. Nouns merely ending in
   -ing (engineering, consulting, marketing, planning) are deliberately absent. */
const GERUND_HINGES = new Set(`
leading building driving managing developing creating ensuring supporting
delivering providing working using including scaling commercializing defining
establishing identifying partnering collaborating monitoring representing
fostering sponsoring guiding advising enabling executing owning translating
maintaining leveraging aligning shaping growing serving
`.trim().split(/\s+/));

/* Modifier suffixes: "AI-enabled" qualifies a skill, it is not one. */
const MODIFIER_SUFFIXES = ["-enabled","-led","-driven","-based","-level","-leading",
  "-focused","-oriented","-facing","-ready","-centric","-native","-first","-wide",
  "-critical","-grade"];

/* Generic business nouns a posting uses to frame a requirement rather than name
   one. Each was reported as a missing keyword against a real posting, where
   "add the word firm to your resume" pads the denominator and understates how
   well the resume covers the job. */
const VAGUE_SINGLES = new Set(`
experience knowledge understanding ability skills strong excellent years work
working team environment including related field level support using use new
well etc firm practice industry industries provider providers network networks
communication communications define scaling global market markets business
organization organizations company companies client clients customer customers
stakeholder stakeholders leader leaders analyst analysts executive executives
professional professionals priorities priority objectives outcomes initiatives
reviews review resources growth success excellence innovation insights trends
vision culture impact opportunities opportunity engagements solutions offerings
methodologies frameworks practices approaches capabilities
serves serve define defines drive drives lead leads own owns build builds
deliver delivers ensure ensures supports manage manages develop develops
create creates execute executes execution monitor monitors represent
represents identify identifies collaborate partner partners translate foster
sponsor guide advise enable maintain leverage align shape grow pipeline
important defining generation operating thought asset assets spanning adoption
questions roadmaps launches workflow launch coverage areas area role roles
`.trim().split(/\s+/));

for (const w of ("job jobs multiple reflect trusted changes change decision decisions mission "
  + "missions staff needed choice choices home value values strongly key member members regular "
  + "regularly direct directly consistently exceptional timely overall across within throughout "
  + "continuous ongoing trust consistency state region travel proactively acumen license licence "
  + "licensure licensed").split(" ")) VAGUE_SINGLES.add(w);

/* A posting's metadata lines name the reporting line, the office and the
   schedule, not a capability. Mining them put "svp", "general manager",
   "dallas" and "reports" among the heaviest missing keywords. */
const METADATA_LINE_RE = /^\s*(?:job\s+)?(?:title|position|location|locations|reports?\s+to|reporting\s+to|department|division|travel|schedule|shift|hours|job\s+type|employment\s+type|salary|pay|compensation|posted|requisition|req\s*id|job\s*id|work\s+arrangement)\s*(?:\/\s*\w+\s*)?[:\-\u2013]/i;

/* Where the person has to live is a condition of the job, not a skill. */
const RESIDENCY_WORDS = new Set(("area living residing reside relocate relocation relocating commute "
  + "commutable commuting locally onsite on-site in-office in-person").split(" "));

/* Gerunds that have become the name of a discipline. Everything else ending
   in -ing is a verb caught mid-sentence ("providing", "ensuring"). */
const NOMINAL_GERUNDS = new Set(("planning training reporting forecasting budgeting consulting "
  + "auditing mentoring coaching staffing scheduling recruiting onboarding testing engineering "
  + "marketing accounting purchasing sourcing licensing nursing modeling modelling pricing billing "
  + "coding programming networking manufacturing underwriting contracting outsourcing benchmarking "
  + "screening credentialing learning monitoring positioning advertising merchandising publishing "
  + "counseling counselling fundraising prospecting selling closing messaging branding").split(" "));

/* Verbs a posting uses to introduce a duty. A phrase that opens or closes on
   one is a slice of a sentence, not a keyword. */
const JD_VERBS = new Set(("ensure provide drive guide deliver improve reduce strengthen support "
  + "execute advise scale conduct implement monitor develop assess help succeed lead build partner "
  + "work foster champion equip reinforce introduce standardize standardise serve align reflect "
  + "maintain manage oversee coordinate collaborate communicate create define design establish "
  + "evaluate identify influence leverage optimize optimise own perform plan prepare prioritize "
  + "prioritise promote recommend represent resolve review shape translate utilize utilise track "
  + "train understand analyze analyse achieve assist demonstrate enable engage facilitate generate "
  + "participate contribute cultivate empower inspire motivate mentor coach negotiate present "
  + "report respond handle operate organize organise").split(" "));

const VERB_FORMS = new Set();
for (const v of JD_VERBS) {
  VERB_FORMS.add(v);
  VERB_FORMS.add(/(s|sh|ch|x|z)$/.test(v) ? v + "es" : v + "s");
  VERB_FORMS.add(v.endsWith("e") && !v.endsWith("ee") ? v.slice(0, -1) + "ing" : v + "ing");
}

/* Nouns that are also verbs: "corrective action plans" ends on one. */
const NOUN_VERB_HOMOGRAPHS = new Set(("plans reports reviews supports controls designs releases "
  + "updates audits schedules forecasts budgets changes needs contacts documents estimates measures "
  + "offers orders places projects records requests results returns uses values works benefits "
  + "impacts interfaces links partners pilots positions presents programs purchases services "
  + "structures targets transfers trends drives leads focus").split(" "));

/* A phrase that trails off into a modifier is cut before its noun. */
const TRAILING_MODIFIERS = new Set(("exceptional timely consistent appropriate operational strategic "
  + "effective efficient successful high strong multiple various regular key new additional ongoing "
  + "overall direct indirect proactive proactively broad deep full").split(" "));

const CITY_STATE_RE = /\b([A-Z][A-Za-z.]+(?:\s+[A-Z][A-Za-z.]+){0,2}),\s*([A-Z]{2}|[A-Z][a-z]+)\b/g;
const RESIDENCY_LINE_RE = /\b(living|reside|residing|based|located|relocat\w*|commut\w*|territor(?:y|ies))\b|\barea\b/i;
const REPORTING_CLAUSE_RE = /\breport(?:s|ing)?\s+(?:directly\s+)?(?:in\s+)?to\s+(?:the\s+)?[^,.;:()]+/gi;

/* Professional licences a posting can require outright. In healthcare they
   are the commonest knockout question there is. */
const LICENSES = {
  "registered nurse": ["rn", "r.n.", "rn license", "rn licensure", "registered nurse license",
                       "bsn, rn", "msn, rn", "registered nurse (rn)"],
  "licensed practical nurse": ["lpn", "lvn", "licensed vocational nurse"],
  "nurse practitioner": ["np", "aprn", "advanced practice registered nurse", "fnp", "fnp-c"],
  "physician assistant": ["pa-c", "physician associate"],
  "physical therapist": ["dpt", "pt license", "licensed physical therapist"],
  "occupational therapist": ["otr", "otr/l", "licensed occupational therapist"],
  "respiratory therapist": ["rrt", "crt"],
  "registered dietitian": ["rd", "rdn"],
  "licensed clinical social worker": ["lcsw", "lmsw", "licensed social worker"],
  "certified nursing assistant": ["cna"],
  "pharmacist": ["pharmd", "rph", "licensed pharmacist"],
  "physician": ["md", "do", "medical license", "licensed physician", "board certified"],
  "certified public accountant": ["cpa", "cpa license"],
  "professional engineer": ["pe license", "p.e.", "licensed professional engineer"],
  "commercial driver's license": ["cdl", "class a cdl", "class b cdl", "cdl-a"],
  "bar admission": ["admitted to the bar", "licensed attorney", "state bar", "juris doctor", "j.d."],
  "real estate license": ["licensed realtor", "real estate salesperson license"],
  "series 7": ["finra series 7", "series 7 license"],
  "series 63": ["finra series 63"],
  "insurance license": ["licensed insurance agent", "property and casualty license", "life and health license"],
};
const LICENSE_NAME_RE = /\b(registered nurse|licensed practical nurse|licensed vocational nurse|nurse practitioner|physician assistant|physical therapist|occupational therapist|respiratory therapist|registered dietitian|licensed clinical social worker|certified nursing assistant|pharmacist|physician|certified public accountant|professional engineer|commercial driver'?s? licen[sc]e|bar admission|admitted to the bar|licensed attorney|real estate licen[sc]e|series 7|series 63|insurance licen[sc]e|rn|lpn|lvn|aprn|cna|cpa|cdl|rrt|lcsw|pharmd|dpt)\b/i;
const LICENSE_CONDITION_RE = /\b(licen[sc]e[ds]?|licensure|must (?:be|hold|have|possess)|required|active|current|valid|unrestricted|in good standing|registered)\b/i;

/* The licence a line makes a condition of the job, or null. */
function licenseRequired(line) {
  const m = line.match(LICENSE_NAME_RE);
  if (!m || !LICENSE_CONDITION_RE.test(line)) return null;
  if (NICE_MARKERS.test(line) && !/(?<!not )\brequired\b|\bmust\b/i.test(line)) return null;
  let found = m[1].toLowerCase().replace("licence", "license");
  if (found.includes("driver")) found = found.replace(/'?s? licen[sc]e$/, "'s license");
  for (const [name, alts] of Object.entries(LICENSES)) if (found === name || alts.includes(found)) return name;
  for (const name of Object.keys(LICENSES)) if (name.includes(found)) return name;
  return found;
}

/* Words that name where the job is, not what it needs. */
function locationTokens(text) {
  const found = new Set();
  const lines = text.split("\n");
  const scopes = lines.slice(0, 5).concat(
    lines.filter((ln) => METADATA_LINE_RE.test(ln) || RESIDENCY_LINE_RE.test(ln)));
  for (const raw of scopes) {
    for (const m of raw.matchAll(CITY_STATE_RE)) {
      for (const word of m[1].split(/\s+/)) found.add(normalize(word).replace(/^[.,]+|[.,]+$/g, ""));
    }
    if (RESIDENCY_LINE_RE.test(raw) || METADATA_LINE_RE.test(raw)) {
      for (const word of raw.match(/\b[A-Z][A-Za-z]{1,}\b/g) || []) {
        const low = normalize(word);
        if (STOPWORDS.has(low) || VAGUE_SINGLES.has(low) || low.length < 3) continue;
        if (raw.trim().startsWith(word)) continue;          // a sentence's first word
        if (/^[A-Z]+$/.test(word) || /^[A-Z][a-z]+$/.test(word)) found.add(low);
      }
    }
  }
  return new Set([...found].filter((t) => !SECTION_VOCAB.has(t)));
}

/* True if the posting wrote the phrase as a proper term: "CMS Conditions of
   Participation" is Title Case or carries an acronym; "decisions support
   exceptional" is not. A short line entirely in Title Case is a sub-heading,
   so capitals there vouch for nothing. */
function isProper(phrase, rawLine) {
  const words = phrase.split(" ");
  const re = new RegExp("\\b" + words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("\\W+") + "\\b", "i");
  const m = rawLine.match(re);
  if (!m) return false;
  const lineWords = rawLine.match(/[A-Za-z][A-Za-z&.+#\/-]*/g) || [];
  if (lineWords.length <= 8 && lineWords.filter((w) => w.length >= 4).every((w) => /^[A-Z]/.test(w))) return false;
  const found = m[0].match(/[A-Za-z][A-Za-z&.+#\/-]*/g) || [];
  if (!found.length) return false;
  const before = rawLine.slice(0, m.index).replace(/\s+$/, "");
  const atStart = m.index === 0 || /[.:\-\u2022]$/.test(before);
  let judged = atStart && found.length > 1 ? found.slice(1) : found;
  judged = judged.filter((w) => !STOPWORDS.has(w.toLowerCase()));
  if (!judged.length) return false;
  if (judged.some((w) => w.length >= 2 && w === w.toUpperCase())) return true;
  return judged.every((w) => /^[A-Z]/.test(w));
}

/* Words appearing in section headings, never in an employer's name. */
const SECTION_VOCAB = new Set([].concat(
  NOISE_SECTIONS, REQUIRED_SECTIONS, PREFERRED_SECTIONS, RESPONSIBILITY_SECTIONS
).join(" ").split(/\s+/).concat(
  ["overview","summary","description","position","job","posting"]));

const COMPANY_PATTERNS = [
  /^\s*([A-Z][\w&.-]*(?:\s+[A-Z][\w&.-]*){0,3})\s*[-\u2013\u2014|]\s*\S/m,
  /\b(?:About|Join|At)\s+([A-Z][\w&.-]*(?:\s+[A-Z][\w&.-]*){0,2})\b/g,
  /\b([A-Z][\w&.-]*(?:\s+[A-Z][\w&.-]*){0,2})\s+is\s+(?:a|an|the|part of)\b/g,
];

/* A posting repeats its own company name, and the miner counted it as a
   required keyword. Nobody can put the hiring employer's name on their
   resume, so every occurrence padded the denominator. */
function companyTokens(text, lexicon) {
  const head = text.split("\n").slice(0, 3).join("\n");
  const wider = text.split("\n").slice(0, 12).join("\n");
  const found = new Set();
  COMPANY_PATTERNS.forEach((pattern, i) => {
    const scope = i === 0 ? head : wider;
    const re = new RegExp(pattern.source, pattern.flags.includes("g") ? pattern.flags : pattern.flags + "g");
    let m;
    while ((m = re.exec(scope)) !== null) {
      for (const word of m[1].split(/\s+/)) {
        const token = normalize(word).replace(/^[.,&-]+|[.,&-]+$/g, "");
        if (token.length < 3 || STOPWORDS.has(token) || VAGUE_SINGLES.has(token)) continue;
        if (SECTION_VOCAB.has(token)) continue;
        if (lexicon && lexicon.resolve(token)) continue;   // never blind us to a product
        found.add(token);
      }
      if (!re.global) break;
    }
  });
  return found;
}

const DEGREE_RANK = { ged: 1, "high school diploma": 1, associate: 2, associates: 2, bachelor: 3,
  bachelors: 3, bs: 3, ba: 3, bsc: 3, master: 4, masters: 4, ms: 4, msc: 4, mba: 4, phd: 5,
  doctorate: 5 };

function degreeRank(text) {
  const t = normalize(text).replace(/\./g, "").replace(/'/g, "");
  let best = 0;
  for (const [name, rank] of Object.entries(DEGREE_RANK)) {
    if (new RegExp("\\b" + name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "\\b").test(t)) {
      best = Math.max(best, rank);
    }
  }
  return best;
}

function classifyHeading(line) {
  let h = normalize(line).trim().replace(/^[:*#\-–—•\s\t]+|[:*#\-–—•\s\t]+$/g, "").replace(/\s+/g, " ");
  if (!h || h.length > 70) return null;
  let kind = matchHeadingLists(h);
  if (kind === null) {
    // "Job Responsibilities", "Key Qualifications", "Core Requirements".
    const stripped = h.replace(/^(?:job|key|core|primary|main|position|role|your|the|our|general)\s+/, "");
    if (stripped !== h) kind = matchHeadingLists(stripped);
  }
  return kind;
}

function matchHeadingLists(h) {
  for (const name of NOISE_SECTIONS) if (h.startsWith(name)) return "noise";
  for (const name of PREFERRED_SECTIONS) if (h.startsWith(name)) return "preferred";
  for (const name of REQUIRED_SECTIONS) if (h.startsWith(name)) return "required";
  for (const name of RESPONSIBILITY_SECTIONS) if (h.startsWith(name)) return "responsibility";
  return null;
}

/* Casing is deliberately not required: real postings write "Minimum
   Qualifications" in title case far more often than in caps. */
function jdLooksLikeHeading(line) {
  const s = line.trim();
  if (!s || s.length > 70 || isBullet(line)) return false;
  if (s.split(/\s+/).length > 8) return false;
  return !/[.,;]$/.test(s);
}

function splitBlocks(text) {
  const blocks = [];
  let heading = "", kind = "body", buf = [];
  // Python's splitlines() drops a final empty line; split("\n") keeps it,
  // which left an extra empty block at the end of every posting.
  const lines = text.split("\n");
  if (lines.length && lines[lines.length - 1] === "") lines.pop();
  for (const raw of lines) {
    const candidate = jdLooksLikeHeading(raw) ? classifyHeading(raw) : null;
    if (candidate) {
      if (buf.length) blocks.push([heading, kind, buf]);
      heading = raw.trim(); kind = candidate; buf = [];
      continue;
    }
    buf.push(raw);
  }
  if (buf.length) blocks.push([heading, kind, buf]);
  return blocks.map(([h, k, b]) => [h, k, b.join("\n").trim()]);
}

function extractTitle(text) {
  for (const raw of text.split("\n").slice(0, 12)) {
    const line = raw.trim().replace(/^[#*_\s]+|[#*_\s]+$/g, "");
    if (!line || line.length > 90) continue;
    const low = normalize(line);
    if (/^(job title|title|position|role)/.test(low)) {
      const part = line.split(/[:\-–]/);
      if (part.length >= 2 && part.slice(1).join("-").trim()) return part.slice(1).join("-").trim();
      continue;
    }
    if (/^(about|we are|our |company)/.test(low)) continue;
    if (line.split(/\s+/).length <= 12 && !line.endsWith(".")) return line;
  }
  return "";
}

function findHardRequirements(blocks) {
  const hard = [];
  for (const [, kind, body] of blocks) {
    if (kind === "noise" || kind === "preferred") continue;
    for (const raw of body.split("\n")) {
      const line = raw.trim();
      if (!line || METADATA_LINE_RE.test(line)) continue;
      const nice = NICE_MARKERS.exec(line);
      const m = line.match(YEARS_RE);
      // "10+ years ... hospice experience strongly preferred": the preference
      // qualifies the clause after it, not the minimum before it.
      if (nice && (!m || nice.index < m.index)) continue;
      if (m && /experience|background|working/i.test(line)) {
        hard.push({ kind: "years", detail: m[0].trim(), value: parseFloat(m[1]), context: line });
      }
      if (nice) continue;
      if (DEGREE_RE.test(line) && /degree|diploma|bachelor|master|phd|ged/i.test(line)) {
        hard.push({ kind: "degree", detail: line.match(DEGREE_RE)[0], value: degreeRank(line), context: line });
      }
      const c = line.match(CLEARANCE_RE);
      if (c) hard.push({ kind: "clearance", detail: c[0], value: null, context: line });
      const lic = licenseRequired(line);
      if (lic && (kind === "required" || MUST_MARKERS.test(line) || /\brequired\b/i.test(line))) {
        hard.push({ kind: "license", detail: lic, value: null, context: line });
      }
    }
  }
  return hard;
}

function isCandidate(phrase, key, lexicon, proper) {
  if (!key || key.length < 2) return false;
  const words = phrase.split(" ");
  const vouched = !!(lexicon && lexicon.resolve(phrase) !== null);
  // A coordinator ("and"/"or") joins two terms; a genitive ("of") sits inside
  // one. Only the first forbids an unvouched phrase.
  if (words.some((w) => STOPWORDS.has(w))) {
    const coordinated = words.some((w) => w === "and" || w === "or");
    if (!vouched && (coordinated || !proper)) return false;
  }
  if (words.some((w) => BOILERPLATE.has(w))) return false;
  if (words.some((w) => REQUIREMENT_LANGUAGE.has(w))) return false;
  if (words.length === 1) {
    const w = words[0];
    if (STOPWORDS.has(w) || /^\d+$/.test(w)) return false;
    if (w.length <= 2 && !ALLOWED_SHORT.has(w)) return false;
    if (VAGUE_SINGLES.has(w)) return false;
    if (MODIFIER_SUFFIXES.some((suf) => w.endsWith(suf))) return false;
  }
  if (words.every((w) => /^\d+$/.test(w) || w.length <= 2)) return false;
  // "15+" is a quantity, not a keyword.
  if (words.length && words.every((w) => /^\d+$/.test(w.replace(/[+-]+$/, "")))) return false;
  // A phrase hinged on a bare verb form is a slice of a sentence.
  if (words.length > 1 && (GERUND_HINGES.has(words[0]) || GERUND_HINGES.has(words[words.length - 1]))) {
    if (!lexicon || lexicon.resolve(phrase) === null) return false;
  }
  // A phrase made entirely of generic words names nothing.
  if (words.length > 1 && words.every((w) => VAGUE_SINGLES.has(w))) {
    if (!lexicon || lexicon.resolve(phrase) === null) return false;
  }
  if (words.some((w) => w.length === 1 && !/^\d$/.test(w))) return false;
  if (words.length >= 4 && !vouched && !proper) return false;
  if (words.length > 1 && CONTAINER_NOUNS.has(words[words.length - 1])) return false;
  if (words.length === 1 && CONTAINER_NOUNS.has(words[0])) return false;
  if (vouched) return true;

  // Everything below removes slices of sentences no resume could be asked to
  // contain. Together they were over a third of the keyword weight against a
  // real posting -- a ceiling no honest resume could reach.
  if (words.some((w) => RESIDENCY_WORDS.has(w))) return false;            // "dfw area"
  const first = words[0], last = words[words.length - 1];
  if (words.length === 1) {
    if (first.endsWith("ing") && !NOMINAL_GERUNDS.has(first)) return false;   // "providing"
    if (VERB_FORMS.has(first) && !NOMINAL_GERUNDS.has(first)) return false;   // "reflect"
    if (first.endsWith("ed") && first.length > 4 && !proper) return false;    // "resourced"
    if (first.endsWith("ly") && first.length > 4) return false;               // "proactively"
    return true;
  }
  if (VERB_FORMS.has(first) || (first.endsWith("ing") && !NOMINAL_GERUNDS.has(first))) return false;
  if (TRAILING_MODIFIERS.has(first) || (first.endsWith("ly") && first.length > 4)) return false;
  if (VERB_FORMS.has(last) && !NOUN_VERB_HOMOGRAPHS.has(last)
      && !NOMINAL_GERUNDS.has(last) && !last.endsWith("ing")) return false;   // "decision reflects"
  if (last.endsWith("ly") || TRAILING_MODIFIERS.has(last)) return false;      // "travel regularly"
  if (last.endsWith("ing") && !NOMINAL_GERUNDS.has(last)) return false;       // "registered nurse living"
  return true;
}

/* Mining 1-4 grams yields "security operations", "operations center" and
   "operations" alongside "security operations center". Reporting all four as
   separate gaps triples the apparent work and buries the real one. */
function suppressSubsumed(found) {
  const anchors = [...found.values()]
    .filter((r) => r.term.split(" ").length > 1)
    .sort((a, b) => (b.knownSkill - a.knownSkill) || (b.term.length - a.term.length));
  for (const anchor of anchors) {
    const parent = " " + anchor.term + " ";
    for (const [cid, req] of [...found.entries()]) {
      if (req === anchor || req.knownSkill || !found.has(cid)) continue;
      if (req.term.length >= anchor.term.length) continue;
      if (parent.includes(" " + req.term + " ") && req.count <= anchor.count) found.delete(cid);
    }
  }
}

function mineTerms(blocks, lexicon, exclude) {
  const found = new Map();
  for (const [, kind, body] of blocks) {
    if (kind === "noise") continue;
    const base = { required: 1.7, preferred: 0.55, responsibility: 1.15 }[kind] || 1.0;
    for (const raw of body.split("\n")) {
      let line = (isBullet(raw) ? stripBullet(raw) : raw).trim();
      if (!line || line.length < 3) continue;
      if (METADATA_LINE_RE.test(line)) continue;
      // "Reporting to the SVP & General Manager, this leader..." names a
      // manager, not a skill. The clause goes; the sentence stays.
      line = line.replace(REPORTING_CLAUSE_RE, " ");
      let lineWeight = base;
      const must = MUST_MARKERS.test(line), nice = NICE_MARKERS.test(line);
      if (must) lineWeight *= 1.45;
      if (nice) lineWeight *= 0.45;

      const seen = new Set();
      // Five raw tokens: a four-word skill containing a glue word
      // ("security information and event management") needs five, and the
      // candidate filter rejects long phrases the lexicon does not vouch for.
      for (const phrase of phraseNgrams(line, 1, 5)) {
        const key = canonical(phrase);
        if (!key || seen.has(key)) continue;
        const proper = phrase.split(" ").length > 1 && isProper(phrase, line);
        if (!isCandidate(phrase, key, lexicon, proper)) continue;
        if (exclude && phrase.split(" ").some((w) => exclude.has(w))) continue;
        seen.add(key);
        const resolved = lexicon.resolve(phrase);
        const known = resolved !== null;
        const cid = resolved || key;
        let req = found.get(cid);
        if (!req) {
          req = { term: phrase, canonicalTerm: cid, weight: 0, count: 0, required: false,
                  preferred: false, knownSkill: known, proper,
                  category: resolved ? lexicon.category(resolved) : "keyword", contexts: [] };
          found.set(cid, req);
        } else if (known && phrase.length > req.term.length && !req.knownSkill) {
          req.term = phrase;
        }
        if (proper) req.proper = true;
        if (phrase.split(" ").length > req.term.split(" ").length && known === req.knownSkill) {
          req.term = phrase;
        }
        req.count += 1;
        req.weight += lineWeight * (1.0 + 0.35 * (phrase.split(" ").length - 1));
        if (known) req.knownSkill = true;
        if (kind === "required" || must) req.required = true;
        if (kind === "preferred" || nice) req.preferred = true;
        if (req.contexts.length < 3) req.contexts.push(line.slice(0, 200));
      }
    }
  }
  // A three-word phrase the posting used once, that neither the lexicon nor
  // the author's capitalisation vouches for, is a sentence fragment.
  for (const [cid, r] of [...found.entries()]) {
    if (r.term.split(" ").length >= 3 && r.count < 2 && !r.knownSkill && !r.proper) found.delete(cid);
  }
  suppressSubsumed(found);
  for (const req of found.values()) {
    req.weight = req.weight * (1.0 + Math.log1p(req.count) * 0.25);
    if (req.knownSkill) req.weight *= 1.6;
    else if (req.term.split(" ").length >= 3) req.weight *= 0.55;
    if (req.required && !req.preferred) req.weight *= 1.15;
    if (req.preferred && !req.required) req.weight *= 0.7;
  }
  return found;
}

function parseJD(text, lexicon) {
  const blocks = splitBlocks(text);
  const jd = { text, blocks, title: extractTitle(text),
               requirements: [],
               hardRequirements: findHardRequirements(blocks),
               responsibilityLines: [], requirementLines: [],
               minYears: null, minDegree: null, clearance: null };

  const years = jd.hardRequirements.filter((h) => h.kind === "years" && h.value).map((h) => h.value);
  jd.minYears = years.length ? Math.min(...years) : null;
  const degrees = jd.hardRequirements.filter((h) => h.kind === "degree" && h.value).map((h) => h.value);
  if (degrees.length) {
    const rank = Math.min(...degrees);
    jd.minDegree = Object.entries(DEGREE_RANK).find(([, v]) => v === rank)?.[0] || null;
  }
  // A company name can contain a common noun ("WNS Global Services"). If the
  // word recurs through the requirements it is a real term too.
  const candidates = companyTokens(text, lexicon);
  const body = normalize(blocks.filter(([, k]) => k === "required" || k === "responsibility")
    .map(([, , t]) => t).join("\n"));
  jd.companyTokens = new Set([...candidates].filter((tok) =>
    (body.match(new RegExp("\\b" + tok.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "\\b", "g")) || []).length < 3));
  const places = new Set([...locationTokens(text)].filter((t) =>
    lexicon.resolve(t) === null
    && (body.match(new RegExp("\\b" + t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "\\b", "g")) || []).length < 3));
  jd.requirements = [...mineTerms(blocks, lexicon, new Set([...jd.companyTokens, ...places])).values()];

  const clr = jd.hardRequirements.filter((h) => h.kind === "clearance");
  jd.clearance = clr.length ? clr[0].detail : null;

  for (const [, kind, body] of blocks) {
    let target = null;
    if (kind === "responsibility") target = jd.responsibilityLines;
    else if (kind === "required" || kind === "preferred") target = jd.requirementLines;
    if (!target) continue;
    for (const raw of body.split("\n")) {
      const line = (isBullet(raw) ? stripBullet(raw) : raw).trim();
      if (line.length > 25) target.push(line);
    }
  }
  jd.signalText = blocks.filter(([, k]) => k !== "noise").map(([, , t]) => t).join("\n");
  jd.top = (n) => [...jd.requirements].sort((a, b) => b.weight - a.weight).slice(0, n);
  return jd;
}

// -------------------------------------------------------------- match ----
const FUZZY_THRESHOLD = 0.86;

class ResumeIndex {
  constructor(text, skillsText, recentText) {
    this.text = text;
    this.normLines = text.split("\n").filter((l) => l.trim());
    this.tokens = tokenize(text);
    this.stems = this.tokens.map(stem);
    this.joined = " " + this.stems.join(" ") + " ";
    this.skillsJoined = skillsText ? " " + stems(skillsText).join(" ") + " " : "";
    this.recentJoined = recentText ? " " + stems(recentText).join(" ") + " " : "";
    this.lineIndex = this.normLines.map((ln) => [" " + stems(ln).join(" ") + " ", ln.trim()]);
    this.vocab = new Set(this.stems);
    this.byInitial = new Map();
    for (const word of this.vocab) {
      const k = word.slice(0, 1);
      if (!this.byInitial.has(k)) this.byInitial.set(k, []);
      this.byInitial.get(k).push(word);
    }
  }
  countOf(haystack, needle) {
    if (!haystack) return 0;
    let n = 0, i = haystack.indexOf(needle);
    while (i !== -1) { n++; i = haystack.indexOf(needle, i + 1); }
    return n;
  }
  contains(phrase) {
    const key = canonical(phrase);
    if (!key) return [false, 0];
    const count = this.countOf(this.joined, " " + key + " ");
    return [count > 0, count];
  }
  findLine(phrase) {
    const key = canonical(phrase);
    if (!key) return "";
    const needle = " " + key + " ";
    for (const [blob, raw] of this.lineIndex) if (blob.includes(needle)) return raw;
    return "";
  }
  inSkills(phrase) {
    const key = canonical(phrase);
    return !!key && this.skillsJoined.includes(" " + key + " ");
  }
  inRecent(phrase) {
    const key = canonical(phrase);
    return !!key && this.recentJoined.includes(" " + key + " ");
  }
  fuzzyWord(word, threshold) {
    if (word.length < 5) return null;  // short tokens are too easy to confuse
    let best = null, bestScore = threshold;
    for (const cand of this.byInitial.get(word.slice(0, 1)) || []) {
      if (Math.abs(cand.length - word.length) > 3) continue;
      const s = similarity(word, cand);
      if (s > bestScore) { best = cand; bestScore = s; }
    }
    return best;
  }
  /* Presence alone is not a phrase match. "Security Analyst", "Information
     Technology" and "vulnerability management" would otherwise combine into
     "security information and event management" across three unrelated lines. */
  fuzzyPhrase(parts, threshold) {
    if (parts.length < 2) return null;
    const resolved = new Map();
    for (const part of parts) {
      if (this.vocab.has(part)) resolved.set(part, part);
      else { const a = this.fuzzyWord(part, threshold); if (a) resolved.set(part, a); }
    }
    const needed = Math.max(2, Math.ceil(parts.length * 0.75));
    if (resolved.size < needed) return null;
    const targets = new Set(resolved.values());
    const positions = [];
    this.stems.forEach((t, i) => { if (targets.has(t)) positions.push([i, t]); });
    if (positions.length < needed) return null;
    const window = parts.length + 1;
    let left = 0;
    const seen = new Map();
    for (let right = 0; right < positions.length; right++) {
      const tok = positions[right][1];
      seen.set(tok, (seen.get(tok) || 0) + 1);
      while (positions[right][0] - positions[left][0] > window) {
        const lt = positions[left][1];
        seen.set(lt, seen.get(lt) - 1);
        if (seen.get(lt) === 0) seen.delete(lt);
        left++;
      }
      if (seen.size >= needed) {
        return this.tokens.slice(positions[left][0], Math.min(this.tokens.length, positions[right][0] + 1)).join(" ");
      }
    }
    return null;
  }
  fuzzy(phrase, threshold) {
    threshold = threshold === undefined ? FUZZY_THRESHOLD : threshold;
    const key = canonical(phrase);
    if (!key) return null;
    const parts = key.split(" ");
    return parts.length > 1 ? this.fuzzyPhrase(parts, threshold) : this.fuzzyWord(key, threshold);
  }
}

function outsideSkills(index, form) {
  const key = canonical(form);
  if (!key) return false;
  const needle = " " + key + " ";
  return index.countOf(index.joined, needle) > index.countOf(index.skillsJoined, needle);
}

function matchCredit(m) {
  if (m.status === "missing") return 0;
  let base = { exact: 1.0, alias: 0.92, fuzzy: 0.6 }[m.status];
  // Present only in a skills list, never demonstrated in context. Keyword
  // filters accept this; AI screeners increasingly do not.
  if (m.inSkillsOnly) base *= 0.82;
  if (m.inRecentRole) base *= 1.05;
  return Math.min(1.0, base);
}

function matchRequirements(requirements, index, lexicon) {
  const out = [];
  for (const req of requirements) {
    let forms = [req.term];
    if (req.knownSkill) forms = [...new Set([req.term, ...lexicon.variantsOf(req.term)])];
    let best = null;
    for (let i = 0; i < forms.length; i++) {
      const [present, count] = index.contains(forms[i]);
      if (present) {
        // The skills-list penalty is for a capability you listed but never
        // showed doing. Showing it under a different name is still showing it.
        const demonstrated = forms.some((f) => outsideSkills(index, f));
        best = { requirement: req, status: i === 0 ? "exact" : "alias", matchedForm: forms[i],
                 evidence: index.findLine(forms[i]), occurrences: count,
                 inRecentRole: index.inRecent(forms[i]),
                 inSkillsOnly: index.inSkills(forms[i]) && !demonstrated };
        break;
      }
    }
    if (!best) {
      for (const form of forms) {
        const approx = index.fuzzy(form);
        if (approx) {
          best = { requirement: req, status: "fuzzy", matchedForm: approx,
                   evidence: index.findLine(approx), occurrences: 1,
                   inRecentRole: false, inSkillsOnly: false };
          break;
        }
      }
    }
    if (!best) best = { requirement: req, status: "missing", matchedForm: "", evidence: "",
                        occurrences: 0, inRecentRole: false, inSkillsOnly: false };
    best.credit = matchCredit(best);
    out.push(best);
  }
  return out;
}

function bm25(queryTokens, docTokens, k1 = 1.5, b = 0.75) {
  if (!queryTokens.length || !docTokens.length) return 0;
  const docLen = docTokens.length, avgLen = docLen || 1;
  const freqs = new Map();
  for (const t of docTokens) freqs.set(t, (freqs.get(t) || 0) + 1);
  let score = 0;
  for (const term of new Set(queryTokens)) {
    const f = freqs.get(term) || 0;
    if (!f) continue;
    const idf = Math.log(1 + (1 - 1 + 0.5) / (1 + 0.5));
    score += idf * (f * (k1 + 1)) / (f + k1 * (1 - b + b * docLen / avgLen));
  }
  return score;
}

function tfIdf(docs) {
  const n = docs.length, df = new Map();
  for (const doc of docs) for (const t of new Set(doc)) df.set(t, (df.get(t) || 0) + 1);
  return docs.map((doc) => {
    const counts = new Map();
    for (const t of doc) counts.set(t, (counts.get(t) || 0) + 1);
    const total = doc.length || 1;
    const vec = new Map();
    for (const [term, count] of counts) {
      vec.set(term, (count / total) * (Math.log((n + 1) / (df.get(term) + 1)) + 1.0));
    }
    return vec;
  });
}

function cosine(a, b) {
  if (!a.size || !b.size) return 0;
  let num = 0;
  const [small, large] = a.size < b.size ? [a, b] : [b, a];
  for (const [t, v] of small) if (large.has(t)) num += v * large.get(t);
  let na = 0, nb = 0;
  for (const v of a.values()) na += v * v;
  for (const v of b.values()) nb += v * v;
  na = Math.sqrt(na); nb = Math.sqrt(nb);
  return na && nb ? num / (na * nb) : 0;
}

/* Separates "the word appears in a skills blob" from "the candidate describes
   doing the thing", which is what LLM-based screeners are asked to judge. */
function contextualCoverage(jdLines, resumeLines) {
  const jdDocs = jdLines.map((l) => stems(l));
  const resDocs = resumeLines.map((l) => stems(l));
  if (!jdDocs.length || !resDocs.length) return jdLines.map((l) => [l, 0, ""]);
  const vectors = tfIdf([...jdDocs, ...resDocs]);
  const jdVecs = vectors.slice(0, jdDocs.length);
  const resVecs = vectors.slice(jdDocs.length);
  return jdLines.map((line, i) => {
    let bestScore = 0, bestLine = "";
    resVecs.forEach((rv, j) => {
      const s = cosine(jdVecs[i], rv);
      if (s > bestScore) { bestScore = s; bestLine = resumeLines[j]; }
    });
    return [line, bestScore, bestLine];
  });
}

// ------------------------------------------------------ parseability ----
const SEVERITY_ORDER = { blocker: 0, major: 1, minor: 2 };
const SEVERITY_PENALTY = { blocker: 34.0, major: 12.0, minor: 4.0 };
const RISKY_FONTS = new Set(["wingdings", "webdings", "symbol", "zapfdingbats", "marlett",
  "bookshelf symbol 7", "monotype sorts"]);
const EXOTIC_BULLETS = "▪◆◇■□▶►✔✓✦❖➢➤";

const COVER_LETTER_MARKERS = ["dear hiring manager", "dear sir or madam",
  "to whom it may concern", "i am writing to express", "i am writing to apply",
  "cover letter", "thank you for considering my application"];

function auditDocument(doc, resume, repairs) {
  const findings = [];
  const add = (severity, code, message, fix) => findings.push({ severity, code, message, fix });
  const text = doc.text || "";
  const words = text.split(/\s+/).filter(Boolean).length;

  for (const note of (repairs || [])) {
    add("blocker", "encoding.symbolbullets", note.charAt(0).toUpperCase() + note.slice(1) + ".",
      "Replace them with your word processor's standard bullet list. The scores below "
      + "assume the repair; without it every accomplishment reads to a parser as prose.");
  }
  const head = text.replace(/\s+/g, " ").slice(0, 2500).toLowerCase();
  if (COVER_LETTER_MARKERS.some((m) => head.includes(m))) {
    add("major", "content.coverletter", "The file appears to open with a cover letter.",
      "Upload the cover letter as a separate document. Bound in here it becomes page one "
      + "of the resume, pushing the work history down and diluting the keyword index.");
  }

  for (const w of doc.warnings || []) {
    add("blocker", "extract.warning", w,
      "Export a text-based PDF directly from Word or Google Docs (File > Save as PDF), never a scan or photo.");
  }
  if (words < 120 && doc.kind !== "txt") {
    add("blocker", "extract.empty", `Only ${words} words of text could be recovered from this file.`,
      "If the resume looks full when you open it, the content is locked inside images or shapes. Rebuild it as ordinary body text.");
  }
  if (doc.columns && doc.columns > 1) {
    add("blocker", "layout.columns", `The document uses a ${doc.columns}-column section layout.`,
      "Switch to a single-column layout. Parsers read left-to-right across the whole page, which interleaves the columns into unusable text.");
  }
  if (doc.textBoxes) {
    add("blocker", "layout.textbox",
      `${doc.textBoxes} text box(es) hold roughly ${doc.textBoxChars} characters.`,
      "Move text box content into the main document body. Most parsers skip text boxes entirely, so anything in them is invisible.");
  }
  if (doc.tables) {
    add(doc.tableTextChars > 400 ? "major" : "minor", "layout.tables",
      `${doc.tables} table(s) contain about ${doc.tableTextChars} characters.`,
      "Replace tables with plain paragraphs and simple bullet lists. Table cells are frequently read out of order or merged together.");
  }
  if (doc.headerFooterChars > 40) {
    add("major", "layout.headerfooter",
      `About ${doc.headerFooterChars} characters sit in the page header or footer.`,
      "Move anything important -- especially your name, email and phone -- into the body of the first page. Headers and footers are routinely discarded before parsing.");
  }
  if (doc.images) {
    add("minor", "layout.images", `The file embeds ${doc.images} image(s).`,
      "Make sure no skill, date or contact detail exists only inside an image, icon, logo or skill-rating graphic -- none of it is readable.");
  }
  const risky = (doc.fonts || []).filter((f) => RISKY_FONTS.has(f.toLowerCase()));
  if (risky.length) {
    add("minor", "layout.fonts", `Symbol fonts in use: ${[...new Set(risky)].sort().join(", ")}.`,
      "Use a standard text font. Symbol fonts often extract as random letters that pollute your keyword match.");
  }

  const contact = resume.contact;
  if (!contact.email) {
    add("blocker", "contact.email", "No email address was found in the resume text.",
      "Put your email as plain selectable text near the top. If it is there but not detected, it is probably inside a header, a text box or an image.");
  }
  if (!contact.phone) {
    add("major", "contact.phone", "No phone number was found in the resume text.",
      "Add a phone number in a standard format, e.g. (555) 010-2233.");
  }
  if (!contact.nameGuess) {
    add("minor", "contact.name", "A candidate name could not be identified in the first few lines.",
      "Put your full name alone on the first line, in body text rather than a graphic or a header.");
  }
  if (contact.email && doc.headerFooterChars && !EMAIL_RE.test(resume.text.split("\n").slice(0, 15).join("\n"))) {
    add("major", "contact.buried", "Contact details do not appear near the top of the document body.",
      "Move them to the first few lines of page one.");
  }

  const present = new Set(resume.sectionOrder);
  const SECTION_CHECKS = [
    ["experience", "blocker", "Without a recognised experience heading, the parser cannot build a work history, and many systems then treat the application as having no relevant experience."],
    ["education", "major", "Education is a standard indexed field and is often used for automatic filtering."],
    ["skills", "minor", "A skills section gives the keyword index a dense, unambiguous block to read."],
  ];
  for (const [name, severity, why] of SECTION_CHECKS) {
    if (!present.has(name)) {
      const label = name.charAt(0).toUpperCase() + name.slice(1);
      add(severity, `section.${name}`, `No recognised '${name}' section heading was found.`,
        `Add a plain heading such as '${label}'. ${why}`);
    }
  }
  if (resume.unrecognizedHeadings.length) {
    add("minor", "section.custom",
      `Non-standard heading(s) detected: ${resume.unrecognizedHeadings.slice(0, 4).join(", ")}.`,
      "Creative headings are not in any parser's vocabulary. Use conventional names.");
  }

  if (!resume.roles.length) {
    add("blocker", "dates.noroles", "No dated positions could be reconstructed from the experience section.",
      "Give every role a heading with a date range on the same line, e.g. 'Security Analyst | Contoso | Mar 2022 - Present'.");
  } else {
    const undated = resume.roles.filter((r) => !r.start);
    if (undated.length) {
      add("major", "dates.missing", `${undated.length} position(s) have no parsable date range.`,
        "Use a consistent 'Mon YYYY - Mon YYYY' or 'YYYY - YYYY' format on the same line as the job title.");
    }
    if (!resume.roles.some((r) => r.isCurrent)) {
      const ends = resume.roles.filter((r) => r.end).map((r) => r.end);
      if (ends.length) {
        const latest = ends.reduce((a, b) => (ymToInt(a) > ymToInt(b) ? a : b));
        const now = todayYM();
        if ((now[0] - latest[0]) * 12 + (now[1] - latest[1]) > 8) {
          add("minor", "dates.stale",
            `The most recent dated role ended around ${String(latest[1]).padStart(2, "0")}/${latest[0]}.`,
            "If you are currently employed, mark the role 'Present' so the parser records you as actively working.");
        }
      }
    }
  }

  if (text.includes("\uFFFD")) {  // literal replacement char, written escaped
    add("major", "encoding.replacement", "The text contains replacement characters, a sign of a broken font or encoding.",
      "Retype the affected lines, or rebuild the document from a clean template.");
  }
  const exotic = [...new Set([...text].filter((c) => EXOTIC_BULLETS.includes(c)))];
  if (exotic.length) {
    add("minor", "encoding.bullets", `Decorative bullet glyphs in use: ${exotic.sort().join(" ")}.`,
      "Use your word processor's standard bullet list. Decorative glyphs sometimes take the rest of the line with them.");
  }
  const spaced = text.split("\n").map((l) => l.trim()).filter(isLetterSpaced);
  if (spaced.length) {
    const sample = spaced.slice(0, 3).map((x) => x.slice(0, 32)).join("; ");
    add(spaced.length >= 4 ? "blocker" : "major", "encoding.spaced",
      `${spaced.length} line(s) are letter-spaced and unreadable to a parser: ${sample}.`,
      "Set letter-spacing in the font instead of typing spaces between letters. As typed, "
      + "these words -- often the section headings and the whole skills list -- do not "
      + "exist as far as an ATS is concerned.");
  }
  const tabs = text.split("\n").filter((l) => (l.match(/\t/g) || []).length >= 2).length;
  if (tabs > 6) {
    add("minor", "encoding.tabs", `${tabs} lines use multiple tab stops to simulate columns.`,
      "Tab-aligned pseudo-columns can be read as one run-on line. Prefer separate lines.");
  }

  if (words > 1400) {
    add("minor", "length.long", `The resume is ${words} words, which is long for a screening read.`,
      "Aim for roughly 450-900 words (1-2 pages) unless the posting asks for a full CV.");
  } else if (words > 0 && words < 220) {
    add("major", "length.short", `The resume is only ${words} words.`,
      "Thin content gives the keyword index almost nothing to match. Expand each role with concrete, quantified accomplishments.");
  }
  if (doc.pages && doc.pages > 3) {
    add("minor", "length.pages", `The PDF is ${doc.pages} pages.`,
      "Trim to two pages unless this is an academic or federal CV.");
  }

  const penalty = findings.reduce((acc, f) => acc + SEVERITY_PENALTY[f.severity], 0);
  findings.sort((a, b) => (SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity])
    || a.code.localeCompare(b.code));
  return {
    findings,
    score: Math.max(0, 100 - penalty),
    count: (sev) => findings.filter((f) => f.severity === sev).length,
  };
}

// -------------------------------------------------------------- score ----
const WEIGHTS = { parseability: 22.0, keywords: 30.0, context: 14.0, title: 10.0,
                  experience: 10.0, education: 6.0, writing: 8.0 };
const RELATED_THRESHOLD = 0.10;
const BANDS = [
  [85, "Strong", "Competitive on keyword screening; focus on the cover note and referrals."],
  [70, "Good", "Likely to clear automated filters. Close the top gaps to be safe."],
  [55, "Borderline", "Could go either way. The gaps below are worth fixing before you apply."],
  [40, "Weak", "Likely to be filtered out. Address the blockers and top missing terms."],
  [0, "Poor", "Very unlikely to reach a human in this form."],
];

const TITLE_NOISE = new Set(["ii", "iii", "iv", "sr", "jr", "senior", "junior", "staff", "lead"]);

function titleScore(jd, resume) {
  if (!jd.title) return [70.0, "no requisition title detected; scored neutrally"];
  const target = new Set(stems(jd.title).filter((t) => !TITLE_NOISE.has(t)));
  if (!target.size) return [70.0, "requisition title had no distinctive words"];
  const candidates = [];
  resume.roles.forEach((role, i) => {
    const got = new Set(stems(role.title));
    if (!got.size) return;
    let overlap = 0;
    for (const t of target) if (got.has(t)) overlap++;
    candidates.push([(overlap / target.size) * (i === 0 ? 1.0 : 0.85), role.title]);
  });
  // A headline under the name is standard practice and is exactly what a title
  // match should see, but it sits above the first section heading.
  for (const raw of resume.section("_header").split("\n")) {
    const line = raw.trim();
    if (!line || line.split(/\s+/).length > 12) continue;
    if (EMAIL_RE.test(line) || PHONE_RE.test(line) || /(?:https?:\/\/|www\.)/i.test(line)) continue;
    const got = new Set(stems(line));
    if (!got.size) continue;
    let overlap = 0;
    for (const t of target) if (got.has(t)) overlap++;
    candidates.push([(overlap / target.size) * 0.95, `headline "${line}"`]);
  }

  const summary = resume.section("summary");
  if (summary) {
    const got = new Set(stems(summary));
    let overlap = 0;
    for (const t of target) if (got.has(t)) overlap++;
    candidates.push([(overlap / target.size) * 0.8, "summary"]);
  }
  if (!candidates.length) return [25.0, "no job titles found to compare"];
  const best = candidates.reduce((a, b) => (a[0] >= b[0] ? a : b));
  const pct = Math.min(100.0, best[0] * 100.0);
  return [pct, `best title overlap ${pct.toFixed(0)}% (from "${best[1]}") against "${jd.title}"`];
}

function experienceScore(jd, resume) {
  const have = resume.yearsExperience, need = jd.minYears;
  if (need === null) {
    return have <= 0
      ? [60.0, "no minimum stated; no dated experience found in resume"]
      : [100.0, `no minimum stated; resume evidences about ${have} years`];
  }
  if (have <= 0) return [15.0, `posting asks for ${need}+ years; none could be parsed from dates`];
  const ratio = have / need;
  // A stated minimum is a threshold: an ATS asks whether years >= minimum, and
  // exceeding it is a full pass. Docking someone for being well over the bar
  // encoded a human screening dynamic this component does not model.
  const s = ratio >= 1.0 ? 100.0 : Math.max(10.0, 100.0 * Math.pow(ratio, 1.5));
  return [s, `posting asks ${need}+ years; resume evidences about ${have} years`];
}

/* Not limited to the education section: a design-led layout can place the
   heading after the degrees it labels, and trusting that section alone reported
   a real candidate's MBA as "no degree detected", failing a gate he meets. */
function degreeEvidence(resume) {
  const sectioned = degreeRank(resume.section("education") + "\n" + resume.section("certifications"));
  return Math.max(sectioned, degreeRank(resume.text));
}

function educationScore(jd, resume) {
  const have = degreeEvidence(resume);
  if (jd.minDegree === null) {
    // A posting stating no requirement cannot be under-met; holding a degree
    // anyway is full marks. The old 85 ceiling docked a gap that did not exist.
    return have ? [100.0, "no degree requirement stated; resume shows a degree"]
                : [70.0, "no degree requirement stated; none detected"];
  }
  const need = degreeRank(jd.minDegree);
  if (have >= need) return [100.0, `posting asks for a ${jd.minDegree} degree; resume shows an equal or higher degree`];
  if (have) return [55.0, `posting asks for a ${jd.minDegree} degree; a lower degree was detected`];
  return [25.0, `posting asks for a ${jd.minDegree} degree; none detected in the resume`];
}

function writingScore(resume) {
  const bullets = resume.experienceBullets || resume.bullets;
  if (!bullets.length) return [35.0, "no bullet points detected"];
  let quantified = 0, strong = 0, weak = 0, longB = 0;
  for (const b of bullets) {
    if (METRIC_RE.test(b)) quantified++;
    const strength = openerStrength(b);
    if (strength === "strong") strong++;
    else if (strength === "weak") weak++;
    if (b.split(/\s+/).length > 45) longB++;
  }
  const n = bullets.length;
  const quantRatio = quantified / n, strongRatio = strong / n;
  let s = 100.0;
  s -= Math.max(0, 0.5 - quantRatio) * 90.0;
  s -= Math.max(0, 0.6 - strongRatio) * 55.0;
  s -= (weak / n) * 45.0;
  s -= (longB / n) * 25.0;
  s = Math.max(0, Math.min(100, s));
  return [s, `${n} bullets; ${quantified} quantified (${Math.round(quantRatio * 100)}%), ` +
             `${strong} strong openers (${Math.round(strongRatio * 100)}%), ${weak} weak openers`];
}

/* Cosine between two short lines is small even when they clearly describe the
   same work, so the raw mean is not usable. Blend breadth with depth. */
function contextScore(pairs) {
  if (!pairs.length) return [60.0, "no requirement lines available to compare"];
  const scores = pairs.map((p) => p[1]).sort((a, b) => b - a);
  const n = scores.length;
  const covered = scores.filter((s) => s >= RELATED_THRESHOLD).length;
  const breadth = covered / n;
  const topHalf = scores.slice(0, Math.max(1, Math.floor(n / 2)));
  const depth = Math.min(1.0, (topHalf.reduce((a, b) => a + b, 0) / topHalf.length) / 0.22);
  return [100.0 * (0.62 * breadth + 0.38 * depth),
          `${covered}/${n} requirement lines have a clearly related resume line`];
}

function evaluateGates(jd, resume, index) {
  const gates = [], seen = new Set();
  for (const hard of jd.hardRequirements) {
    const key = hard.kind + "|" + hard.detail.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    if (hard.kind === "years") {
      const need = hard.value || 0, have = resume.yearsExperience;
      gates.push({ kind: "years", detail: `${need}+ years of experience`, satisfied: have >= need,
                   evidence: `resume evidences about ${have} years`, note: hard.context.slice(0, 160) });
    } else if (hard.kind === "degree") {
      const need = Math.trunc(hard.value || 0);
      const have = degreeEvidence(resume);
      gates.push({ kind: "degree", detail: hard.detail, satisfied: have >= need,
                   evidence: have ? "degree detected" : "no degree detected",
                   note: hard.context.slice(0, 160) });
    } else if (hard.kind === "clearance") {
      let present = index.contains(hard.detail)[0];
      if (!present) present = !!resume.section("clearance");
      gates.push({ kind: "clearance", detail: hard.detail, satisfied: present,
                   evidence: present ? "mentioned in resume" : "not mentioned in resume",
                   note: hard.context.slice(0, 160) });
    } else if (hard.kind === "license") {
      const forms = [hard.detail].concat(LICENSES[hard.detail] || []);
      const present = forms.some((f) => index.contains(f)[0]);
      gates.push({ kind: "license", detail: `${hard.detail} license`, satisfied: present,
                   evidence: present ? "held per resume" : "not found on resume",
                   note: hard.context.slice(0, 160) });
    }
  }
  return gates;
}

function scoreResume(doc, jd, lexicon) {
  // Repair mechanical damage first, then measure. Scoring broken text reports a
  // content problem for what is really a font problem.
  const [repairedText, repairs] = repairLayout(doc.text);
  const resume = parseResume(repairedText);
  const recentText = resume.roles.length ? resume.roles[0].text : "";
  const index = new ResumeIndex(repairedText, resume.section("skills"), recentText);
  const matches = matchRequirements(jd.requirements, index, lexicon);

  const jdLines = [...jd.requirementLines, ...jd.responsibilityLines];
  const resumeLines = [...resume.bullets];
  for (const ln of repairedText.split("\n")) {
    const t = ln.trim();
    if (t.split(/\s+/).length > 4 && !resumeLines.includes(t)) resumeLines.push(t);
  }
  const pairs = contextualCoverage(jdLines, resumeLines);
  const audit = auditDocument(doc, resume, repairs);

  const totalW = matches.reduce((a, m) => a + m.requirement.weight, 0);
  const gotW = matches.reduce((a, m) => a + m.requirement.weight * m.credit, 0);
  const coverage = totalW > 0 ? gotW / totalW : 0;
  const kwScore = Math.min(100.0, coverage * 118.0);

  const [titleS, titleD] = titleScore(jd, resume);
  const [expS, expD] = experienceScore(jd, resume);
  const [eduS, eduD] = educationScore(jd, resume);
  const [wriS, wriD] = writingScore(resume);
  const [ctxS, ctxD] = contextScore(pairs);

  const components = [
    { name: "parseability", score: audit.score, weight: WEIGHTS.parseability,
      detail: `${audit.count("blocker")} blockers, ${audit.count("major")} major, ${audit.count("minor")} minor` },
    { name: "keywords", score: kwScore, weight: WEIGHTS.keywords,
      detail: `${Math.round(coverage * 100)}% weighted coverage of ${jd.requirements.length} mined terms` },
    { name: "context", score: ctxS, weight: WEIGHTS.context, detail: ctxD },
    { name: "title", score: titleS, weight: WEIGHTS.title, detail: titleD },
    { name: "experience", score: expS, weight: WEIGHTS.experience, detail: expD },
    { name: "education", score: eduS, weight: WEIGHTS.education, detail: eduD },
    { name: "writing", score: wriS, weight: WEIGHTS.writing, detail: wriD },
  ];
  components.forEach((c) => { c.points = (c.score / 100) * c.weight; });

  let total = components.reduce((a, c) => a + c.points, 0);
  const gates = evaluateGates(jd, resume, index);
  const failed = gates.filter((g) => !g.satisfied);
  // A failed gate caps the score rather than merely subtracting from it,
  // because that is how a knockout filter behaves.
  let gatePenalty = 0;
  if (failed.length) {
    const cap = failed.length === 1 ? 62.0 : 48.0;
    if (total > cap) { gatePenalty = total - cap; total = cap; }
  }
  const bandRow = BANDS.find(([t]) => total >= t) || BANDS[BANDS.length - 1];

  const report = {
    total: Math.round(total * 10) / 10, band: bandRow[1], verdict: bandRow[2],
    components, gates, matches, parse: audit, resume, jd, document: doc,
    coverage, contextPairs: pairs, gatePenalty: Math.round(gatePenalty * 10) / 10,
    failedGates: failed,
    bm25: bm25(stems(jd.signalText), index.stems),
    missing: (limit) => matches.filter((m) => m.status === "missing")
      .sort((a, b) => b.requirement.weight - a.requirement.weight).slice(0, limit),
    matched: (limit) => matches.filter((m) => m.status === "exact" || m.status === "alias")
      .sort((a, b) => b.requirement.weight - a.requirement.weight).slice(0, limit),
    weak: (limit) => matches
      .filter((m) => m.status === "fuzzy" || (m.status !== "missing" && m.inSkillsOnly))
      .sort((a, b) => b.requirement.weight - a.requirement.weight).slice(0, limit),
    component: (name) => components.find((c) => c.name === name),
  };
  report.suggestions = buildSuggestions(report);
  return report;
}

function buildSuggestions(report) {
  const out = [];
  for (const f of report.parse.findings) {
    if (f.severity === "blocker") out.push(`Fix first (blocks parsing): ${f.message} ${f.fix}`.trim());
  }
  for (const g of report.failedGates) {
    out.push(`Hard requirement not evidenced -- ${g.detail} (${g.evidence}). If you do meet it, state it explicitly; if you do not, expect an automatic knockout regardless of everything else.`);
  }
  const missing = report.missing(8);
  if (missing.length) {
    out.push("Add the highest-weighted missing terms, each inside a real accomplishment bullet rather than a keyword list: "
      + missing.map((m) => `"${m.requirement.term}"`).join(", ") + ".");
  }
  const weak = report.weak(6);
  const skillsOnly = weak.filter((m) => m.inSkillsOnly);
  if (skillsOnly.length) {
    out.push("These appear only in your skills list: "
      + skillsOnly.slice(0, 6).map((m) => `"${m.requirement.term}"`).join(", ")
      + ". Show at least one of them being used in a bullet -- newer AI screeners weight demonstrated use over a keyword blob.");
  }
  const fuzzy = weak.filter((m) => m.status === "fuzzy");
  if (fuzzy.length) {
    out.push("Near-miss wording: " + fuzzy.slice(0, 6).map((m) => `"${m.requirement.term}"`).join(", ")
      + ". Match the posting's exact phrasing at least once -- literal string indexes do not credit paraphrases.");
  }
  const writing = report.component("writing");
  if (writing && writing.score < 70) {
    out.push(`Strengthen the bullets: open with an action verb and quantify the result (scope, percentage, time saved, volume handled). Currently ${writing.detail}.`);
  }
  const title = report.component("title");
  if (title && title.score < 55 && report.jd.title) {
    out.push(`Your titles do not align with "${report.jd.title}". If your actual title differs, add the posting's title as a parenthetical or in your summary line.`);
  }
  for (const f of report.parse.findings.filter((x) => x.severity === "major").slice(0, 4)) {
    out.push(`${f.message} ${f.fix}`.trim());
  }
  return out;
}

// ====================================================== docx generation ===
/* Writing a .docx in the browser with no library, mirroring the Python
   writer. The reader already parses OOXML by hand so it can see the
   constructs that break ATS parsers; the writer stays hand-rolled so the
   page's main output never depends on a CDN that might be blocked. */

const CRC_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    table[n] = c >>> 0;
  }
  return table;
})();

function crc32(bytes) {
  let c = 0xffffffff;
  for (let i = 0; i < bytes.length; i++) c = CRC_TABLE[(c ^ bytes[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

/* ZIP with stored (uncompressed) entries. A resume package is a few
   kilobytes, so compression buys nothing and STORED keeps the writer free of
   CompressionStream and its async plumbing. */
function zipStored(files) {
  const enc = new TextEncoder();
  const chunks = [];
  const central = [];
  let offset = 0;

  const u16 = (v) => [v & 0xff, (v >> 8) & 0xff];
  const u32 = (v) => [v & 0xff, (v >> 8) & 0xff, (v >> 16) & 0xff, (v >>> 24) & 0xff];

  for (const [name, content] of files) {
    const nameBytes = enc.encode(name);
    const data = typeof content === "string" ? enc.encode(content) : content;
    const crc = crc32(data);
    const local = [
      ...u32(0x04034b50), ...u16(20), ...u16(0), ...u16(0),
      ...u16(0), ...u16(0),                       // time, date
      ...u32(crc), ...u32(data.length), ...u32(data.length),
      ...u16(nameBytes.length), ...u16(0),
    ];
    chunks.push(new Uint8Array(local), nameBytes, data);
    central.push({ name: nameBytes, crc, size: data.length, offset });
    offset += local.length + nameBytes.length + data.length;
  }

  const dirStart = offset;
  for (const e of central) {
    const header = [
      ...u32(0x02014b50), ...u16(20), ...u16(20), ...u16(0), ...u16(0),
      ...u16(0), ...u16(0),
      ...u32(e.crc), ...u32(e.size), ...u32(e.size),
      ...u16(e.name.length), ...u16(0), ...u16(0), ...u16(0), ...u16(0),
      ...u32(0), ...u32(e.offset),
    ];
    chunks.push(new Uint8Array(header), e.name);
    offset += header.length + e.name.length;
  }

  const eocd = [
    ...u32(0x06054b50), ...u16(0), ...u16(0),
    ...u16(central.length), ...u16(central.length),
    ...u32(offset - dirStart), ...u32(dirStart), ...u16(0),
  ];
  chunks.push(new Uint8Array(eocd));

  const total = chunks.reduce((n, c) => n + c.length, 0);
  const out = new Uint8Array(total);
  let p = 0;
  for (const c of chunks) { out.set(c, p); p += c.length; }
  return out;
}

const xmlEscape = (s) => String(s).replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;" }[c]))
  .replace(/[\x00-\x08\x0b\x0c\x0e-\x1f]/g, "");

function runXml(run) {
  const props = [];
  if (run.bold) props.push("<w:b/>");
  if (run.italic) props.push("<w:i/>");
  if (run.color) props.push(`<w:color w:val="${run.color}"/>`);
  if (run.size) props.push(`<w:sz w:val="${run.size}"/><w:szCs w:val="${run.size}"/>`);
  const rpr = props.length ? `<w:rPr>${props.join("")}</w:rPr>` : "";
  return `<w:r>${rpr}<w:t xml:space="preserve">${xmlEscape(run.text)}</w:t></w:r>`;
}

/* CT_PPr is a sequence, not a choice: numPr, pBdr, spacing, ind, outlineLvl.
   Word tolerates a wrong order; the OOXML schema does not. */
function blockXml(b) {
  const props = [];
  if (b.kind === "bullet") props.push('<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>');
  if (b.ruleBelow) props.push('<w:pBdr><w:bottom w:val="single" w:sz="6" w:space="2" w:color="444444"/></w:pBdr>');
  props.push(`<w:spacing w:before="${b.spaceBefore || 0}" w:after="${b.spaceAfter == null ? 40 : b.spaceAfter}"/>`);
  if (b.kind === "bullet") props.push('<w:ind w:left="360" w:hanging="220"/>');
  if (b.kind === "heading") props.push('<w:outlineLvl w:val="0"/>');
  return `<w:p><w:pPr>${props.join("")}</w:pPr>${b.runs.map(runXml).join("")}</w:p>`;
}

const W_MAIN = "http://schemas.openxmlformats.org/wordprocessingml/2006/main";

function buildDocxBytes(blocks, { title = "Resume", author = "", font = "Calibri", size = 20 } = {}) {
  const body = blocks.map(blockXml).join("");
  const sect = '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/>'
    + '<w:pgMar w:top="720" w:right="720" w:bottom="720" w:left="720" w:header="0" w:footer="0" w:gutter="0"/>'
    + '<w:cols w:num="1" w:space="0"/></w:sectPr>';
  const decl = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>';
  const R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships";
  const PKG = "http://schemas.openxmlformats.org/package/2006/relationships";

  return zipStored([
    ["[Content_Types].xml", decl
      + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
      + '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
      + '<Default Extension="xml" ContentType="application/xml"/>'
      + '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
      + '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
      + '<Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>'
      + '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
      + "</Types>"],
    ["_rels/.rels", decl + `<Relationships xmlns="${PKG}">`
      + `<Relationship Id="rId1" Type="${R}/officeDocument" Target="word/document.xml"/>`
      + `<Relationship Id="rId2" Type="${PKG}/metadata/core-properties" Target="docProps/core.xml"/>`
      + "</Relationships>"],
    ["docProps/core.xml", decl
      + '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
      + 'xmlns:dc="http://purl.org/dc/elements/1.1/">'
      + `<dc:title>${xmlEscape(title)}</dc:title><dc:creator>${xmlEscape(author)}</dc:creator>`
      + "</cp:coreProperties>"],
    ["word/_rels/document.xml.rels", decl + `<Relationships xmlns="${PKG}">`
      + `<Relationship Id="rId1" Type="${R}/styles" Target="styles.xml"/>`
      + `<Relationship Id="rId2" Type="${R}/numbering" Target="numbering.xml"/>`
      + "</Relationships>"],
    ["word/document.xml", decl + `<w:document xmlns:w="${W_MAIN}"><w:body>${body}${sect}</w:body></w:document>`],
    ["word/styles.xml", decl + `<w:styles xmlns:w="${W_MAIN}"><w:docDefaults><w:rPrDefault><w:rPr>`
      + `<w:rFonts w:ascii="${font}" w:hAnsi="${font}" w:cs="${font}"/>`
      + `<w:sz w:val="${size}"/><w:szCs w:val="${size}"/>`
      + '</w:rPr></w:rPrDefault><w:pPrDefault><w:pPr>'
      + '<w:spacing w:after="40" w:line="240" w:lineRule="auto"/>'
      + "</w:pPr></w:pPrDefault></w:docDefaults>"
      + '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style></w:styles>'],
    ["word/numbering.xml", decl + `<w:numbering xmlns:w="${W_MAIN}">`
      + '<w:abstractNum w:abstractNumId="0"><w:multiLevelType w:val="hybridMultilevel"/>'
      + '<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/>'
      + '<w:lvlText w:val="•"/><w:lvlJc w:val="left"/>'
      + '<w:pPr><w:ind w:left="360" w:hanging="220"/></w:pPr>'
      + '<w:rPr><w:rFonts w:ascii="Symbol" w:hAnsi="Symbol" w:hint="default"/></w:rPr>'
      + "</w:lvl></w:abstractNum>"
      + '<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num></w:numbering>'],
  ]);
}

// =========================================================== tailoring ====
const SECTION_PLAN = [
  ["summary", "SUMMARY"], ["skills", "CORE COMPETENCIES"],
  ["experience", "PROFESSIONAL EXPERIENCE"], ["projects", "PROJECTS"],
  ["education", "EDUCATION"], ["certifications", "CERTIFICATIONS"],
  ["clearance", "SECURITY CLEARANCE"], ["awards", "AWARDS"],
  ["publications", "PUBLICATIONS"], ["volunteer", "VOLUNTEER EXPERIENCE"],
];
const MONTH_NAMES = ["January","February","March","April","May","June",
                     "July","August","September","October","November","December"];
const MAX_ADDED_TERMS = 12;
const ACRONYM_SKIP = new Set(["and","or","of","the","for","to","in","on","a","an"]);
const SMALL_WORDS = new Set(["and","or","of","the","for","to","in","as","on","a","an"]);

const cleanText = (t) => String(t).split(/\s+/).filter(Boolean).join(" ");

function isAcronymOf(short, longForm) {
  const probe = short.replace(/[.\-&]/g, "").toLowerCase();
  if (probe.length < 2 || /\s/.test(short.trim())) return false;
  const words = longForm.split(/\s+/).filter((w) => w && /[a-z0-9]/i.test(w[0]));
  const withGlue = words.map((w) => w[0]).join("").toLowerCase();
  const withoutGlue = words.filter((w) => !ACRONYM_SKIP.has(w.toLowerCase()))
                           .map((w) => w[0]).join("").toLowerCase();
  return probe === withGlue || probe === withoutGlue;
}

function pairForms(a, b) {
  const [short, long] = a.length <= b.length ? [a, b] : [b, a];
  return isAcronymOf(short, long) ? `${short.toUpperCase()} (${long})` : `${a} (${b})`;
}

function lexAcronyms(lexicon) {
  const out = new Set();
  for (const key of lexicon.surfacesMap.keys()) {
    if (!/\s/.test(key) && key.length >= 2 && key.length <= 5 && /^[a-z]+$/.test(key)) out.add(key);
  }
  return out;
}

function titleCaseTerm(term, acronyms) {
  return term.split(/\s+/).map((w, i) => {
    const low = w.toLowerCase();
    if (w === w.toUpperCase() && /[A-Z]/.test(w)) return w.toUpperCase();
    if (acronyms.has(low)) return low.toUpperCase();
    if (low.endsWith("s") && acronyms.has(low.slice(0, -1))) return low.slice(0, -1).toUpperCase() + "s";
    if (i && SMALL_WORDS.has(low)) return low;
    return w.charAt(0).toUpperCase() + w.slice(1);
  }).join(" ");
}

function joinWrapped(text) {
  const out = [];
  for (const raw of text.split("\n")) {
    const stripped = raw.trim();
    if (!stripped) continue;
    const startsItem = /^[-•*]/.test(stripped);
    if (out.length && !startsItem && !/[,|:;]$/.test(out[out.length - 1])) {
      out[out.length - 1] = out[out.length - 1] + " " + stripped;
    } else out.push(stripped);
  }
  return out;
}

function competencyTerms(resume) {
  const out = [], seen = new Set();
  // Join wrapped lines first, or a competency running over the line break is
  // cut in half ("Deal Shaping and" + "Pursuit Management").
  for (let line of joinWrapped(resume.section("skills") || "")) {
    line = line.trim().replace(/^[-•*]+/, "").trim();
    if (!line) continue;
    if (line.includes(":") && line.split(":")[0].split(/\s+/).length <= 4) {
      line = line.slice(line.indexOf(":") + 1);
    }
    for (const part of line.replace(/\|/g, ",").split(",")) {
      const t = part.split(/\s+/).filter(Boolean).join(" ");
      if (t.length > 1 && t.length <= 60 && !seen.has(t.toLowerCase())) {
        seen.add(t.toLowerCase()); out.push(t);
      }
    }
  }
  return out;
}

function roleHeading(role) {
  const parts = [role.title, role.organization].map((p) => (p || "").trim()).filter(Boolean);
  if (parts.length) return parts.join(" | ");
  return cleanText(role.heading.replace(new RegExp(DATE_RANGE_RE.source, "gi"), ""))
    .replace(/^[\s|,\-]+|[\s|,\-]+$/g, "") || "Position";
}

function roleDates(role) {
  if (!role.start) return "";
  const fmt = (ym) => ym ? `${MONTH_NAMES[ym[1] - 1] || ""} ${ym[0]}`.trim() : "";
  const end = role.isCurrent || !role.end ? "Present" : fmt(role.end);
  return `${fmt(role.start)} - ${end}`;
}


/* ------------------------------------------------------------- rewriting ---
   Everything here rewrites a claim the candidate already made. It changes how
   a sentence is worded, never what it asserts: no number, employer, credential
   or skill enters a bullet that was not already in it. A rewrite that cannot
   keep that promise is not applied. */

/* Each rule is [pattern, verbForm, nounForm]. Stripping a duty phrase leaves
   either a verb ("responsible for MANAGING x") or a noun ("responsible for THE
   DELIVERY of x"). The first is conjugated; the second gets a verb put in
   front. Both say what the original said -- and "assisted with x" becomes
   "supported x", never "led x". */
const OPENER_REWRITES = [
  [/^responsible for (?:the )?(?:overall )?/, "", "Owned "],
  [/^responsibilities included /, "", "Owned "],
  [/^duties included /, "", "Owned "],
  [/^accountable for (?:the )?/, "", "Owned "],
  [/^tasked with /, "", "Drove "],
  [/^charged with /, "", "Drove "],
  [/^helped (?:to )?/, "", "Supported "],
  [/^assisted (?:with|in) /, "", "Supported "],
  [/^assisted /, "", "Supported "],
  [/^worked with /, "", "Partnered with "],
  [/^worked on /, "", "Drove "],
  [/^worked to /, "", ""],
  [/^participated in /, "", "Contributed to "],
  [/^involved in /, "", "Contributed to "],
  [/^handled /, "Managed ", "Managed "],
];

const IRREGULAR_PAST = {
  leading: "Led", running: "Ran", building: "Built", driving: "Drove",
  growing: "Grew", holding: "Held", keeping: "Kept", winning: "Won",
  overseeing: "Oversaw", rebuilding: "Rebuilt", setting: "Set",
  writing: "Wrote", making: "Made", meeting: "Met", bringing: "Brought",
  finding: "Found", selling: "Sold", spending: "Spent", taking: "Took",
  teaching: "Taught", beginning: "Began", choosing: "Chose",
  rising: "Rose", sending: "Sent", speaking: "Spoke", standing: "Stood",
};

const IRREGULAR_BARE = {
  lead: "Led", run: "Ran", build: "Built", drive: "Drove", grow: "Grew",
  hold: "Held", keep: "Kept", win: "Won", oversee: "Oversaw",
  rebuild: "Rebuilt", set: "Set", write: "Wrote", make: "Made", meet: "Met",
  bring: "Brought", find: "Found", sell: "Sold", spend: "Spent",
  take: "Took", teach: "Taught", begin: "Began", choose: "Chose",
  rise: "Rose", send: "Sent", speak: "Spoke", stand: "Stood", cut: "Cut",
  put: "Put",
};

/* Verbs the strong-opener list does not carry, but which a stripped duty
   phrase routinely leaves leading the sentence. */
const EXTRA_BARE_VERBS = new Set(("improve manage use utilise utilize ensure "
  + "maintain provide execute identify review plan handle support serve "
  + "deliver run own drive lead build create develop coordinate organise "
  + "organize oversee report track prepare conduct").split(" "));

const PAST_TO_BARE = {};
for (const [bare, past] of Object.entries(IRREGULAR_BARE)) PAST_TO_BARE[past.toLowerCase()] = bare;
const ALREADY_PAST = new Set(
  [...Object.values(IRREGULAR_PAST), ...Object.values(IRREGULAR_BARE)].map((v) => v.toLowerCase()));

const FILLER = [
  [/\bin order to\b/gi, "to"], [/\bwith the goal of\b/gi, "to"],
  [/\bfor the purpose of\b/gi, "to"], [/\bwas able to\b/gi, ""],
  [/\bsuccessfully\b/gi, ""], [/\beffectively\b/gi, ""],
  [/\bconsistently\b/gi, ""], [/\bvery\b/gi, ""],
  [/\butilis|utiliz/gi, "us"], [/\ba variety of\b/gi, ""],
  [/\bvarious\b/gi, ""], [/\bnumerous\b/gi, ""], [/\ba number of\b/gi, ""],
];

const REWRITE_DROPPABLE = new Set(("responsible for the overall responsibilities "
  + "included duties tasked charged with accountable helped to assisted in "
  + "worked on participated involved handled successfully effectively "
  + "consistently very various numerous a number of variety was able order "
  + "goal purpose supported served as utilize utilise utilized utilised "
  + "utilizing utilising").split(" "));

function capitalise(word) { return word.charAt(0).toUpperCase() + word.slice(1); }

function regularPast(root) {
  if (root.endsWith("e")) return capitalise(root + "d");
  if (root.endsWith("y") && root.length > 1 && !"aeiou".includes(root[root.length - 2])) {
    return capitalise(root.slice(0, -1) + "ied");
  }
  if (root.length > 2 && !"aeiouwxy".includes(root[root.length - 1])
      && "aeiou".includes(root[root.length - 2])
      && !"aeiou".includes(root[root.length - 3])) {
    return capitalise(root + root[root.length - 1] + "ed");
  }
  return capitalise(root + "ed");
}

/* Past tense for the verb now leading a bullet, or "" if it is not one. A
   bullet whose duty phrase has been stripped opens on a gerund or a bare
   infinitive; anything else is a noun, and stripping left a fragment. */
function toPast(word) {
  const low = word.toLowerCase().replace(/[.,;:]+$/, "");
  if (!/^[a-z]+$/.test(low)) return "";
  if (low.endsWith("ed") || ALREADY_PAST.has(low)) return "";   // "Ledded"
  if (IRREGULAR_PAST[low]) return IRREGULAR_PAST[low];
  if (IRREGULAR_BARE[low]) return IRREGULAR_BARE[low];
  if (low.endsWith("ing") && low.length >= 6) {
    const root = low.slice(0, -3);
    if (/(at|iz|is|ur|or|id|ut|iv|in|ag|us|il|er|ol|ac|it)$/.test(root)) return capitalise(root + "ed");
    if (root.length > 2 && root[root.length - 1] === root[root.length - 2]
        && !"aeiou".includes(root[root.length - 1])) return capitalise(root.slice(0, -1) + "ed");
    return regularPast(root);
  }
  if (STRONG_VERB_STEMS.has(stem(low)) || EXTRA_BARE_VERBS.has(low)) return regularPast(low);
  return "";
}

function tidyText(t) {
  return t.replace(/\s{2,}/g, " ").trim().replace(/\s+([,.;:])/g, "$1");
}

/* Returns ["", []] when the leading word is not a verb -- stripping the duty
   phrase off "Assisted with the migration of 40 servers" leaves a noun
   phrase, and no conjugation makes that a sentence. */
function leadWithFiniteVerb(text) {
  const first = text.split(" ")[0];
  const past = toPast(first);
  if (!past) return ["", []];
  const changed = [first.toLowerCase().replace(/[.,;:]+$/, "")];
  let rest = text.slice(first.length);
  const pair = rest.match(/^(\s+and\s+)(\w+ing)\b/);
  if (pair) {
    const second = toPast(pair[2]);
    if (second) {
      changed.push(pair[2].toLowerCase());
      rest = pair[1] + second.toLowerCase() + rest.slice(pair[0].length);
    }
  }
  return [past + rest, changed];
}

function carriedWords(text) {
  const out = new Set();
  for (const w of text.match(/[A-Za-z0-9$%][\w$%.,-]*/g) || []) {
    const low = w.toLowerCase().replace(/[.,]+$/, "");
    if (!REWRITE_DROPPABLE.has(low)) out.add(low);
  }
  return out;
}

/* True if the rewrite dropped a word that carried meaning. Numbers and proper
   nouns are the ones that matter: losing one turns a wording change into a
   change of claim. */
function lostContent(before, after, changedVerbs) {
  const skip = new Set(changedVerbs || []);
  const a = carriedWords(after);
  for (const word of carriedWords(before)) {
    if (a.has(word) || skip.has(word)) continue;
    if (/\d/.test(word)) return true;
    let found = false;
    for (const w of a) if (stem(word) === stem(w)) { found = true; break; }
    if (!found) return true;
  }
  return false;
}

/* Rewrite a duty-listing bullet as the accomplishment it describes. Returns
   [text, reason]; reason is "" when nothing could be improved without
   changing the claim. */
function strengthenBullet(bullet) {
  const original = (bullet || "").trim();
  if (!original) return [bullet, ""];
  let text = original;
  const reasons = [];
  let changedVerb = [];

  const lowered = text.toLowerCase();
  for (const [pattern, verbForm, nounForm] of OPENER_REWRITES) {
    const m = lowered.match(pattern);
    if (!m) continue;
    const remainder = tidyText(text.slice(m[0].length));
    if (!remainder) return [original, ""];
    if (verbForm) {
      text = verbForm + remainder.charAt(0).toLowerCase() + remainder.slice(1);
      reasons.push("opened with the action instead of a duty phrase");
      break;
    }
    const [led, verbs] = leadWithFiniteVerb(remainder);
    if (led) { text = led; changedVerb = verbs; }
    else if (nounForm) text = nounForm + remainder.charAt(0).toLowerCase() + remainder.slice(1);
    else return [original, ""];
    reasons.push("opened with the action instead of a duty phrase");
    break;
  }

  text = tidyText(text);
  if (!text) return [original, ""];

  for (const [pattern, replacement] of FILLER) {
    const next = text.replace(pattern, replacement);
    if (next !== text) {
      text = next;
      if (!reasons.includes("cut filler")) reasons.push("cut filler");
    }
  }

  text = tidyText(text);
  if (text && !reasons.some((r) => r.includes("duty phrase"))) {
    const [led, verbs] = leadWithFiniteVerb(text);
    if (led && led !== text) { text = led; changedVerb = verbs; }
  }
  if (text) text = text.charAt(0).toUpperCase() + text.slice(1);

  if (!text || text === original) return [original, ""];
  if (text.split(/\s+/).length < 4) return [original, ""];
  if (lostContent(original, text, changedVerb)) return [original, ""];
  if (openerStrength(text) === "weak") return [original, ""];
  return [text, reasons.join("; ")];
}

/* Say the same thing in the posting's vocabulary. Replacing the resume's
   phrase with the posting's changes which words an index matches, not what
   the bullet claims. */
function alignWording(bullet, pairs) {
  let text = bullet;
  const used = [];
  for (const [postingForm, resumeForm] of pairs) {
    if (resumeForm.length < 4) continue;
    if (resumeForm.endsWith("s") !== postingForm.endsWith("s")) continue;
    const re = new RegExp("\\b" + resumeForm.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "\\b", "i");
    const m = text.match(re);
    if (!m) continue;
    let replacement = postingForm;
    if (m[0].charAt(0) === m[0].charAt(0).toUpperCase()) {
      replacement = postingForm.charAt(0).toUpperCase() + postingForm.slice(1);
    }
    const candidate = text.slice(0, m.index) + replacement + text.slice(m.index + m[0].length);
    if (lostContent(text, candidate, [resumeForm.toLowerCase()])) continue;
    text = candidate;
    used.push(postingForm);
  }
  return [text, used];
}

/* Derivational endings, stripped only when deciding whether the resume
   evidences a posting's term. The main stemmer stays shallow on purpose --
   collapsing "management" into "manage" everywhere would make unrelated terms
   collide during scoring -- but for "does this resume show this at all",
   "leadership" and "leading" are the same thing. */
const DERIVATIONAL = ["ship", "ments", "ment", "nesses", "ness", "ities", "ity",
  "ances", "ance", "ences", "ence", "ations", "ation", "ions", "ion",
  "ives", "ive", "ally", "ly", "ers", "er"];

function deepStem(word) {
  const low = word.toLowerCase();
  let root = stem(PAST_TO_BARE[low] || low);
  for (let i = 0; i < 3; i++) {
    let hit = false;
    for (const ending of DERIVATIONAL) {
      if (root.endsWith(ending) && root.length - ending.length >= 4) {
        root = root.slice(0, -ending.length); hit = true; break;
      }
    }
    if (!hit) break;
  }
  if (root.endsWith("e") && root.length > 4) root = root.slice(0, -1);
  return stem(root);
}

/* The resume's own phrasing for a term whose every content word it uses. A
   posting asking for "executive leadership" against a resume that says
   "leading a team of Executive Directors" is asking for something the resume
   plainly evidences, just not in that word order. Every content word has to
   appear, and near each other. */
function wordsAllPresent(term, index) {
  const words = tokenize(term).filter((w) => !STOPWORDS.has(w));
  if (words.length < 2) return "";
  const stems = words.map(deepStem);
  const deepIndex = index.tokens.map(deepStem);
  const vocab = new Set(deepIndex);
  for (const st of stems) if (!vocab.has(st)) return "";
  const window = stems.length + 6;
  const positions = {};
  for (const st of stems) positions[st] = [];
  deepIndex.forEach((t, i) => { if (positions[t]) positions[t].push(i); });
  for (const anchor of positions[stems[0]]) {
    let near = 0;
    for (const st of stems.slice(1)) {
      if (positions[st].some((p) => Math.abs(p - anchor) <= window)) near++;
    }
    if (near === stems.length - 1) {
      return index.tokens.slice(Math.max(0, anchor - window),
                                Math.min(index.tokens.length, anchor + window)).join(" ");
    }
  }
  return "";
}


/* Rebuilding from parsed structure means content the parser never attached to
   a role or a recognised section simply disappears: a position written without
   dates, a PATENTS or MILITARY SERVICE block, an award list under an unusual
   heading. Silently dropping a line from someone's resume is the worst thing
   this tool could do, so the rebuild is verified against the source and
   anything missing is carried through rather than lost. */
function rescueDroppedContent(source, builtText, resume, placedExtra) {
  let placed = tokenize(builtText).join(" ");
  for (const line of placedExtra || []) placed += " " + tokenize(line).join(" ");
  const placedWords = new Set(placed.split(" "));

  // The cover letter is dropped deliberately; do not rescue it.
  const head = source.split(/\s+/).join(" ").slice(0, 2500).toLowerCase();
  let skipPrefix = 0;
  if (COVER_LETTER_MARKERS.some((m) => head.includes(m))) {
    const lines = source.split("\n");
    for (let i = 0; i < lines.length; i++) {
      if (matchHeading(lines[i])) { skipPrefix = i; break; }
    }
  }

  const contactBits = new Set([resume.contact.email, resume.contact.phone,
    resume.contact.linkedin, resume.contact.github, resume.contact.location,
    resume.contact.nameGuess].filter(Boolean).map((b) => b.toLowerCase()));

  /* A role heading is reprinted in the rebuild's own format, with the location
     split off the employer. Judged only on word coverage it looks like lost
     content, and gets "rescued" -- printing the employer twice. */
  const headingNames = [];
  for (const role of resume.roles) {
    if (role.organization) headingNames.push(role.organization);
    if (role.title) headingNames.push(role.title);
  }
  const isRoleHeading = (line) => {
    const base = stripLocation(line);
    let rest = base;
    for (const name of headingNames) {
      rest = rest.replace(new RegExp(name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi"), " ");
    }
    if (rest === base) return false;      // no role name in it; not a heading
    return rest.replace(/[,|–—-]/g, " ").split(/\s+/).filter(Boolean).length <= 2;
  };

  const missing = [];
  for (const raw of source.split("\n").slice(skipPrefix)) {
    const line = raw.split(/\s+/).filter(Boolean).join(" ");
    if (line.split(" ").filter(Boolean).length < 5) continue;
    if (contactBits.has(line.toLowerCase())) continue;
    if (isRoleHeading(line)) continue;
    const words = tokenize(line).filter((w) => w.length > 2);
    if (!words.length) continue;
    const covered = words.filter((w) => placedWords.has(w)).length / words.length;
    // Below this, the line's substance is genuinely absent rather than merely
    // reformatted.
    if (covered < 0.6) missing.push(line.replace(/^[-•*\s]+/, "").trim());
  }
  return missing;
}

function buildTailored(doc, jd, lexicon, headlineOverride, confirmedSkills) {
  const changes = [], manual = [], blocks = [];
  const [repaired, repairs] = repairLayout(doc.text);
  for (const note of repairs) changes.push({ category: "layout", detail: note.charAt(0).toUpperCase() + note.slice(1) + "." });

  const resume = parseResume(repaired);
  const index = new ResumeIndex(repaired, resume.section("skills"),
                               resume.roles.length ? resume.roles[0].text : "");

  const head = repaired.replace(/\s+/g, " ").slice(0, 2500).toLowerCase();
  if (COVER_LETTER_MARKERS.some((m) => head.includes(m))) {
    changes.push({ category: "structure",
      detail: "Dropped cover-letter prose from the top; send it as a separate document." });
  }
  const banners = repeatedLines(repaired);
  if (banners.size) {
    changes.push({ category: "layout",
      detail: `Removed ${banners.size} repeated page banner(s), which a parser otherwise reads as a job title on every role.` });
  }

  const push = (runs, opts = {}) => blocks.push(Object.assign({ runs, kind: "body", spaceBefore: 0, spaceAfter: 40 }, opts));
  const name = resume.contact.nameGuess || "";
  if (name) push([{ text: cleanText(name), bold: true, size: 30 }], { spaceAfter: 20 });
  const contact = [resume.contact.location, resume.contact.phone, resume.contact.email,
                   resume.contact.linkedin, resume.contact.github].filter(Boolean).join(" | ");
  if (contact) push([{ text: cleanText(contact), size: 19 }], { spaceAfter: 20 });

  const headline = headlineOverride || (jd.title || "").trim();
  if (headline) {
    push([{ text: cleanText(headline), bold: true, size: 22 }], { spaceAfter: 160 });
    changes.push({ category: "structure",
      detail: `Added the headline "${headline}" under the name, which is what title matching reads.` });
  }

  // Terminology: only where the resume already evidences the same skill.
  const existing = new Set(competencyTerms(resume).map((t) => t.toLowerCase()));
  const acronyms = lexAcronyms(lexicon);
  const addable = []; let absent = [];
  for (const req of [...jd.requirements].sort((a, b) => b.weight - a.weight)) {
    const term = req.term;
    if (existing.has(term.toLowerCase()) || index.contains(term)[0]) continue;
    const canon = lexicon.resolve(term);
    let resumeForm = "";
    if (canon) {
      for (const surface of lexicon.surfaces(canon)) {
        if (index.contains(surface)[0]) { resumeForm = surface; break; }
      }
    }
    /* Evidenced, but scattered: adding the posting's phrasing to the
       competencies makes a literal index find what a reader already would.
       Nothing is added to an achievement on this basis. */
    if (!resumeForm && wordsAllPresent(term, index)) resumeForm = term;
    if (resumeForm) { if (addable.length < MAX_ADDED_TERMS) addable.push([term, resumeForm]); }
    else if (req.required || req.knownSkill) absent.push(term);
  }

  const alignedTerms = new Set();
  const rewritten = [];
  const competencies = competencyTerms(resume);
  const addedDisplay = [];
  let paired = 0;
  for (const [postingForm, resumeForm] of addable) {
    const p = titleCaseTerm(postingForm, acronyms), r = titleCaseTerm(resumeForm, acronyms);
    if (p.toLowerCase() !== r.toLowerCase()
        && (isAcronymOf(resumeForm, postingForm) || isAcronymOf(postingForm, resumeForm))) {
      addedDisplay.push(pairForms(p, r)); paired++;
    } else addedDisplay.push(p);
  }
  const confirmed = (confirmedSkills || []).map((t) => (t || "").trim()).filter(Boolean);
  const confirmedAdded = [];
  if (confirmed.length) {
    const already = new Set(competencies.map((c) => c.toLowerCase()));
    for (const term of confirmed) {
      const display = titleCaseTerm(term.toLowerCase(), acronyms);
      if (already.has(display.toLowerCase())) continue;
      already.add(display.toLowerCase());
      confirmedAdded.push(display);
    }
    competencies.push(...confirmedAdded);
    if (confirmedAdded.length) {
      changes.push({ category: "terminology",
        detail: "Added skills you confirmed you hold but had not written down: "
          + confirmedAdded.join(", ") + ". They are listed as skills only -- "
          + "no achievement claims them." });
    }
  }

  competencies.push(...addedDisplay);
  if (addedDisplay.length) {
    changes.push({ category: "terminology",
      detail: `Added the posting's wording for skills the resume already evidences under another name: ${addedDisplay.join(", ")}.` });
  }
  if (paired) {
    changes.push({ category: "terminology",
      detail: `Paired ${paired} acronym(s) with their spelled-out form, so a posting searching for either half finds it.` });
  }
  const weights = new Map(jd.requirements.map((r) => [r.term.toLowerCase(), r.weight]));
  competencies.sort((a, b) => (weights.get(b.toLowerCase().split(" (")[0]) || 0)
                            - (weights.get(a.toLowerCase().split(" (")[0]) || 0));

  const heading = (text) => push([{ text: cleanText(text), bold: true, size: 21, color: "222222" }],
                                 { kind: "heading", spaceBefore: 220, spaceAfter: 90, ruleBelow: true });

  for (const [key, label] of SECTION_PLAN) {
    if (key === "skills") {
      if (competencies.length) { heading(label); push([{ text: cleanText(competencies.join(" | ")), size: 20 }]); }
      continue;
    }
    if (key === "experience") {
      if (!resume.roles.length) continue;
      heading(label);
      for (const role of resume.roles) {
        push([{ text: cleanText(roleHeading(role)), bold: true, size: 20 }], { spaceBefore: 150, spaceAfter: 10 });
        const dates = roleDates(role);
        if (dates) push([{ text: dates, italic: true, size: 19, color: "444444" }], { spaceAfter: 50 });
        for (const b of role.bullets) {
          let written = cleanText(b);
          const [swappedText, swapped] = alignWording(written, addable);
          written = swappedText;
          for (const t of swapped) alignedTerms.add(t);
          const [stronger, why] = strengthenBullet(written);
          if (why) { rewritten.push([written, stronger]); written = stronger; }
          push([{ text: written, size: 20 }], { kind: "bullet" });
        }
        // Content following the bullets inside this role's block, in order.
        for (const line of (role.trailing || [])) {
          if (line.startsWith("- ")) push([{ text: cleanText(line.slice(2)), size: 20 }], { kind: "bullet" });
          else push([{ text: cleanText(line), bold: true, size: 20 }], { spaceBefore: 120, spaceAfter: 20 });
        }
      }
      continue;
    }
    const body = resume.section(key);
    if (!body || !body.trim()) continue;
    heading(label);
    // Rejoin wrapped lines so a summary reads as one paragraph, not as the
    // source file's line breaks frozen into ragged fragments.
    for (const raw of joinWrapped(body)) {
      const line = raw.trim();
      if (!line) continue;
      if (line.startsWith("-")) push([{ text: cleanText(line.replace(/^-+/, "")), size: 20 }], { kind: "bullet" });
      else push([{ text: cleanText(line), size: 20 }]);
    }
  }

  changes.push({ category: "layout",
    detail: "Rebuilt as single-column body text with standard headings, native Word bullets and dates on the title line: no tables, text boxes, columns, headers, footers or images." });

  // A skill the candidate has already confirmed is no longer theirs to add.
  const confirmedLower = new Set(confirmed.map((c) => c.toLowerCase()));
  absent = absent.filter((t) => !confirmedLower.has(t.toLowerCase()));
  if (absent.length) {
    manual.push({ kind: "missing-keyword",
      detail: "The posting asks for these and the resume shows no evidence of them. Add each only where you can point to real work: " + absent.slice(0, 12).join(", ") + "." });
  }
  if (resume.roles.length) {
    const role = resume.roles[0];
  if (rewritten.length) {
    changes.push({ category: "writing",
      detail: `Rewrote ${rewritten.length} duty-listing bullet(s) to open on the `
        + "action instead: the claim is unchanged, the voice is the one a reader credits." });
  }
  if (alignedTerms.size) {
    changes.push({ category: "terminology",
      detail: "Swapped the resume's wording for the posting's inside "
        + `${alignedTerms.size} skill(s) it already evidences: `
        + [...alignedTerms].sort().join(", ") + "." });
  }

    const quantified = role.bullets.filter((b) => METRIC_RE.test(b)).length;
    if (role.bullets.length && quantified === 0) {
      manual.push({ kind: "metrics",
        detail: `Your current role ("${roleHeading(role)}") has no numbers in any of its ${role.bullets.length} bullets. Recruiters read it first. Add scope, savings, percentages or headcount to two or three of them.` });
    }
  }
  const skillsOnly = matchRequirements(jd.requirements, index, lexicon)
    .filter((m) => m.status !== "missing" && m.inSkillsOnly).slice(0, 8)
    .map((m) => m.requirement.term);
  if (skillsOnly.length) {
    manual.push({ kind: "verify",
      detail: "These appear only in your competencies list, never in a bullet: " + skillsOnly.join(", ") + ". Show at least one being used in real work." });
  }

  // Source quality: refuse to rebuild from a file that never parsed.
  const warnings = [];
  const spaced = repaired.split("\n").filter(isLetterSpaced);
  if (spaced.length >= 4) warnings.push(`${spaced.length} lines of the original are letter-spaced graphics rather than text, so their content never reached the parser.`);
  if (!resume.sectionOrder.includes("experience")) warnings.push("No experience section could be found in the original.");
  if (!resume.roles.length) warnings.push("No dated positions could be recovered from the original.");
  if (!resume.contact.email) warnings.push("No email address could be read from the original.");

  const asText = (bs) => bs.map((b) => {
    const content = b.runs.map((r) => r.text).join("");
    if (b.kind === "bullet") return "- " + content;
    if (b.kind === "heading") return "\n" + content;
    return content;
  }).join("\n").trim() + "\n";

  /* A rewritten bullet no longer matches its source line, so the rescue net is
     told it was placed -- otherwise it "recovers" the original wording and the
     resume says it twice. */
  const rescued = rescueDroppedContent(repaired, asText(blocks), resume,
                                       rewritten.map(([was]) => was));
  if (rescued.length) {
    push([{ text: "ADDITIONAL INFORMATION", bold: true, size: 21, color: "222222" }],
         { kind: "heading", spaceBefore: 220, spaceAfter: 90, ruleBelow: true });
    for (const line of rescued) push([{ text: cleanText(line), size: 20 }], { kind: "bullet" });
    changes.push({ category: "structure",
      detail: `Carried ${rescued.length} line(s) the rebuild did not otherwise place `
        + "into an Additional Information section, so nothing from the original is "
        + "lost. Move them where they belong." });
  }

  const text = asText(blocks);

  return { blocks, text, changes, manual, resume, headline, sourceWarnings: warnings,
           name, confirmedAdded, rewrittenBullets: rewritten, absentTerms: absent };
}
