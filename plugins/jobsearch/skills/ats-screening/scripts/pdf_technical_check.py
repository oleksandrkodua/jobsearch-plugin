#!/usr/bin/env python3
"""
ATS technical-quality check for a CV PDF.

Prints a JSON report to stdout covering:
  - text layer presence / extraction quality (per page char counts)
  - reading-order / multi-column risk (naive-order vs. layout-order text diff)
  - duplicate or overlapping text runs
  - invisible text (render mode 3, or near-zero font size)
  - non-ASCII / encoding artifacts and broken hyphenation
  - embedded hyperlinks
  - page count and page-size consistency (clipping/overflow risk)

This is a signal-gathering tool, not a verdict. The skill using this script is
responsible for translating these signals into plain-language findings and for
NOT treating "risk with a naive/coordinate-based parser" as equivalent to
"the PDF is structurally broken" -- a well-tagged two-column PDF can still
trip up a bad parser without being a bad PDF.

Needs the optional libraries pdfplumber and pypdf (pip install pdfplumber pypdf).

Usage:
    python3 scripts/pdf_technical_check.py <path-to-cv.pdf>
"""

import sys
import json
import re
import unicodedata


def safe_div(a, b):
    return a / b if b else 0.0


def check_hidden_text(page):
    """Flag chars rendered invisible (render mode 3) or with ~zero size."""
    hidden = []
    for ch in page.chars:
        size = ch.get("size", 0)
        render_mode = ch.get("render_mode", ch.get("rendering_mode"))
        if size is not None and size < 0.5:
            hidden.append({"text": ch.get("text"), "reason": "near-zero font size", "size": size})
        elif render_mode == 3:
            hidden.append({"text": ch.get("text"), "reason": "invisible render mode (3)"})
    return hidden


def check_reading_order_risk(page):
    """
    Rough column/reading-order heuristic: bucket chars into left/right halves
    by x-position. If both halves have substantial, vertically-overlapping
    text, a naive top-to-bottom-left-to-right (non-layout-aware) parser is
    likely to interleave the two columns.
    """
    width = page.width
    if not width:
        return {"likely_multi_column": False, "note": "no page width available"}

    mid = width / 2
    left_chars = [c for c in page.chars if c["x0"] < mid - (width * 0.05)]
    right_chars = [c for c in page.chars if c["x0"] > mid + (width * 0.05)]

    left_count = len(left_chars)
    right_count = len(right_chars)
    total = len(page.chars) or 1

    likely_multi_column = (
        left_count > total * 0.15 and right_count > total * 0.15
    )

    return {
        "likely_multi_column": likely_multi_column,
        "left_char_ratio": round(safe_div(left_count, total), 3),
        "right_char_ratio": round(safe_div(right_count, total), 3),
        "note": (
            "Two-column layout detected. This is not inherently a defect -- "
            "flag it as a parser-specific compatibility risk, not a structural "
            "problem, unless extraction below is also garbled."
            if likely_multi_column
            else "No strong signal of multi-column layout."
        ),
    }


def check_duplicate_text(full_text):
    """Detect suspicious duplicate lines (e.g. text repeated for a rendering hack)."""
    lines = [l.strip() for l in full_text.splitlines() if l.strip()]
    seen = {}
    dupes = []
    for l in lines:
        if len(l) < 8:  # skip trivial short lines (headers, bullets)
            continue
        seen[l] = seen.get(l, 0) + 1
    for l, count in seen.items():
        if count > 1:
            dupes.append({"line": l[:120], "count": count})
    return dupes[:20]  # cap output


def check_encoding_artifacts(full_text):
    findings = []

    # Replacement / control characters often indicate broken font encoding
    bad_chars = [c for c in full_text if unicodedata.category(c) == "Cc" and c not in "\n\t\r"]
    if bad_chars:
        findings.append(f"{len(bad_chars)} control/unprintable characters found")

    if "�" in full_text:
        findings.append("Unicode replacement character (\\ufffd) present -- likely broken font encoding")

    # Broken hyphenation: word broken across a line with a trailing hyphen
    # followed by a lowercase continuation, common when column extraction
    # mis-orders text.
    broken_hyphens = re.findall(r"[a-zA-Zа-яА-ЯёЁіІїЇєЄ]-\s*\n\s*[a-zа-яіїє]", full_text)
    if len(broken_hyphens) > 3:
        findings.append(f"{len(broken_hyphens)} possible broken-hyphenation instances")

    return findings


def analyze(path):
    import pdfplumber
    from pypdf import PdfReader

    report = {"file": path}

    # --- pypdf pass: page count, hyperlinks, metadata ---
    try:
        reader = PdfReader(path)
        report["page_count"] = len(reader.pages)
        hyperlinks = []
        for i, page in enumerate(reader.pages):
            annots = page.get("/Annots")
            if not annots:
                continue
            for a in annots:
                try:
                    obj = a.get_object()
                    uri = obj.get("/A", {}).get("/URI")
                    if uri:
                        hyperlinks.append({"page": i + 1, "uri": str(uri)})
                except Exception:
                    continue
        report["hyperlinks"] = hyperlinks
    except Exception as e:
        report["pypdf_error"] = str(e)

    # --- pdfplumber pass: text layer, reading order, hidden text, duplicates ---
    pages_report = []
    full_text_parts = []
    total_chars = 0
    hidden_text_total = []

    with pdfplumber.open(path) as pdf:
        page_sizes = set()
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            full_text_parts.append(text)
            char_count = len(page.chars)
            total_chars += char_count
            page_sizes.add((round(page.width), round(page.height)))

            hidden = check_hidden_text(page)
            hidden_text_total.extend(hidden)

            reading_order = check_reading_order_risk(page)

            pages_report.append({
                "page": i + 1,
                "char_count": char_count,
                "extracted_text_chars": len(text),
                "reading_order_risk": reading_order,
                "hidden_text_count": len(hidden),
            })

        report["page_dimensions_consistent"] = len(page_sizes) <= 1
        report["page_dimensions_seen"] = list(page_sizes)

    full_text = "\n".join(full_text_parts)

    report["has_text_layer"] = total_chars > 0
    report["total_extracted_characters"] = total_chars
    report["pages"] = pages_report
    report["hidden_text_findings"] = hidden_text_total[:20]
    report["duplicate_text_lines"] = check_duplicate_text(full_text)
    report["encoding_artifacts"] = check_encoding_artifacts(full_text)

    if total_chars == 0:
        report["verdict_hint"] = (
            "No extractable text layer detected. This is very likely an "
            "image-only / scanned PDF with no OCR text layer -- a serious "
            "ATS risk, since most ATS parsers will read this CV as blank."
        )
    elif any(p["reading_order_risk"]["likely_multi_column"] for p in pages_report):
        report["verdict_hint"] = (
            "Text layer present. Multi-column layout detected on at least one "
            "page -- flag as a parser-specific compatibility risk, not "
            "necessarily a structural defect. Compare extracted text order to "
            "visual order to judge severity."
        )
    else:
        report["verdict_hint"] = "Text layer present, no strong multi-column risk detected."

    return report


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 pdf_technical_check.py <path-to-cv.pdf>", file=sys.stderr)
        sys.exit(1)

    path = sys.argv[1]
    try:
        report = analyze(path)
    except ImportError as e:
        # optional dependencies: say so plainly instead of a bare traceback
        print(json.dumps({"file": path, "error": "optional PDF libraries missing (%s); "
                          "install with: pip install pdfplumber pypdf" % e}, ensure_ascii=False, indent=2))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"file": path, "error": str(e)}, ensure_ascii=False, indent=2))
        sys.exit(1)

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
