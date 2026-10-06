#!/usr/bin/env python3
"""Build the study dashboard (one self-contained HTML file) from this repo's Markdown.

Usage:  python3 site/build.py [output.html]     (default: site/index.html)

Reads: README.md, MASTER-PLAN.md, SOURCE-MAP.md, WEAK-TOPICS.md, MISTAKES.md,
       QUESTIONS.md, */TOPICS.md, */NOTES/*.md, UNSORTED/*
Nothing is invented: syllabus and plan text come straight from those files.
"""
import datetime
import html
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "site" / "index.html"
YEAR = 2026
MONTHS = {m: i + 1 for i, m in enumerate(
    "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}
REPO_URL = "https://github.com/muhtasimrp74-lab/3rd-Prof-2026"

SUBJECTS = {
    "path": dict(name="Pathology", dir="PATHOLOGY", emoji="🔬"),
    "micro": dict(name="Microbiology", dir="MICROBIOLOGY", emoji="🦠"),
    "cm": dict(name="Community Medicine", dir="COMMUNITY-MEDICINE", emoji="🏘️"),
}
PDFS = [
    ("Pathology (BMDC 2021)", "https://www.bmdc.org.bd/docs/curriculum/2021/11.Pathology.pdf"),
    ("Microbiology (BMDC 2021)", "https://www.bmdc.org.bd/docs/curriculum/2021/12.Microbiology.pdf"),
    ("Community Medicine (BMDC)", "https://www.bmdc.org.bd/docs/4-Community%20Medicine.pdf"),
]


def read(rel):
    p = ROOT / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


# ---------------------------------------------------------------- markdown
def esc(s):
    return html.escape(s, quote=False)


def inline(s):
    s = esc(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
               r'<a href="\2" target="_blank" rel="noopener">\1</a>', s)
    s = re.sub(r"\[([^\]]+)\]\((?!https?://)[^)]*\)", r"\1", s)
    s = re.sub(r'(?<!href=")(?<![>"=])(https?://[^\s<)]+)',
               r'<a href="\1" target="_blank" rel="noopener">\1</a>', s)
    return s


LIST_RE = re.compile(r"^(\s*)(?:([-*])|(\d+)\.)\s+(.*)$")


def md(text, base=2):
    """Small Markdown subset -> HTML (headings, lists, tables, paragraphs, hr)."""
    lines = text.splitlines()
    out, para, stack = [], [], []
    i = 0

    def flush_para(label=False):
        if para:
            cls = ' class="lbl"' if label or (len(para) == 1 and para[0].rstrip().endswith(":")) else ""
            out.append("<p%s>%s</p>" % (cls, "<br>".join(inline(x) for x in para)))
            para.clear()

    def close_lists():
        while stack:
            out.append("</li></ul>" if stack[-1][1] == "ul" else "</li></ol>")
            stack.pop()

    while i < len(lines):
        line = lines[i]
        if not line.strip():
            flush_para(); close_lists(); i += 1; continue
        if line.strip() == "---":
            flush_para(); close_lists(); out.append("<hr>"); i += 1; continue
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            flush_para(); close_lists()
            lvl = min(6, len(m.group(1)) + base - 1)
            out.append("<h%d>%s</h%d>" % (lvl, inline(m.group(2)), lvl))
            i += 1; continue
        if line.lstrip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|[\s:\-|]+\|?\s*$", lines[i + 1]):
            flush_para(); close_lists()
            rows = []
            j = i
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                rows.append([c.strip() for c in lines[j].strip().strip("|").split("|")])
                j += 1
            head, body = rows[0], rows[2:]
            t = "<div class='tbl'><table><thead><tr>%s</tr></thead><tbody>" % "".join(
                "<th>%s</th>" % inline(c) for c in head)
            for r in body:
                t += "<tr>%s</tr>" % "".join("<td>%s</td>" % inline(c) for c in r)
            out.append(t + "</tbody></table></div>")
            i = j; continue
        m = LIST_RE.match(line)
        if m:
            indent = len(m.group(1).replace("\t", "  "))
            tag = "ol" if m.group(3) else "ul"
            if para:
                flush_para(label=True)
            while stack and indent < stack[-1][0]:
                out.append("</li></ul>" if stack[-1][1] == "ul" else "</li></ol>")
                stack.pop()
            if stack and indent == stack[-1][0]:
                out.append("</li>")
            else:
                out.append("<%s>" % tag)
                stack.append((indent, tag))
            out.append("<li>%s" % inline(m.group(4)))
            i += 1; continue
        close_lists()
        para.append(line.strip())
        i += 1
    flush_para(); close_lists()
    return "\n".join(out)


def tables_of(text):
    """Return [(heading, header, rows)] for every Markdown table."""
    res, heading, lines, i = [], "", text.splitlines(), 0
    while i < len(lines):
        l = lines[i]
        m = re.match(r"^#{1,6}\s+(.*)$", l)
        if m:
            heading = m.group(1)
        if l.lstrip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|[\s:\-|]+\|?\s*$", lines[i + 1]):
            rows, j = [], i
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                rows.append([c.strip() for c in lines[j].strip().strip("|").split("|")])
                j += 1
            res.append((heading, rows[0], rows[2:]))
            i = j; continue
        i += 1
    return res


def prose_of(text):
    keep = [l for l in text.splitlines()
            if l.strip() and not l.lstrip().startswith("|") and not l.startswith("#")]
    return md("\n".join(keep))


PLACEHOLDER = {"", "⚪", "⬜"}


def real_rows(rows):
    return [r for r in rows if any(c not in PLACEHOLDER for c in r)]


def table_html(header, rows):
    t = "<div class='tbl'><table><thead><tr>%s</tr></thead><tbody>" % "".join(
        "<th>%s</th>" % esc(c) for c in header)
    for r in rows:
        t += "<tr>%s</tr>" % "".join("<td>%s</td>" % inline(c) for c in r)
    return t + "</tbody></table></div>"


# ------------------------------------------------------------------ dates
DATE_RE = re.compile(r"^(\d{1,2})(?:\s+([A-Z][a-z]{2}))?(?:\s*[–-]\s*(\d{1,2})\s+([A-Z][a-z]{2}))?$")


def span(s):
    m = DATE_RE.match(s.replace("*", "").strip())
    if not m:
        return None
    d1, m1, d2, m2 = m.groups()
    try:
        if d2:
            a = datetime.date(YEAR, MONTHS[m1 or m2], int(d1))
            b = datetime.date(YEAR, MONTHS[m2], int(d2))
        elif m1:
            a = b = datetime.date(YEAR, MONTHS[m1], int(d1))
        else:
            return None
    except (KeyError, ValueError):
        return None
    return a, b


def daterange(a, b):
    d = a
    while d <= b:
        yield d
        d += datetime.timedelta(days=1)


# ------------------------------------------------------------- plan -> data
def parse_exams(readme):
    ex = []
    for name, key in (("Community Medicine", "cm"), ("Pathology", "path"), ("Microbiology", "micro")):
        m = re.search(r"\|\s*%s\s*\|\s*(\d{1,2})\s+([A-Z][a-z]{2})" % name, readme)
        if m:
            ex.append(dict(key=key, name=name, date=datetime.date(YEAR, MONTHS[m.group(2)], int(m.group(1))).isoformat()))
    return ex


def parse_phases(plan):
    phases = []
    for _h, header, rows in tables_of(plan):
        if header and header[0] == "Dates" and len(header) >= 5:
            for r in rows:
                sp = span(r[0])
                if not sp:
                    continue

                def num(x):
                    try:
                        return float(x.replace("*", ""))
                    except ValueError:
                        return None
                phases.append(dict(a=sp[0].isoformat(), b=sp[1].isoformat(),
                                   focus=r[1].replace("*", ""),
                                   hours=dict(path=num(r[2]), micro=num(r[3]), cm=num(r[4])),
                                   exam="written" in r[1].lower()))
            break
    return phases


SUBJ_HDR = re.compile(r"^\*\*(Pathology|Microbiology|Community Medicine)")
SUBJ_KEY = {"Pathology": "path", "Microbiology": "micro", "Community Medicine": "cm"}
BUL = re.compile(r"^\s*-\s+(?P<d>\d{1,2}(?:\s+[A-Z][a-z]{2})?(?:\s*[–-]\s*\d{1,2}\s+[A-Z][a-z]{2})?):\s+(?P<t>.+)$")
UNDATED = re.compile(r"^\s*-\s+(.+)$")


def parse_schedule(plan, phases, exams):
    entries, undated = [], []
    week = subj = section = None
    for line in plan.splitlines():
        if line.startswith("## "):
            t = line[3:]
            section, subj, week = t, None, None
            m = re.match(r"Week \d+ — (.+?)(?: \(.*\))?$", t)
            if m:
                week = span(m.group(1))
            elif t.startswith("3–4 Nov"):
                subj, week = "cm", span("3–4 Nov")
            elif t.startswith("13–14 Nov"):
                subj, week = "micro", span("13–14 Nov")
            continue
        m = SUBJ_HDR.match(line)
        if m:
            subj = SUBJ_KEY[m.group(1)]
            continue
        if section and section.startswith("6–11 Nov") and line.startswith("|"):
            c = [x.strip() for x in line.strip().strip("|").split("|")]
            sp = span(c[0]) if c else None
            if sp and len(c) >= 3:
                entries.append(("path", sp[0], sp[1], c[1]))
                entries.append(("micro", sp[0], sp[1], c[2]))
            continue
        if subj is None or week is None and not (section or "").startswith(("3–4", "13–14")):
            continue
        m = BUL.match(line)
        if m:
            sp = span(m.group("d"))
            txt = m.group("t").replace("**", "")
            if sp and "written" not in txt.lower():
                entries.append((subj, sp[0], sp[1], txt))
            continue
        m = UNDATED.match(line)
        if m and week:
            undated.append((subj, week[0], week[1], m.group(1).replace("**", "")))

    exam_by_date = {e["date"]: e["key"] for e in exams}
    start = min(datetime.date.fromisoformat(p["a"]) for p in phases)
    end = max(datetime.date.fromisoformat(p["b"]) for p in phases)
    days = {}
    for d in daterange(start, end):
        iso = d.isoformat()
        ph = next((p for p in phases if p["a"] <= iso <= p["b"]), None)
        items = {}
        for k in SUBJECTS:
            got = [(e[2] - e[1], e[3]) for e in entries if e[0] == k and e[1] <= d <= e[2]]
            got.sort(key=lambda x: -x[0].days)
            texts = [t for _, t in got]
            if not texts:
                texts = [u[3] for u in undated if u[0] == k and u[1] <= d <= u[2]]
            items[k] = texts
        days[iso] = dict(focus=ph["focus"] if ph else "", hours=ph["hours"] if ph else {},
                         items=items, exam=exam_by_date.get(iso))
    return days


# ---------------------------------------------------------- topics -> data
STATUS_CHARS = "🟢🟡🔴⚪"
ID_RE = re.compile(r"\b(?:PATH-\d[AB]-\d{2}|MICRO-[A-Z]{2}-(?:\d{2}|ADD)|CM-\d{2})\b")
UNTRACKED = {"PATH-1B-04"}


def parse_topics(text):
    title, intro, sections, cur, unit = "", [], [], None, None
    for line in text.splitlines():
        if line.startswith("# ") and not title:
            title = line[2:].strip(); continue
        if line.startswith("# "):
            cur = dict(title=line[2:].strip(), intro=[], units=[]); sections.append(cur); unit = None; continue
        if line.startswith("### ") and cur is not None:
            m = re.match(r"###\s+(\S+)\s+(.*)$", line)
            unit = dict(id=m.group(1), title=m.group(2).strip(), body=[], status="⚪", meta="")
            cur["units"].append(unit); continue
        if line.strip() == "---":
            continue
        if unit is not None:
            if line.startswith("Status:") and not unit["meta"] and unit["status"] == "⚪" and not unit["body"]:
                s = line[len("Status:"):].strip()
                ch = next((c for c in STATUS_CHARS if s.startswith(c)), "⚪")
                unit["status"] = ch
                unit["meta"] = s[len(ch):].strip().lstrip("|").strip()
                continue
            unit["body"].append(line)
        elif cur is not None:
            cur["intro"].append(line)
        else:
            intro.append(line)
    return title, intro, sections


def unit_tracked(uid):
    return uid not in UNTRACKED and not uid.endswith("-ADD")


def subject_page(key, units_out):
    meta = SUBJECTS[key]
    title, intro, sections = parse_topics(read(meta["dir"] + "/TOPICS.md"))
    parts = []
    for sec in sections:
        if not sec["units"]:
            body = md("\n".join(sec["intro"]), base=4)
            if body.strip():
                parts.append("<details class='ref'><summary>%s</summary><div class='ub'>%s</div></details>" % (esc(sec["title"]), body))
            continue
        pre = md("\n".join(sec["intro"]), base=4)
        us = []
        for u in sec["units"]:
            tr = unit_tracked(u["id"])
            units_out[u["id"]] = dict(s=key, t=u["title"], b=u["status"], k=1 if tr else 0)
            chip = ("<button class='chip' data-id='%s' aria-label='Status of %s. Tap to change.'></button>" % (u["id"], esc(u["id"]))
                    if tr else "<span class='chip off' title='Extra / reference'>＋</span>")
            us.append(
                "<details class='unit' id='u-%s' data-id='%s'><summary>%s<span class='uid'>%s</span>"
                "<span class='ut'>%s</span><span class='um'>%s</span></summary><div class='ub'>%s</div></details>"
                % (u["id"], u["id"], chip, esc(u["id"]), esc(u["title"]), esc(u["meta"]), md("\n".join(u["body"]), base=4)))
        parts.append("<section class='grp'><h3 class='gh'>%s</h3>%s<div class='units'>%s</div></section>"
                     % (esc(sec["title"]), ("<div class='gp'>%s</div>" % pre) if pre.strip() else "", "".join(us)))
    about = md("\n".join(intro), base=4)
    exam = ""
    return """
<section class="page" id="p-%(k)s" data-subj="%(k)s" hidden>
  <header class="phead acc-%(k)s">
    <div class="script kick">%(emoji)s BMDC syllabus</div>
    <h1 class="display">%(name)s</h1>
    <div class="examline" data-exam="%(k)s"></div>
    <div class="subprog" data-prog="%(k)s"></div>
  </header>
  <div class="tools">
    <input class="search" type="search" placeholder="Search this syllabus…" aria-label="Search syllabus" data-search="%(k)s">
    <button class="btn" data-expand="%(k)s">Expand all</button>
    <button class="btn" data-collapse="%(k)s">Collapse all</button>
  </div>
  <p class="hint">Tap a status dot to mark your progress: ⚪ → 🔴 → 🟡 → 🟢. Saved on this device.</p>
  <details class="ref"><summary>About this syllabus</summary><div class="ub">%(about)s</div></details>
  %(parts)s
</section>""" % dict(k=key, emoji=meta["emoji"], name=meta["name"], about=about, parts="".join(parts))


# ----------------------------------------------------------- other pages
def link_ids(h, units):
    return ID_RE.sub(lambda m: ("<a class='uidlink' href='#' data-go='%s'>%s</a>" % (m.group(0), m.group(0)))
                     if m.group(0) in units else m.group(0), h)


def plan_page(units):
    body = link_ids(md(read("MASTER-PLAN.md"), base=2), units)
    return """
<section class="page" id="p-plan" hidden>
  <header class="phead acc-plan">
    <div class="script kick">🗓 the roadmap</div>
    <h1 class="display">Master plan</h1>
  </header>
  <article class="prose plan">%s</article>
</section>""" % body


EMPTY = "<div class='empty'><div class='script big'>%s</div><p>%s</p></div>"


def tracker_page(pid, kick, title, file, empty_msg):
    text = read(file)
    prose = prose_of(text)
    blocks = []
    for heading, header, rows in tables_of(text):
        rr = real_rows(rows)
        h = ("<h3 class='gh'>%s</h3>" % esc(heading)) if pid == "questions" else ""
        if rr:
            body = table_html(header, rr)
        elif pid == "questions":
            body = "<div class='empty sm'><p>Nothing tracked yet.</p></div>"
        else:
            body = EMPTY % ("nothing here yet", esc(empty_msg))
        blocks.append("<section class='grp'>%s%s</section>" % (h, body))
    if pid == "questions" and not any("<table" in b for b in blocks):
        blocks.append("<p class='muted'>%s</p>" % esc(empty_msg))
    return """
<section class="page" id="p-%s" hidden>
  <header class="phead acc-%s">
    <div class="script kick">%s</div>
    <h1 class="display">%s</h1>
  </header>
  <div class="prose small">%s</div>
  %s
</section>""" % (pid, pid, kick, title, prose, "".join(blocks))


def tracker_stats():
    st = {}
    wt = tables_of(read("WEAK-TOPICS.md"))
    wrows = real_rows(wt[0][2]) if wt else []
    st["weak"] = dict(n=len(wrows), crit=sum(1 for r in wrows if any("🔥" in c for c in r)),
                      rows=[dict(subject=r[0] if r else "", topic=r[1] if len(r) > 1 else "",
                                 priority=r[3] if len(r) > 3 else "") for r in wrows][:5])
    mt = tables_of(read("MISTAKES.md"))
    st["mistakes"] = dict(n=len(real_rows(mt[0][2])) if mt else 0)
    q = dict(n=0, todo=0, mid=0, strong=0)
    for _h, _hd, rows in tables_of(read("QUESTIONS.md")):
        for r in real_rows(rows):
            q["n"] += 1
            s = r[-1]
            q["strong" if "🟢" in s else "mid" if "🟡" in s else "todo"] += 1
    st["questions"] = q
    return st


def notes_page(units):
    sm = read("SOURCE-MAP.md")
    sm_html = ""
    for heading, header, rows in tables_of(sm):
        rr = real_rows(rows)
        sm_html += "<h3 class='gh'>%s</h3>" % esc(heading or "Source map")
        sm_html += table_html(header, rr) if rr else EMPTY % ("no sources mapped yet", "As you assign a PRIMARY source to each topic, it will list here.")
    notes = []
    for key, meta in SUBJECTS.items():
        d = ROOT / meta["dir"] / "NOTES"
        files = sorted(p for p in d.glob("**/*") if p.is_file() and p.name != ".gitkeep") if d.exists() else []
        for f in files:
            rel = f.relative_to(ROOT).as_posix()
            if f.suffix.lower() == ".md":
                notes.append("<details class='ref'><summary>%s %s <span class='um'>%s</span></summary><div class='ub'>%s</div></details>"
                             % (meta["emoji"], esc(f.stem.replace("-", " ").replace("_", " ")), esc(rel), md(f.read_text(encoding="utf-8"), base=4)))
            else:
                notes.append("<div class='filechip'>%s <a href='%s/blob/main/%s' target='_blank' rel='noopener'>%s</a></div>"
                             % (meta["emoji"], REPO_URL, rel, esc(rel)))
    notes_html = "".join(notes) or EMPTY % ("notes arrive gradually", "Add files to <code>PATHOLOGY/NOTES</code>, <code>MICROBIOLOGY/NOTES</code> or <code>COMMUNITY-MEDICINE/NOTES</code> on GitHub. Markdown notes show here in full after a sync.")
    un = ROOT / "UNSORTED"
    unfiles = sorted(p.name for p in un.glob("*") if p.is_file() and p.name != ".gitkeep") if un.exists() else []
    un_html = "".join("<div class='filechip'>📎 %s</div>" % esc(n) for n in unfiles) or "<p class='muted'>Nothing unsorted.</p>"
    pdfs = "".join("<li><a href='%s' target='_blank' rel='noopener'>%s</a></li>" % (u, esc(n)) for n, u in PDFS)
    return """
<section class="page" id="p-notes" hidden>
  <header class="phead acc-notes">
    <div class="script kick">📚 shelf</div>
    <h1 class="display">Notes &amp; resources</h1>
  </header>
  <h2 class="h2">Notes</h2>%s
  <h2 class="h2">Source map</h2><div class="prose small">%s</div>
  <h2 class="h2">Unsorted files</h2>%s
  <h2 class="h2">Official syllabus PDFs</h2><ul class="plain">%s</ul>
  <h2 class="h2">Repository</h2>
  <p><a class="btn" href="%s" target="_blank" rel="noopener">Open GitHub repo ↗</a></p>
</section>""" % (notes_html, sm_html, un_html, pdfs, REPO_URL)


# ------------------------------------------------------------------ build
def git(*a):
    try:
        return subprocess.check_output(["git", "-C", str(ROOT)] + list(a), text=True).strip()
    except Exception:
        return ""


def main():
    readme, plan = read("README.md"), read("MASTER-PLAN.md")
    exams = parse_exams(readme)
    phases = parse_phases(plan)
    days = parse_schedule(plan, phases, exams)
    units = {}
    pages = [subject_page(k, units) for k in ("path", "micro", "cm")]
    stats = tracker_stats()
    commit = git("rev-parse", "--short", "HEAD")
    when = git("log", "-1", "--format=%cd", "--date=format:%-d %b %Y")
    data = dict(exams=exams, days=days, units=units, stats=stats, commit=commit, synced=when,
                subjects={k: dict(name=v["name"], emoji=v["emoji"]) for k, v in SUBJECTS.items()})
    body = "".join([
        plan_page(units), pages[0], pages[1], pages[2],
        notes_page(units),
        tracker_page("weak", "🎯 revise these first", "Weak topics", "WEAK-TOPICS.md",
                     "No weak topics logged. Rows added to WEAK-TOPICS.md on GitHub show up here after a sync."),
        tracker_page("mistakes", "✏️ learn from them", "Mistakes", "MISTAKES.md",
                     "No mistakes logged. Rows added to MISTAKES.md on GitHub show up here after a sync."),
        tracker_page("questions", "❓ question bank", "Questions", "QUESTIONS.md",
                     "No questions tracked yet. Rows added to QUESTIONS.md on GitHub show up here after a sync."),
    ])
    tpl = (ROOT / "site" / "template.html").read_text(encoding="utf-8")
    js = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    out = tpl.replace("__DATA__", js).replace("__BODY__", body)
    OUT.write_text(out, encoding="utf-8")
    print("wrote", OUT, len(out) // 1024, "KB;", len(units), "units;", len(days), "days; commit", commit)


if __name__ == "__main__":
    main()
