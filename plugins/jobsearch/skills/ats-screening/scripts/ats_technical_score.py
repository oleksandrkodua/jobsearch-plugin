#!/usr/bin/env python3
"""
ATS Technical Score for a CV PDF: a deterministic 0-100 estimate of how well
a typical parser can READ the file. It is not a prediction of hiring outcomes
and not a quality score of the candidate (that is Candidate Quality, a
separate judgement made by the skill).

Rubric (100 points, 15 checks, no model calls, same file -> same numbers):
  Parseability 25: machine-text 15, encoding 10
  Contact      15: email 5, phone 5, links 5
  Sections     35: experience 8, education 6, skills 6, summary 5, bonus 10
  Format       15: pages 5, dates 5, bullets 5
  Content      10: quant 5, verbs 5
Bands: >=85 excellent, >=70 good, >=50 needs work, else filtered.
Advisories (never change the score): length, thin-role, long-bullets,
file-name, document-properties, table, columns, header-contact,
graduation-year, reading-order.

Reading model: the scored text is read the way a simple parser reads a page,
in rows across the full page width (baseline tolerance 3 pt, spread limit
6 pt), so a two-column layout interleaves its columns and can hide section
headings. The logical, block-by-block reading is computed too; when it finds
sections the row reading loses, the `reading-order` advisory says which.

Section headings, action verbs, impact units and month names (English and
Ukrainian) are this script's own lists. Weights, thresholds and the layout
method follow the published rubric of the cv.shykov.dev project idea; the
code and word lists here are written separately.

Usage:
    python3 scripts/ats_technical_score.py <cv.pdf> [--json] [--lang en|uk]
    python3 scripts/ats_technical_score.py --selftest [<cv.pdf>]

Needs PyMuPDF (`import fitz`). PDF only.
"""

import argparse
import datetime
import json
import os
import re
import sys
import unicodedata

DISCLAIMER = ("Estimates how readable the file is for a parser, not hiring "
              "outcomes and not candidate quality.")

# ---------------------------------------------------------------- vocabulary

SECTIONS = {
    "experience": [
        "experience", "work experience", "professional experience",
        "employment", "employment history", "work history", "career history",
        "досвід", "досвід роботи", "професійний досвід", "трудова діяльність",
        "місця роботи", "кар'єра", "кар’єра", "історія роботи",
    ],
    "education": [
        "education", "academic background", "education and training",
        "академічна освіта", "освіта", "навчання", "вища освіта",
    ],
    "skills": [
        "skills", "technical skills", "key skills", "core competencies",
        "competencies", "expertise", "навички", "ключові навички",
        "технічні навички", "професійні навички", "компетенції", "вміння",
    ],
    "summary": [
        "summary", "professional summary", "profile", "objective",
        "about me", "about", "резюме", "про себе", "профіль", "підсумок", "мета",
    ],
    "achievements": [
        "achievements", "key achievements", "accomplishments", "highlights",
        "досягнення", "ключові досягнення", "професійні досягнення",
    ],
    "projects": [
        "projects", "selected projects", "personal projects", "side projects",
        "проєкти", "проекти", "ключові проєкти", "особисті проєкти",
    ],
    "certifications": [
        "certifications", "certification", "certificates", "courses",
        "licenses", "certifications and courses", "courses and certificates",
        "сертифікати", "сертифікація", "курси", "ліцензії",
        "курси та сертифікати", "сертифікати та курси",
    ],
}

