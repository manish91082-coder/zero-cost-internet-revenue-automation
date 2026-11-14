#!/usr/bin/env python3
"""Extract a source-faithful occurrence ledger from embedded plan/destinations-hi.md.

Usage:
  python scripts/extract_destination_occurrences.py SOURCE.md OUTPUT.json

This performs literal table-row extraction only. It does not deduplicate, infer
shared-list/category links, validate URLs, or judge commercial eligibility.
"""
from pathlib import Path
import hashlib, json, re, sys

START = "# भाग 7: `plan/destinations-hi.md`"
END = "<!-- SOURCE END: plan/destinations-hi.md -->"
CATEGORY = re.compile(r"^#{2,4}\\s+(\\d+)\\.\\s+(.+?)\\s+[—-]\\s+(\\d+)\\s+(?:destinations|अपनी destinations)\\s*$", re.I)
SHARED = re.compile(r"^#{2,4}\\s+साझा सूची\\s+([A-Z])\\s+[—-]\\s+(.+?)\\s+[—-]\\s+(\\d+)\\s*$", re.I)
ANY_HEADING = re.compile(r"^#{2,4} ")

def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: extract_destination_occurrences.py SOURCE.md OUTPUT.json")
    source = Path(sys.argv[1]).read_text(encoding="utf-8")
    a, b = source.find(START), source.find(END)
    if a < 0 or b < a:
        raise SystemExit("embedded destinations section markers not found")
    section = source[a:b]
    lines = section.splitlines()
    headings = []
    for i, line in enumerate(lines):
        m = CATEGORY.match(line)
        if m:
            headings.append((i, "category", m.group(1), m.group(2), int(m.group(3))))
            continue
        m = SHARED.match(line)
        if m:
            headings.append((i, "shared", m.group(1), m.group(2), int(m.group(3))))
    headings.sort()
    all_headings = [i for i, line in enumerate(lines) if ANY_HEADING.match(line)]
    records, audit = [], []
    for i, (start, kind, ident, name, declared) in enumerate(headings):
        stop = next((x for x in all_headings if x > start), len(lines))
        extracted = []
        for row_i in range(start + 1, stop):
            line = lines[row_i].strip()
            if not line.startswith("|"):
                continue
            cells = [x.strip() for x in line.strip("|").split("|")]
            if len(cells) < 5 or not cells[0].isdigit():
                continue
            ordinal, display, site, how, notes = cells[:5]
            extracted.append({
                "record_type": kind,
                "category_id": int(ident) if kind == "category" else None,
                "shared_list_id": ident if kind == "shared" else None,
                "section_name": name,
                "ordinal": int(ordinal),
                "display_name": display,
                "site_raw": site,
                "how_raw": how,
                "notes_raw": notes,
                "source_line_start_1based": row_i + 1,
                "source_heading_line_1based": start + 1,
                "markers": re.findall(r"\\[(S|V|K)\\]", notes),
            })
        records.extend(extracted)
        audit.append({
            "type": kind, "id": ident, "name": name,
            "declared_count": declared, "extracted_rows": len(extracted),
            "source_heading_line": start + 1,
            "count_match": len(extracted) == declared,
        })
    categories = [x for x in audit if x["type"] == "category"]
    shared = [x for x in audit if x["type"] == "shared"]
    out = {
        "schema_version": "1.0.0",
        "source_filename": Path(sys.argv[1]).name,
        "embedded_section": "plan/destinations-hi.md",
        "embedded_section_sha256_scope_includes_start_heading_excludes_end_marker": hashlib.sha256(section.encode("utf-8")).hexdigest(),
        "method": "Literal numbered Markdown table rows under each category/shared-list heading; no deduplication or inferred mappings.",
        "category_section_count": len(categories),
        "shared_list_count": len(shared),
        "declared_category_slots": sum(x["declared_count"] for x in categories),
        "extracted_category_rows": sum(x["extracted_rows"] for x in categories),
        "declared_shared_slots": sum(x["declared_count"] for x in shared),
        "extracted_shared_rows": sum(x["extracted_rows"] for x in shared),
        "marker_occurrence_counts": {m: sum(m in r["markers"] for r in records) for m in "SVK"},
        "all_section_counts_match": all(x["count_match"] for x in audit),
        "records": records,
        "section_audit": audit,
    }
    Path(sys.argv[2]).write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in out if k not in ("records", "section_audit")}, ensure_ascii=False, indent=2))
    if not out["all_section_counts_match"] or len(categories) != 219 or len(shared) != 8:
        raise SystemExit("validation failed")

if __name__ == "__main__":
    main()
