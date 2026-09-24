#!/usr/bin/env python3
"""Build the reader-safe workshop data file.

Only content/workshop.public.json is an input contract.  This script never
copies vault paths, notes, pitches, manuscript prose, or unapproved fields.
"""
from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "content" / "workshop.public.json"
OUTPUT = ROOT / "content" / "workshop.json"
DEFAULT_VAULT_EPISODES = Path("/home/rook/Documents/Runagarthur/Author/Mason Rok/Bloodline/Garnet Shield/Writing/Episodes")
SOURCE_DIR = Path(os.environ.get("BLOODLINE_WORKSHOP_SOURCE_DIR", str(DEFAULT_VAULT_EPISODES)))


def frontmatter_and_body(path: Path) -> tuple[dict, str]:
    raw = path.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", raw, re.DOTALL)
    if not match:
        return {}, raw
    return yaml.safe_load(match.group(1)) or {}, match.group(2)


def prose_words(body: str) -> int:
    # Match the existing dashboard's principle: count prose, not vault machinery.
    clean = re.sub(r"<!--[\s\S]*?-->|%%[\s\S]*?%%", "", body)
    clean = re.sub(r"^> ?\[![^\n]*(\n>[^\n]*)*", "", clean, flags=re.MULTILINE)
    clean = re.sub(r"^\s*(#{1,6}\s.*|-{3,}|\*{3,}|_{3,}|[-*] \[.\].*)\s*$", "", clean, flags=re.MULTILINE)
    return len(re.findall(r"\b[\w’'-]+\b", clean))


def source_episode_rows() -> tuple[list[dict], list[dict], dict, list[dict], dict]:
    if not SOURCE_DIR.is_dir():
        return [], [], {}, [], {}
    rows, planned_rows, genre_totals, mood_totals = [], [], {}, {}
    damage, incidents, next_drops = 0, 0, []
    for path in sorted(SOURCE_DIR.glob("Episode *.md"), key=lambda p: int(re.search(r"\d+", p.stem).group())):
        meta, body = frontmatter_and_body(path)
        number = meta.get("episode")
        if not isinstance(number, int):
            continue
        words = prose_words(body)
        # The standard empty episode template is a planned installment, not prose.
        if body.strip() == "Begin manuscript here." or not words:
            planned_rows.append({"number": number, "title": f"Episode {number}", "words": 0, "url": None, "published": False, "started": False})
            continue
        # A prose count is safe; title/logline/body are never exported for unpublished episodes.
        # The vault's manual publication_status is not always updated after a
        # release. A passed paid or free schedule still means readers have it.
        today = datetime.now().strftime("%Y-%m-%d")
        release_dates = [str(meta.get(key) or "") for key in ("scheduled paid post", "scheduled free post")]
        published = str(meta.get("publication_status", "")).lower() == "published" or any(
            re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) and value <= today for value in release_dates
        )
        entry = {"number": number, "title": f"Episode {number}", "words": words, "url": meta.get("publication_url") if published else None, "published": published, "started": True}
        rows.append(entry)
        planned_rows.append(entry)
        for prefix, totals in (("genre_", genre_totals), ("tone_", mood_totals)):
            for key, value in meta.items():
                if key.startswith(prefix) and isinstance(value, (int, float)):
                    totals[key.removeprefix(prefix)] = totals.get(key.removeprefix(prefix), 0) + value * words
        for item in meta.get("property_damage") or []:
            if isinstance(item, dict) and item.get("cause") == "judah":
                damage += float(item.get("cost") or 0); incidents += 1
        for item in meta.get("injuries") or []:
            if isinstance(item, dict) and item.get("cause") == "judah":
                damage += float(item.get("cost") or 0); incidents += 1
        for key, label in (("scheduled paid post", "Patron release"), ("scheduled free post", "Public release")):
            value = str(meta.get(key) or "")
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) and value >= datetime.now().strftime("%Y-%m-%d"):
                next_drops.append({"date": value, "label": f"Episode {number} · {label}", "public": True})
    return rows, planned_rows, {"amount": round(damage), "incidents": incidents, "public": True}, sorted(next_drops, key=lambda d: d["date"])[:6], {"genre": genre_totals, "mood": mood_totals}


def episode_rows(book: dict) -> list[dict]:
    source = ROOT / book.get("source", "")
    if not source.is_file():
        return []
    episodes = json.loads(source.read_text(encoding="utf-8"))
    return [
        {
            "number": item.get("episodeNumber"),
            "title": item.get("episodeTitle", "Episode"),
            "words": int(item.get("wordCount", 0)),
            "url": item.get("episodeUrl"),
            "published": item.get("releaseState") == "live",
        }
        for item in episodes
        if isinstance(item.get("episodeNumber"), int) and int(item.get("wordCount", 0)) > 0
    ]


def main() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    source_rows, source_planned_rows, source_judah, source_drops, source_tone = source_episode_rows()
    books = []
    for book in config.get("books", []):
        if not book.get("public"):
            continue
        row = {key: book[key] for key in ("id", "arc", "label", "title", "goalWords") if key in book}
        row["episodes"] = source_rows if source_rows else episode_rows(book)
        row["plannedEpisodes"] = source_planned_rows if source_rows else row["episodes"]
        row["wordCount"] = sum(item["words"] for item in row["episodes"])
        books.append(row)

    # Explicitly whitelist each public top-level field.  This is the spoiler boundary.
    tone = config.get("tone", {})
    if source_rows:
        # Preserve the editorial labels/colors, but replace their values with the
        # word-weighted scores calculated from the canonical episode frontmatter.
        tone = {**tone}
        for group in ("genre", "mood"):
            tone[group] = [{**item, "value": source_tone.get(group, {}).get(item["key"], 0)} for item in tone.get(group, [])]
        tone["episodes"] = [{"number": row["number"]} for row in source_rows]
    payload = {
        "siteTitle": config.get("siteTitle", "The Workshop"),
        "intro": config.get("intro", ""),
        "updatedLabel": config.get("updatedLabel", ""),
        "generatedAt": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "books": books,
        "nextDrops": source_drops or [item for item in config.get("nextDrops", []) if item.get("public", True)],
        "worldInventory": [item for item in config.get("worldInventory", []) if item.get("public", True) and item.get("count", 0) > 0],
        "judahTotal": source_judah if source_rows else (config.get("judahTotal", {}) if config.get("judahTotal", {}).get("public") else {}),
        "activity": config.get("activity", [])[:8],
        "tone": tone,
    }
    # A timestamp alone should not create an endless stream of deploy commits.
    # Keep the last timestamp when every reader-visible field is unchanged.
    if OUTPUT.is_file():
        previous = json.loads(OUTPUT.read_text(encoding="utf-8"))
        candidate = {**payload, "generatedAt": previous.get("generatedAt")}
        if previous == candidate:
            payload["generatedAt"] = previous.get("generatedAt")
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Built {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