# English verbs: exact first word. Ukrainian: first word starts with a stem.
VERBS_EN = {
    "led", "managed", "built", "delivered", "improved", "reduced", "increased",
    "launched", "created", "developed", "designed", "implemented", "drove",
    "owned", "established", "mentored", "partnered", "streamlined",
    "optimized", "optimised", "scaled", "coordinated", "analyzed", "analysed",
    "automated", "migrated", "tested", "verified", "validated", "executed",
    "reviewed", "reported", "investigated", "diagnosed", "triaged",
    "documented", "prepared", "performed", "maintained", "supported",
    "collaborated", "conducted", "defined", "introduced", "reconciled",
    "monitored", "identified", "ensured", "organized", "organised",
    "planned", "prioritized", "prioritised", "resolved", "trained",
    "cut", "moved", "set", "wrote", "ran", "reproduced", "checked",
}
VERB_STEMS_UK = (
    "керува", "очолю", "запровад", "впровад", "розроб", "створ", "запуст",
    "покращ", "скороти", "збільш", "оптиміз", "автоматиз", "мігру",
    "проаналіз", "побуду", "координу", "налагод", "забезпеч", "провів",
    "провел", "реаліз", "організ", "тестув", "перевір", "валід", "викон",
    "документ", "підготу", "супровод", "підтрим", "ментор", "виріш",
    "усуну", "дослід", "діагност", "відтвор", "веду", "вів", "вела",
)

UNITS_EN = {"x", "×", "k", "m", "bn", "users", "people", "engineers", "hours",
            "days", "weeks", "months", "minutes", "bugs", "defects", "tickets",
            "releases", "devices", "tests", "cases", "requests", "customers",
            "clients", "teams"}
UNIT_STEMS_UK = ("користувач", "люд", "інженер", "годин", "хвилин", "дні",
                 "днів", "тижн", "місяц", "раз", "млн", "тис", "грн",
                 "дефект", "баг", "реліз", "пристро", "тест", "клієнт",
                 "команд", "запит")

MONTHS = (
    "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "sept",
    "oct", "nov", "dec", "january", "february", "march", "april", "june",
    "july", "august", "september", "october", "november", "december",
    "січ", "лют", "бер", "квіт", "трав", "черв", "лип", "серп", "вер",
    "жовт", "лист", "груд",
)
BULLET_CHARS = set("•·●○◦▪■▫–—-*▸►➢✓→")
CONTACT_SEPARATORS = " \t\r\n|,;·"
TRIM_CHARS = "()[]{}<>\"'.,;:"
PROFILE_TLDS = {"dev", "io", "me", "com", "net", "org"}
PRESENT_WORDS = ("present", "current", "now", "тепер", "теперішн", "наш час")

SCRATCH_NAME = re.compile(
    r"(\bfinal\b|\bdraft\b|\bcopy\b|\buntitled\b|\blatest\b|\bnew\b|\breal\b|"
    r"\bv\d+\b|\bversion\s*\d+\b|\(\d+\)|\d{6,}|^microsoft word)", re.I)


def fold(s):
    s = unicodedata.normalize("NFKD", s.lower().replace("’", "'"))
    return "".join(c for c in s if not unicodedata.combining(c))


FOLDED_SECTIONS = {k: {fold(v) for v in vs} for k, vs in SECTIONS.items()}
ALL_HEADINGS = set().union(*FOLDED_SECTIONS.values())


def words(s):
    return re.findall(r"[^\W\d_]{2,}", s, re.UNICODE)


# ------------------------------------------------------------- date / bullets

_MONTH_RE = "|".join(sorted((fold(m) for m in MONTHS), key=len, reverse=True))
DATE_RES = [
    re.compile(r"\b(0?[1-9]|1[0-2])\s*[/.\-]\s*(19|20)\d{2}\b"),
    re.compile(r"\b(%s)[a-zа-яіїєґ]*\.?\s+(19|20)\d{2}\b" % _MONTH_RE),
    re.compile(r"\b(19|20)\d{2}\s*[-–—]\s*((19|20)\d{2}|[a-zа-яіїєґ]+)\b"),
]


def has_date(text):
    t = fold(text)
    for rx in DATE_RES:
        for m in rx.finditer(t):
            if rx is DATE_RES[2]:
                tail = m.group(2)
                if not re.match(r"(19|20)\d{2}$", tail) and not tail.startswith(
                        tuple(fold(p) for p in PRESENT_WORDS)):
                    continue
            return True
    return False


YEAR_END_RE = re.compile(r"\b(19|20)\d{2}\s*$")


