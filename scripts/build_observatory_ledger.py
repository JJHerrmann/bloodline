#!/usr/bin/env python3
"""Build the reader-safe Shelton Observatory ledger feed.

Scans the private vault for supplemental case files and emits
content/supplements.json: the public production-ledger's list of Shelton
Observatory markers (case id, title, slug, published date, word count,
and a URL when a reader page exists). No manuscript prose is exported.
"""
from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "content" / "supplements.json"
DEFAULT_VAULT_DIR = ROOT.parent / "Shelton Observatory" / "Writing"
SOURCE_DIR = Path(os.environ.get("BLOODLINE_OBSERVATORY_SOURCE_DIR", str(DEFAULT_VAULT_DIR)))
READ_DIR = ROOT / "read" / "shelton-observatory"

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def frontmatter_and_body(path: Path) -> tuple[dict, str]:
    raw = path.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", raw, re.DOTALL)
    if not match:
        return {}, raw
    return yaml.safe_load(match.group(1)) or {}, match.group(2)


def prose_words(body: str) -> int:
    clean = re.sub(r"<!--[\s\S]*?-->", "", body)
    clean = re.sub(r"^\s*(#{1,6}\s.*|-{3,}|\*{3,}|_{3,})\s*$", "", clean, flags=re.MULTILINE)
    return len(re.findall(r"\b[\w'’-]+\b", clean))


def case_file_entry(path: Path) -> dict | None:
    meta, body = frontmatter_and_body(path)
    if meta.get("type") != "supplemental-case-file":
        return None

    slug = meta.get("slug")
    title = meta.get("title")
    case_id = meta.get("case_id")
    status = meta.get("status")
    published = meta.get("published")
    if hasattr(published, "isoformat"):
        published = published.isoformat()
    if not (slug and title and case_id and status):
        return None

    reader_page = READ_DIR / slug / "index.html"
    if reader_page.is_file():
        url = f"/read/shelton-observatory/{slug}/"
    else:
        patreon_url = meta.get("Patreon - Link") or meta.get("patreon_link")
        url = patreon_url if (status == "public" and patreon_url) else None

    return {
        "caseId": case_id,
        "title": title,
        "slug": slug,
        "status": status,
        "published": published if isinstance(published, str) and DATE_RE.match(published) else None,
        "words": prose_words(body),
        "url": url,
    }


def main() -> None:
    entries: list[dict] = []
    if SOURCE_DIR.is_dir():
        for path in sorted(SOURCE_DIR.glob("*.md")):
            entry = case_file_entry(path)
            if entry:
                entries.append(entry)
    entries.sort(key=lambda item: item["published"] or "9999-99-99")

    payload = {
        "generatedAt": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "caseFiles": [entry for entry in entries if entry["status"] == "public"],
    }

    if OUTPUT.is_file():
        previous = json.loads(OUTPUT.read_text(encoding="utf-8"))
        candidate = {**payload, "generatedAt": previous.get("generatedAt")}
        if previous == candidate:
            payload["generatedAt"] = previous.get("generatedAt")

    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Built {OUTPUT.relative_to(ROOT)} from {len(entries)} case file(s)")


if __name__ == "__main__":
    main()
