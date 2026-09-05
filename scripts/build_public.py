from __future__ import annotations

import html
import json
import runpy
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT.parent / "Garnet Shield" / "Writing" / "Episodes"
CONFIG = ROOT / "content" / "publication.json"
OUTPUT = ROOT / "read"
helpers = runpy.run_path(str(ROOT / "scripts" / "generate_scenes.py"))
markdown_to_html = helpers["markdown_to_html"]
estimate_read_minutes = helpers["estimate_read_minutes"]
KOFI_URL = "https://ko-fi.com/mindpalacegarden"


def frontmatter_value(text: str, key: str) -> str:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.startswith(f"{key}:"):
            return line.split(":", 1)[1].strip().strip("'\"")
    return ""


def nav(current: str) -> str:
    items = [("Read", "/read/"), ("Story", "/#story"), ("World", "/#world"), ("Community", "/#membership"), ("About", "/#about")]
    links = "".join(
        f'<a href="{url}"{(" aria-current=\"page\"" if label == current else "")}>{label}</a>'
        for label, url in items
    )
    return f'<header class="site-header"><div class="header-inner"><a class="brand" href="/">Bloodline</a><nav class="site-nav" aria-label="Primary">{links}</nav></div></header>'


def episode_source(number: int) -> Path:
    return SOURCE / f"Episode {number}.md"


def build_episode(entry: dict, previous: dict | None, following: dict | None, series: dict) -> None:
    source = episode_source(entry["number"])
    if not source.exists():
        raise FileNotFoundError(source)
    body, excerpt, words, _, _ = markdown_to_html(source.read_text(encoding="utf-8"))
    minutes = estimate_read_minutes(words)
    slug = f'episode-{entry["number"]}'
    destination = OUTPUT / series["slug"] / slug
    destination.mkdir(parents=True, exist_ok=True)
    prev_link = f'<a href="../episode-{previous["number"]}/">← {html.escape(previous["title"])}</a>' if previous else "<span></span>"
    next_link = f'<a href="../episode-{following["number"]}/">{html.escape(following["title"])} →</a>' if following else "<span></span>"
    canonical = f'https://bloodline.rook.works/read/{series["slug"]}/{slug}/'
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(entry["title"])} | {html.escape(series["title"])} | Bloodline</title><meta name="description" content="{html.escape(excerpt[:155], quote=True)}"><link rel="canonical" href="{canonical}"><link rel="icon" href="/favicon.ico"><link rel="stylesheet" href="/assets/reader.css"><link rel="stylesheet" href="/assets/catalog.css"><meta name="theme-color" content="#171312"></head><body>{nav("Read")}<main><header class="episode-header"><p class="eyebrow">{html.escape(series["label"])} · Episode {entry["number"]}</p><h1>{html.escape(entry["title"])}</h1><div class="episode-meta-line"><span>{entry["published"]}</span><span>{words:,} words</span><span>About {minutes} minutes</span></div></header><div class="reading-tools" aria-label="Reading controls"><button type="button" data-size-down aria-label="Decrease text size">A−</button><button type="button" data-size-up aria-label="Increase text size">A+</button><button type="button" data-theme>Light / dark</button></div><article class="episode-copy">{body}</article><aside class="support"><p class="eyebrow">Keep walking</p><h2>Read two weeks ahead.</h2><p>The public trail continues here. Members of The Hallowed can follow the story two weeks ahead on Patreon.</p><div class="support-actions"><a class="button" href="https://www.patreon.com/checkout/masonrok?rid=28657016">Read ahead on Patreon</a><a class="button secondary" href="{KOFI_URL}">Support on Ko-fi</a></div><p class="support-alt">Prefer a one-time contribution? Ko-fi supports the work without a membership.</p></aside><footer class="episode-footer"><nav class="episode-nav" aria-label="Episode navigation">{prev_link}<a href="../../">All episodes</a>{next_link}</nav></footer></main><footer class="site-footer">Bloodline: Spirits of the Smokies · Mason Rok</footer><script src="/assets/reader.js"></script></body></html>'''
    (destination / "index.html").write_text(page, encoding="utf-8")


def build_index(public: list[dict], advance: list[dict], series: dict) -> None:
    cards = []
    for entry in public:
        source = episode_source(entry["number"])
        source_text = source.read_text(encoding="utf-8")
        _, excerpt, words, _, _ = markdown_to_html(source_text)
        stinger = frontmatter_value(source_text, "logline") or excerpt[:190]
        cards.append(f'''<a class="episode-card" href="./{series["slug"]}/episode-{entry["number"]}/"><span class="episode-number">Episode {entry["number"]}</span><span class="episode-copyline"><h3>{html.escape(entry["title"])}</h3><p>{html.escape(stinger)}</p></span><span class="episode-meta">{estimate_read_minutes(words)} min · {entry["published"]}</span></a>''')
    advance_note = ""
    if advance:
        advance_url = advance[0].get("patreon_url", "https://www.patreon.com/checkout/masonrok?rid=28657016")
        advance_note = f'''<aside class="advance"><p class="eyebrow">Ahead on Patreon</p><h3>{len(advance)} advance episode{"s" if len(advance) != 1 else ""} beyond the public trail</h3><p>Join The Hallowed to continue with Episode {advance[0]["number"]}: {html.escape(advance[0]["title"])}.</p><div class="support-actions"><a class="button" href="{html.escape(advance_url, quote=True)}">Read ahead</a><a class="button secondary" href="{KOFI_URL}">Support on Ko-fi</a></div><p class="support-alt">Prefer a one-time contribution? Ko-fi supports the work without a membership.</p></aside>'''
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Read {html.escape(series["title"])} | Bloodline</title><meta name="description" content="{html.escape(series["description"], quote=True)}"><link rel="canonical" href="https://bloodline.rook.works/read/"><link rel="icon" href="/favicon.ico"><link rel="stylesheet" href="/assets/reader.css"><link rel="stylesheet" href="/assets/catalog.css"></head><body>{nav("Read")}<main><section class="reader-hero"><div class="shell"><p class="eyebrow">Bloodline: Spirits of the Smokies</p><h1>{html.escape(series["title"])}</h1><p class="lede">{html.escape(series["description"])}</p><div class="actions"><a class="button" href="./{series["slug"]}/episode-{public[0]["number"]}/">Start reading</a><a class="button secondary" href="./{series["slug"]}/episode-{public[-1]["number"]}/">Latest public episode</a></div></div></section><section class="toc"><div class="shell"><div class="toc-head"><div><p class="eyebrow">Table of contents</p><h2>Follow the trail.</h2></div><p>{len(public)} episodes available free.</p></div><div class="episode-list">{"".join(cards)}</div>{advance_note}</div></section></main><footer class="site-footer">Bloodline: Spirits of the Smokies · Mason Rok</footer></body></html>'''
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "index.html").write_text(page, encoding="utf-8")


def main() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    public = [entry for entry in config["episodes"] if entry["status"] == "public"]
    advance = [entry for entry in config["episodes"] if entry["status"] == "advance"]
    if not public:
        raise ValueError("Publication manifest must contain at least one public episode")
    for entry in public:
        if not entry.get("published") or date.fromisoformat(entry["published"]) > date.today():
            raise ValueError(f'Public episode {entry["number"]} has an invalid publication date')
    for index, entry in enumerate(public):
        build_episode(entry, public[index - 1] if index else None, public[index + 1] if index + 1 < len(public) else None, config["series"])
    build_index(public, advance, config["series"])
    print(f"Built {len(public)} public episodes in {OUTPUT}")


if __name__ == "__main__":
    main()