def is_entry_header(line):
    """A role or project heading: carries a date range, or is a short
    capitalised non-sentence line that ends with a single year
    ("Ad-Tracking System 2015")."""
    if is_bullet(line):
        return False
    t = line.strip()
    if has_date(t):
        return True
    return (len(t) <= 80 and t[:1].isupper() and not t.endswith((".", ";", ","))
            and not starts_with_verb(t) and bool(YEAR_END_RE.search(t)))


def strip_bullet(line):
    t = line.lstrip()
    if len(t) > 1 and t[0] in BULLET_CHARS and t[1].isspace():
        return t[1:].strip()
    return line.strip()


def is_bullet(line):
    return strip_bullet(line) != line.strip()


# ------------------------------------------------------------------- contact

def _trim(tok):
    return tok.strip(TRIM_CHARS)


def tokens(text):
    out, cur = [], []
    for ch in text:
        if ch in CONTACT_SEPARATORS:
            if cur:
                out.append("".join(cur))
                cur = []
        else:
            cur.append(ch)
    if cur:
        out.append("".join(cur))
    return [_trim(t) for t in out if _trim(t)]


EMAIL_RE = re.compile(r"^[^@\s]+@[a-z0-9]([a-z0-9-]*[a-z0-9])?"
                      r"(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*\.[a-z]{2,}$")


def has_email(text):
    return any(EMAIL_RE.match(t.lower()) for t in tokens(text) if t.count("@") == 1)


def has_phone(text):
    for m in re.finditer(r"\+?\d[\d\s().\-]{7,}\d", text):
        run = m.group(0)
        digits = sum(c.isdigit() for c in run)
        if digits < 9 or digits > 15:
            continue
        groups = [g for g in re.split(r"[^0-9]+", run) if g]
        if any(len(g) == 1 for g in groups[2:]):
            continue
        if all(len(g) == 4 and 1900 <= int(g) <= 2099 for g in groups):
            continue
        return True
    return False


def profile_urls(text):
    found = []
    for line in text.splitlines():
        line_has_contact = has_email(line) or has_phone(line)
        for tok in tokens(line):
            if "@" in tok:
                continue
            low = tok.lower()
            bare = re.sub(r"^https?://", "", low)
            bare = re.sub(r"^www\.", "", bare)
            explicit = bare.startswith(("linkedin.com/", "github.com/"))
            has_proto = low.startswith(("http://", "https://", "www."))
            host, _, path = bare.partition("/")
            tld = host.rsplit(".", 1)[-1] if "." in host else ""
            if explicit:
                found.append(tok)
            elif tld in PROFILE_TLDS and re.match(r"^[a-z0-9.-]+$", host):
                if has_proto or path:
                    found.append(tok)
                elif line_has_contact and "." in host:
                    found.append(tok)
    return found


# -------------------------------------------------------------------- loading

def load(path):
    import fitz
    doc = fitz.open(path)
    pages, all_lines, row_lines = [], [], []
    for pno, page in enumerate(doc):
        d = page.get_text("dict")
        pieces, lines = [], []
        pending = ""
        for b in d["blocks"]:
            if b.get("type") != 0:
                continue
            for ln in b["lines"]:
                spans = [s for s in ln["spans"] if s["text"].strip()]
                if not spans:
                    continue
                for s in spans:
                    x0, y0, x1, y1 = s["bbox"]
                    pieces.append((x0, y0, x1 - x0, s["text"], y1))
                text = "".join(s["text"] for s in ln["spans"]).strip()
                if text in {c for c in BULLET_CHARS}:
                    pending = text + " "
                    continue
                lines.append(pending + text)
                pending = ""
        links = [l["uri"] for l in page.get_links() if l.get("uri")]
        pages.append({"w": page.rect.width, "h": page.rect.height,
                      "pieces": pieces, "links": links})
        all_lines.extend(lines)
        row_lines.extend(page_row_lines(d))
    meta = dict(doc.metadata or {})
    return meta, pages, row_lines, all_lines


def page_row_lines(d):
    """Lines in row order across the full page width (baseline grouping)."""
    items = []
    for b in d["blocks"]:
        if b.get("type") != 0:
            continue
        for ln in b["lines"]:
            for s in ln["spans"]:
                if s["text"].strip():
                    items.append((s["origin"][1], s["bbox"][0], s["bbox"][2], s["text"]))
    items.sort(key=lambda t: (t[0], t[1]))
    rows = []
    for it in items:
        if rows and abs(it[0] - rows[-1][-1][0]) <= 3 and abs(it[0] - rows[-1][0][0]) <= 6:
            rows[-1].append(it)
        else:
            rows.append([it])
    out = []
    for r in rows:
        r.sort(key=lambda t: t[1])
        text, prev = "", None
        for _, x0, x1, t in r:
            if prev is not None and not text.endswith(" ") and not t.startswith(" ") and x0 - prev > 1:
                text += " "
            text += t
            prev = x1
        text = " ".join(text.split())
        if text:
            out.append(text)
    return out


# ------------------------------------------------------------------ sections

def norm_head(s):
    return fold(s).strip(" :.-–—•·*#|\t")


def find_headings(lines):
    """Return {idx: category} for lines that look like a section heading."""
    heads = {}
    for i, raw in enumerate(lines):
        t = raw.strip()
        if not t or len(t) > 45:
            continue
        head, inline = t, False
        if ":" in t:
            h, rest = t.split(":", 1)
            if rest.strip():
                head, inline = h, True
        n = norm_head(head)
        for cat, kws in FOLDED_SECTIONS.items():
            if n in kws:
                heads[i] = (cat, inline)
                break
    return heads


def sections_with_content(lines):
    heads = find_headings(lines)
    order = sorted(heads)
    found = {}
    for pos, i in enumerate(order):
        cat, inline = heads[i]
        end = order[pos + 1] if pos + 1 < len(order) else len(lines)
        body = lines[i + 1:end]
        ok = inline or len(words(" ".join(body))) >= 2
        if ok:
            found[cat] = (i, end)
    return found


# -------------------------------------------------------------------- layout

def rows_from_pieces(pieces):
    rows = []
    for p in sorted(pieces, key=lambda p: (p[1], p[0])):
        if rows and abs(p[1] - rows[-1]["y"]) <= 3:
            rows[-1]["items"].append(p)
        else:
            rows.append({"y": p[1], "items": [p]})
    for r in rows:
        r["items"].sort(key=lambda p: p[0])
    return rows


def segments_of(row, page_w):
    segs, cur = [], None
    for x0, y0, w, text, y1 in row["items"]:
        if cur and x0 - cur["x1"] < 0.04 * page_w:
            cur["text"] += (" " if x0 - cur["x1"] > 1 else "") + text
            cur["x1"] = x0 + w
        else:
            if cur:
                segs.append(cur)
            cur = {"x": x0, "x1": x0 + w, "text": text}
    if cur:
        segs.append(cur)
    for s in segs:
        s["text"] = " ".join(s["text"].split())
    return [s for s in segs if s["text"]]


def page_layout_flags(page):
    W = page["w"]
    clusters = []
    for ri, row in enumerate(rows_from_pieces(page["pieces"])):
        for seg in segments_of(row, W):
            if len(seg["text"]) <= 24 and has_date(seg["text"]):
                continue
            for c in clusters:
                if abs(seg["x"] - c["x"]) <= 6:
                    c["rows"].add(ri)
                    c["top"] = min(c["top"], row["y"])
                    c["bottom"] = max(c["bottom"], row["y"])
                    break
            else:
                clusters.append({"x": seg["x"], "rows": {ri},
                                 "top": row["y"], "bottom": row["y"]})
    big = sorted((c for c in clusters if len(c["rows"]) >= 6), key=lambda c: c["x"])
    kept = set()
    for i in range(len(big)):
        for j in range(i + 1, len(big)):
            a, b = big[i], big[j]
            overlap = min(a["bottom"], b["bottom"]) - max(a["top"], b["top"])
            if abs(a["x"] - b["x"]) >= 0.2 * W and overlap >= 80:
                kept.update((i, j))
    return len(kept) >= 2, len(kept) >= 3


def header_contact(pages):
    if len(pages) < 2:
        return False
    per_page = []
    for pg in pages:
        rows = []
        for r in rows_from_pieces(pg["pieces"]):
            txt = " ".join(" ".join(p[3] for p in r["items"]).lower().split())
            rows.append((r["y"], txt))
        per_page.append(rows)
    running = set()
    for y, txt in per_page[0]:
        if all(any(t == txt and abs(y2 - y) <= 3 for y2, t in rows)
               for rows in per_page[1:]):
            running.add(txt)
    band_rows, body = [], []
    for pg, rows in zip(pages, per_page):
        for y, txt in rows:
            in_band = y < 0.07 * pg["h"] or y > 0.93 * pg["h"]
            if txt in running and in_band:
                band_rows.append(txt)
            elif txt not in running:
                body.append(txt)
    band = " ".join(band_rows)
    body_text = " ".join(body)
    b_mail, b_phone = has_email(band), has_phone(band)
    if not (b_mail or b_phone):
        return False
    if b_mail and has_email(body_text):
        return False
    if b_phone and has_phone(body_text):
        return False
    return True


# ------------------------------------------------------------------- checks

def check(cid, group, mx, pts, status, detail):
    return {"id": cid, "group": group, "max": mx, "points": pts,
            "status": status, "detail": detail}


SEC_IDS = {"experience": "sec-exp", "education": "sec-edu",
           "skills": "sec-skills", "summary": "sec-summary"}


def score_pdf(path, lang="en"):
    meta, pages, lines, block_lines = load(path)
    text = "\n".join(lines)
    n_chars = len(text.replace("\n", "").strip())
    checks = []

    # Parseability
    if n_chars >= 300:
        checks.append(check("machine-text", "Parseability", 15, 15, "pass",
                            "%d characters of extractable text" % n_chars))
    elif n_chars >= 50:
        checks.append(check("machine-text", "Parseability", 15, 7, "warn",
                            "only %d characters extracted" % n_chars))
    else:
        checks.append(check("machine-text", "Parseability", 15, 0, "fail",
                            "no usable text layer (%d characters)" % n_chars))
    bad_enc = re.search("[ﬀ-ﬆ]", text) or "(cid:" in text
    checks.append(check("encoding", "Parseability", 10, 0 if bad_enc else 10,
                        "fail" if bad_enc else "pass",
                        "ligature characters or (cid:) codes found" if bad_enc
                        else "no ligature or CID artefacts"))

    # Contact
    checks.append(check("email", "Contact", 5, 5 if has_email(text) else 0,
                        "pass" if has_email(text) else "fail",
                        "email found" if has_email(text) else "no email address"))
    checks.append(check("phone", "Contact", 5, 5 if has_phone(text) else 0,
                        "pass" if has_phone(text) else "warn",
                        "phone found" if has_phone(text) else "no phone number"))
    link_text = profile_urls(text)
    link_targets = []
    for pg in pages:
        link_targets.extend(pg["links"])
    if link_text:
        checks.append(check("links", "Contact", 5, 5, "pass",
                            "visible profile link: %s" % link_text[0]))
    elif profile_urls("\n".join(link_targets)) or any(
            "linkedin.com" in u or "github.com" in u for u in link_targets):
        checks.append(check("links", "Contact", 5, 0, "warn",
                            "profile link exists only as a hidden hyperlink "
                            "target; the URL is not visible in the text"))
    else:
        checks.append(check("links", "Contact", 5, 0, "warn",
                            "no profile link (LinkedIn, GitHub, site)"))

    # Sections
    found = sections_with_content(lines)
    for cat, mx, pts_label, essential in (
            ("experience", 8, "experience", True),
            ("education", 6, "education", True),
            ("skills", 6, "skills", True),
            ("summary", 5, "summary", False)):
        ok = cat in found
        checks.append(check(SEC_IDS[cat], "Sections", mx, mx if ok else 0,
                            "pass" if ok else ("fail" if essential else "warn"),
                            "%s section with content" % pts_label if ok
                            else "no %s section with content" % pts_label))
    bonus_pts = {"achievements": 4, "projects": 3, "certifications": 3}
    got = sum(v for k, v in bonus_pts.items() if k in found)
    names = [k for k in bonus_pts if k in found]
    checks.append(check("sec-bonus", "Sections", 10, got,
                        "pass" if got >= 7 else "warn",
                        "found: %s" % (", ".join(names) or "none")))

    # Format
    n_pages = len(pages)
    if n_pages <= 2:
        p_pts, p_st = 5, "pass"
    elif n_pages == 3:
        p_pts, p_st = 3, "warn"
    else:
        p_pts, p_st = 0, "fail"
    checks.append(check("pages", "Format", 5, p_pts, p_st, "%d page(s)" % n_pages))
    dated = has_date(text)
    checks.append(check("dates", "Format", 5, 5 if dated else 0,
                        "pass" if dated else "warn",
                        "dates found" if dated else "no recognisable dates"))
    n_bul = sum(1 for l in lines if is_bullet(l))
    b_pts, b_st = (5, "pass") if n_bul >= 3 else ((3, "warn") if n_bul else (0, "warn"))
    checks.append(check("bullets", "Format", 5, b_pts, b_st,
                        "%d bullet line(s)" % n_bul))

    # Content
    hits = quant_hits(text)
    q_pts, q_st = (5, "pass") if hits >= 3 else ((3, "warn") if hits else (0, "fail"))
    checks.append(check("quant", "Content", 5, q_pts, q_st,
                        "%d quantified-impact token(s)" % hits))
    n_verbs = sum(1 for l in lines if starts_with_verb(strip_bullet(l)))
    v_pts, v_st = (5, "pass") if n_verbs >= 3 else ((3, "warn") if n_verbs else (0, "warn"))
    checks.append(check("verbs", "Content", 5, v_pts, v_st,
                        "%d line(s) start with an action verb" % n_verbs))

    total = sum(c["points"] for c in checks)
    band = ("excellent" if total >= 85 else "good" if total >= 70
            else "needs work" if total >= 50 else "filtered")
    lost = [c for c in checks if c["status"] != "pass"]
    lost.sort(key=lambda c: (-(c["max"] - c["points"]),
                             0 if c["status"] == "fail" else 1))
    top = [{"id": c["id"], "lost": c["max"] - c["points"], "detail": c["detail"]}
           for c in lost[:3]]

    groups = {}
    for c in checks:
        g = groups.setdefault(c["group"], {"points": 0, "max": 0})
        g["points"] += c["points"]
        g["max"] += c["max"]

    return {
        "file": os.path.basename(path), "pages": n_pages,
        "score": total, "max": 100, "band": band, "groups": groups,
        "checks": checks, "top_fixes": top,
        "advisories": advisories(path, meta, pages, lines, found, text, lang,
                                 block_lines),
        "disclaimer": DISCLAIMER,
    }


def quant_hits(text):
    toks = tokens(text)
    hits = 0

    def numeric(t):
        return t.replace(".", "", 1).isdigit()

    for i, t in enumerate(toks):
        nxt = toks[i + 1].lower() if i + 1 < len(toks) else ""
        low = t.lower()
        if t.endswith("%") and any(c.isdigit() for c in t):
            hits += 1
        elif t == "%" and i and numeric(toks[i - 1]):
            hits += 1
        elif t[:1] in "$€£₴" and len(t) > 1 and t[1].isdigit():
            hits += 1
        elif t in "$€£₴" and nxt and any(c.isdigit() for c in nxt):
            hits += 1
        elif numeric(t) and nxt and (nxt in UNITS_EN or nxt.startswith(UNIT_STEMS_UK)):
            hits += 1
        elif re.match(r"^\d+(\.\d+)?(k|m|bn|x|×)$", low):
            hits += 1
    return hits


def starts_with_verb(line):
    parts = line.split()
    if not parts:
        return False
    w = fold(parts[0]).strip(TRIM_CHARS + ":")
    return w in VERBS_EN or w.startswith(tuple(fold(s) for s in VERB_STEMS_UK))


# ---------------------------------------------------------------- advisories

def advisories(path, meta, pages, lines, found, text, lang, block_lines=None):
    out = []
    if block_lines:
        lost = [c for c in sections_with_content(block_lines) if c not in found]
        if lost:
            out.append({"id": "reading-order",
                        "detail": "section(s) %s are found in logical reading order but lost "
                                  "in row-order reading (columns interleave); a simple parser "
                                  "may miss them" % ", ".join(sorted(lost))})
    n_words = len(text.split())
    if n_words > 1000:
        out.append({"id": "length", "detail": "%d words; long CVs tend to be skimmed" % n_words})

    bullets = bullet_groups(lines)
    long_b = sum(1 for b in bullets if len(b.split()) > 40)
    if long_b:
        out.append({"id": "long-bullets",
                    "detail": "%d bullet(s) over 40 words (heuristic: wrapped lines joined)" % long_b})

    if "experience" in found:
        s, e = found["experience"]
        entries, cur = [], None
        for l in lines[s + 1:e]:
            if is_entry_header(l):
                cur = {"bullets": 0}
                entries.append(cur)
            elif is_bullet(l) and cur is not None:
                cur["bullets"] += 1
        thin = sum(1 for en in entries if en["bullets"] == 1)
        if len(entries) >= 2 and thin:
            out.append({"id": "thin-role",
                        "detail": "%d role/project entry(ies) with exactly one bullet (heuristic)" % thin})

    stem = os.path.splitext(os.path.basename(path))[0]
    if SCRATCH_NAME.search(stem.replace("_", " ").replace("-", " ")):
        out.append({"id": "file-name", "detail": "file name looks like a scratch name: %s" % stem})

    name_line = lines[0] if lines else ""
    author, title = meta.get("author") or "", meta.get("title") or ""
    name_words = {fold(w) for w in words(name_line) if len(w) > 1}
    bad_author = bool(author.strip()) and not (
        name_words & {fold(w) for w in words(author) if len(w) > 1})
    bad_title = bool(title.strip()) and bool(SCRATCH_NAME.search(title))
    if bad_author or bad_title:
        out.append({"id": "document-properties",
                    "detail": "PDF metadata author=%r title=%r does not fit the CV" % (author, title)})

    flags = [page_layout_flags(pg) for pg in pages if pg["pieces"]]
    cols = any(f[0] for f in flags)
    table = any(f[1] for f in flags)
    if table:
        out.append({"id": "table", "detail": "layout looks like a table; some parsers read it poorly"})
    elif cols:
        out.append({"id": "columns", "detail": "multi-column layout; single column is the safest for parsers"})
    if header_contact(pages):
        out.append({"id": "header-contact",
                    "detail": "contact details only in the page header/footer band"})

    if lang == "en" and "education" in found:
        s, e = found["education"]
        years = [int(y) for y in re.findall(r"\b(19\d{2}|20\d{2})\b", " ".join(lines[s:e]))]
        if years and datetime.date.today().year - max(years) > 15:
            out.append({"id": "graduation-year",
                        "detail": "latest education year %d is over 15 years old; omitting it is a choice, not a rule" % max(years)})
    return out


def bullet_groups(lines):
    heads = find_headings(lines)
    groups, cur, cont = [], None, 0
    for i, l in enumerate(lines):
        if is_bullet(l):
            if cur is not None:
                groups.append(cur)
            cur, cont = strip_bullet(l), 0
        elif cur is not None and i not in heads and not is_entry_header(l) and cont < 4 and l.strip():
            cur += " " + l.strip()
            cont += 1
        else:
            if cur is not None:
                groups.append(cur)
            cur = None
    if cur is not None:
        groups.append(cur)
    return groups


# --------------------------------------------------------------------- output

def render(rep):
    out = ["ATS Technical Score: %d/100 (%s)" % (rep["score"], rep["band"]),
           "File: %s, %d page(s)" % (rep["file"], rep["pages"]), ""]
    out.append("%-14s %-5s %-4s %s" % ("check", "pts", "max", "status / detail"))
    for c in rep["checks"]:
        out.append("%-14s %-5d %-4d %s: %s" % (c["id"], c["points"], c["max"],
                                              c["status"], c["detail"]))
    out.append("")
    out.append("Groups: " + ", ".join("%s %d/%d" % (g, v["points"], v["max"])
                                      for g, v in rep["groups"].items()))
    out.append("Top fixes: " + ("; ".join("%s (-%d)" % (t["id"], t["lost"])
                                          for t in rep["top_fixes"]) or "none"))
    out.append("Advisories (unscored): " + ("; ".join(
        "%s: %s" % (a["id"], a["detail"]) for a in rep["advisories"]) or "none"))
    out.append("")
    out.append(rep["disclaimer"])
    return "\n".join(out)


SELFTEST_CASES = [
    # (function, argument, expected)
    (lambda t: has_phone(t), "+10000000000", True),
    (lambda t: has_phone(t), "+1 000 000 00 00", True),
    (lambda t: has_phone(t), "96.5 99.5 99.9", False),
    (lambda t: has_phone(t), "2014 2022 2020", False),
    (lambda t: has_date(t), "04/2014 - Present", True),
    (lambda t: has_date(t), "March 2020", True),
    (lambda t: has_date(t), "2015 \u2013 2022", True),
    (lambda t: has_date(t), "\u043b\u0438\u043f 2021", True),
    (lambda t: has_date(t), "96.5 99.5", False),
    (lambda t: has_date(t), "no dates here", False),
    (lambda t: quant_hits(t), "cut by 30% saved $5k 10 users 3x 40 %", 5),
    (lambda t: quant_hits(t), "3 days", 1),
    (lambda t: quant_hits(t), "roughly ten days to weekly", 0),
    (lambda t: is_entry_header(t), "Ad-Tracking System 2015", True),
    (lambda t: is_entry_header(t), "Example Platform - Real Estate / Booking 2014", True),
    (lambda t: is_entry_header(t), "Senior Engineer | Example Corp 04/2014 - Present", True),
    (lambda t: is_entry_header(t), "Led the release in 2022", False),
    (lambda t: is_entry_header(t), "Tested search in 2019.", False),
    (lambda t: is_entry_header(t), "\u2022 Built tests 2015", False),
    (lambda t: is_entry_header(t), "in the 2020", False),
]


def run_selftest():
    bad = 0
    for fn, arg, want in SELFTEST_CASES:
        got = fn(arg)
        if got != want:
            bad += 1
            print("FAIL  %r -> %r, expected %r" % (arg, got, want))
    print("selftest: %d case(s), %d failed" % (len(SELFTEST_CASES), bad))
    return bad == 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("pdf", nargs="?")
    ap.add_argument("--selftest", action="store_true",
                    help="run the built-in checks of the helper functions")
    ap.add_argument("--json", action="store_true", help="print JSON only")
    ap.add_argument("--lang", choices=("en", "uk"), default="en",
                    help="CV language (affects only the graduation-year advisory)")
    a = ap.parse_args()
    if a.selftest:
        if not run_selftest():
            sys.exit(1)
        if not a.pdf:
            return
    if not a.pdf:
        ap.error("a PDF file is required (or use --selftest)")
    if not os.path.isfile(a.pdf):
        sys.exit("file not found: %s" % a.pdf)
    try:
        rep = score_pdf(a.pdf, a.lang)
    except ImportError:
        sys.exit("PyMuPDF is required: pip install pymupdf")
    print(json.dumps(rep, ensure_ascii=False, indent=2) if a.json else render(rep))


if __name__ == "__main__":
    main()
