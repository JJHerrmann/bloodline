from __future__ import annotations

import html
import os
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE_DIR = ROOT.parent / "Shelton Observatory" / "Writing"
SOURCE_DIR = Path(os.environ.get("BLOODLINE_OBSERVATORY_SOURCE_DIR", str(DEFAULT_SOURCE_DIR)))
OUTPUT_DIR = ROOT / "read" / "shelton-observatory"

HEADING_RE = re.compile(r"^#{1,6}\s")


def frontmatter_and_body(path: Path) -> tuple[dict, str]:
    raw = path.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", raw, re.DOTALL)
    if not match:
        return {}, raw
    return yaml.safe_load(match.group(1)) or {}, match.group(2)


def inline(text: str) -> str:
    escaped = html.escape(text, quote=False)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"_([^_]+)_", r"<em>\1</em>", escaped)
    escaped = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", escaped)
    escaped = re.sub(
        r"^(NEWSOME|KLEIN|WINTERS|BELL|MULLINS|VOICE(?: [12])?|UNKNOWN ENTITY(?:,[^:]+)?)(:)",
        r'<strong class="speaker">\1\2</strong>',
        escaped,
    )
    if escaped.startswith("[") and escaped.endswith("]"):
        escaped = f'<em class="stage-direction">{escaped}</em>'
    return escaped


def split_blocks(lines: list[str]) -> list[list[str]]:
    blocks: list[list[str]] = [[]]
    for line in lines:
        if line.strip() == "---":
            blocks.append([])
        else:
            blocks[-1].append(line)
    return blocks


def classify_block(block: list[str]) -> str:
    stripped_lines = [line.strip() for line in block]
    if not any(stripped_lines):
        return "empty"
    if next((s for s in stripped_lines if s), "") == "> [!text-message]":
        return "message"
    if any(HEADING_RE.match(s) for s in stripped_lines):
        return "body"
    return "letter"


def render_message_block(block: list[str]) -> str:
    quoted: list[str] = []
    for line in block[1:]:
        stripped = line.strip()
        if stripped.startswith(">"):
            quoted.append(stripped[1:].lstrip())
        elif not stripped:
            quoted.append("")

    metadata: dict[str, str] = {}
    messages: list[str] = []
    current: list[str] = []
    for item in quoted:
        match = re.match(r"^\*\*(From|To|Status):\*\*\s*(.+)$", item)
        if match and not messages and not current:
            metadata[match.group(1).lower()] = match.group(2).strip()
        elif not item:
            if current:
                messages.append(" ".join(current))
                current.clear()
        else:
            current.append(item)
    if current:
        messages.append(" ".join(current))

    sender = metadata.get("from", "Unknown sender")
    recipient = metadata.get("to", "Unknown recipient")
    status = metadata.get("status", "Delivered")
    parts = [
        '<section class="message-capture" '
        f'aria-label="Text message from {html.escape(sender)} to {html.escape(recipient)}">',
        f'<p class="message-contact"><strong>{inline(sender)}</strong>'
        f'Text Message · to {inline(recipient)}</p>',
    ]
    parts.extend(f'<p class="message-bubble">{inline(message)}</p>' for message in messages)
    parts.append(f'<p class="message-status">{inline(status)}</p>')
    parts.append("</section>")
    return "\n".join(parts)


def paragraph_groups(block: list[str]) -> list[str]:
    """Blank-line-separated groups, joined with <br> where the source used a
    markdown hard break (trailing double space) and a space otherwise."""
    groups: list[str] = []
    current: list[str] = []

    def flush() -> None:
        if not current:
            return
        rendered = ""
        # Each source line within a group is its own visual line here (the
        # vault is written for Obsidian's lenient line breaks, not strict
        # CommonMark hard breaks), so join with <br> rather than a space.
        rendered = "<br>".join(inline(raw_line.strip()) for raw_line in current)
        groups.append(rendered)
        current.clear()

    for line in block:
        if not line.strip():
            flush()
        else:
            current.append(line)
    flush()
    return groups


def render_letter_block(block: list[str]) -> str:
    groups = paragraph_groups(block)
    if not groups:
        return ""
    salutation = re.sub(r"[,.]$", "", re.sub(r"<[^>]+>", "", groups[0].split("<br>")[0])).strip()
    signature = re.sub(r"<[^>]+>", " ", groups[-1].split("<br>")[0]).strip()
    label = f"Letter from {html.escape(signature)} to {html.escape(salutation)}" if len(groups) > 1 else f"Letter to {html.escape(salutation)}"
    parts = [f'<section class="letter-capture" aria-label="{label}">']
    for index, group in enumerate(groups):
        css_class = "letter-signature" if index == len(groups) - 1 and len(groups) > 1 else ""
        parts.append(f'<p{f" class={css_class!r}" if css_class else ""}>{group}</p>')
    parts.append("</section>")
    return "\n".join(parts)


def render_body_block(block: list[str]) -> list[str]:
    output: list[str] = []
    paragraph: list[str] = []

    def flush() -> None:
        if paragraph:
            value = " ".join(part.strip() for part in paragraph).strip()
            output.append(f"<p>{inline(value)}</p>")
            paragraph.clear()

    for line in block:
        stripped = line.strip()
        standalone = (
            re.match(r"^(NEWSOME|KLEIN|WINTERS|BELL|MULLINS|VOICE(?: [12])?|UNKNOWN ENTITY(?:,[^:]+)?):", stripped)
            or re.match(r"^\*\*[^*]+\*\*:", stripped)
            or re.match(r"^(Case status|Entity status|Access):", stripped)
            or (stripped.startswith("[") and stripped.endswith("]"))
        )
        if not stripped:
            flush()
        elif stripped.startswith("#### "):
            flush()
            output.append(f"<h3>{inline(stripped[5:])}</h3>")
        elif stripped.startswith("### "):
            flush()
            output.append(f"<h2>{inline(stripped[4:])}</h2>")
        elif stripped.startswith("## "):
            flush()
            output.append(f"<h2>{inline(stripped[3:])}</h2>")
        elif stripped.startswith("# "):
            flush()
            output.append(f"<h2>{inline(stripped[2:])}</h2>")
        elif standalone:
            flush()
            output.append(f"<p>{inline(stripped)}</p>")
        else:
            paragraph.append(stripped)
    flush()
    return output


def markdown_body(text: str) -> tuple[str, int]:
    body_text = text.strip()
    blocks = split_blocks(body_text.splitlines())
    rendered_blocks: list[str] = []
    for block in blocks:
        kind = classify_block(block)
        if kind == "empty":
            continue
        if kind == "message":
            rendered_blocks.append(render_message_block(block))
        elif kind == "letter":
            rendered_blocks.append(render_letter_block(block))
        else:
            rendered_blocks.append("\n".join(render_body_block(block)))
    output = "\n<hr>\n".join(part for part in rendered_blocks if part)
    plain = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", output))
    return output, len(plain.split())


def build_case_file(path: Path) -> str | None:
    meta, raw_body = frontmatter_and_body(path)
    if meta.get("type") != "supplemental-case-file" or meta.get("status") != "public":
        return None

    slug = meta.get("slug")
    title = meta.get("title")
    case_id = meta.get("case_id")
    if not (slug and title and case_id):
        print(f"Skipping {path.name}: missing slug/title/case_id")
        return None

    deck = meta.get("deck", "A case file from the Shelton Observatory archive.")
    hero_image = meta.get("hero_image", "/images/hootin-anne-newsome.webp")
    hero_image_alt = meta.get("hero_image_alt", f"{title}, a Shelton Observatory case file")
    share_image = meta.get("share_image", hero_image)
    url = f"https://bloodline.rook.works/read/shelton-observatory/{slug}/"

    body, words = markdown_body(raw_body)
    minutes = max(1, round(words / 240))
    title_html = html.escape(title, quote=False)
    deck_html = html.escape(deck, quote=False)
    deck_attr = html.escape(deck, quote=True)
    case_id_html = html.escape(case_id, quote=False)

    page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title_html} | Shelton Observatory | Bloodline</title>
<meta name="description" content="{deck_attr}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Bloodline">
<meta property="og:title" content="{title_html} | Shelton Observatory">
<meta property="og:description" content="{deck_attr}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="https://bloodline.rook.works{share_image}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="From the Shelton Observatory: {title_html}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title_html} | Shelton Observatory">
<meta name="twitter:description" content="{deck_attr}">
<meta name="twitter:image" content="https://bloodline.rook.works{share_image}">
<meta name="twitter:image:alt" content="From the Shelton Observatory: {title_html}">
<link rel="icon" href="/favicon.ico"><link rel="stylesheet" href="/assets/reader.css"><meta name="theme-color" content="#171312">
<style>
.case-hero{{display:grid;grid-template-columns:150px 1fr;gap:30px;align-items:center;width:min(780px,calc(100% - 36px));margin:auto;padding:48px 0 34px}}
.case-hero img{{display:block;width:100%;height:auto;aspect-ratio:2/3;object-fit:cover;border:1px solid var(--rule);filter:saturate(.8)}}
.case-hero h1{{font-size:clamp(38px,6vw,62px)}}.case-id{{color:var(--gold);font-size:11px;font-weight:700;letter-spacing:.16em;text-transform:uppercase}}
.case-deck{{max-width:590px;color:var(--muted);font:17px/1.55 Georgia,serif}}
.case-copy h2{{margin:2.2em 0 .65em;color:var(--gold);font-size:1.5em;text-align:center;letter-spacing:.04em}}
.case-copy h3{{margin:1.8em 0 .8em;color:var(--gold);font-size:1.2em;letter-spacing:.06em;text-align:center}}
.case-copy hr{{margin:3em 0;border:0;border-top:1px solid #644b3d}}
.case-copy code{{color:var(--gold);font:0.82em ui-monospace,SFMono-Regular,Consolas,monospace}}
.message-capture{{width:min(390px,100%);margin:1.5em auto 3em;padding:14px 12px 18px;border:1px solid #514d49;border-radius:26px;background:#111;color:#f5f5f7;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;box-shadow:0 16px 38px rgba(0,0,0,.24)}}
.message-contact{{margin:0 0 16px!important;padding:2px 8px 12px;border-bottom:1px solid #303033;text-align:center;font-size:.78em;line-height:1.25;color:#aaa}}
.message-contact strong{{display:block;color:#f5f5f7;font-size:1.05em}}
.message-bubble{{width:fit-content;max-width:88%;margin:0 0 5px auto!important;padding:9px 13px;border-radius:18px 18px 5px 18px;background:#0a84ff;color:#fff;font-size:.83em;line-height:1.38}}
.message-status{{margin:0 7px 0 0!important;text-align:right;color:#8e8e93;font-size:.62em;line-height:1.3}}
.letter-capture{{width:min(520px,100%);margin:1.5em auto 3em;padding:28px 32px;border:1px solid #644b3d;background:linear-gradient(180deg,rgba(230,201,133,.06),rgba(230,201,133,.02));font-family:Georgia,serif;font-style:italic;color:#e3d9c8;line-height:1.6}}
.letter-capture p{{margin:0 0 1em}}
.letter-capture p:last-child{{margin-bottom:0}}
.letter-signature{{margin-top:1.4em!important;font-style:normal;color:var(--gold);letter-spacing:.02em}}
.speaker{{color:#e6c985;font-family:Arial,Helvetica,sans-serif;font-size:.78em;letter-spacing:.04em}}
.stage-direction{{color:var(--muted)}}
@media(max-width:600px){{.case-hero{{grid-template-columns:92px 1fr;gap:18px;align-items:start}}.case-hero h1{{font-size:36px}}}}
</style></head><body>
<header class="site-header"><div class="header-inner"><a class="brand" href="/">Bloodline</a><nav class="site-nav" aria-label="Primary"><a href="/read/">Read</a><a href="/#story">Story</a><a href="/#world" aria-current="page">World</a><a href="/#membership">Community</a><a href="/#about">About</a></nav></div></header>
<main><header class="case-hero"><img src="{hero_image}" alt="{html.escape(hero_image_alt, quote=True)}"><div><p class="case-id">Shelton Observatory · Case File {case_id_html}</p><h1>{title_html}</h1><p class="case-deck">{deck_html}</p><div class="episode-meta-line" style="justify-content:flex-start"><span>Public case file</span><span>{words:,} words</span><span>About {minutes} minutes</span></div></div></header>
<div class="reading-tools" aria-label="Reading controls"><button type="button" data-size-down aria-label="Decrease text size">A−</button><button type="button" data-size-up aria-label="Increase text size">A+</button><button type="button" data-theme>Light / dark</button></div>
<article class="episode-copy case-copy">{body}</article>
<aside class="support"><p class="eyebrow">Beyond the main trail</p><h2>More files are waiting.</h2><p>Read <em>The Garnet Shield</em> free, or support Bloodline on Patreon for early episodes and stories from the wider setting.</p><div class="actions"><a class="button secondary" href="/read/">Read The Garnet Shield</a><a class="button" href="https://www.patreon.com/checkout/masonrok?rid=28657908">Follow the wider story</a></div></aside>
<footer class="episode-footer"><nav class="episode-nav" aria-label="Case file navigation"><span></span><a href="/#field-note">Return to the archive</a><span></span></nav></footer></main>
<footer class="site-footer">Bloodline: Spirits of the Smokies · Mason Rok</footer><script src="/assets/reader.js"></script></body></html>'''

    output_path = OUTPUT_DIR / slug / "index.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(page, encoding="utf-8")
    return f"read/shelton-observatory/{slug}/index.html"


def main() -> None:
    if not SOURCE_DIR.is_dir():
        print(f"Source directory not found: {SOURCE_DIR}")
        return
    built = []
    for path in sorted(SOURCE_DIR.glob("*.md")):
        result = build_case_file(path)
        if result:
            built.append(result)
    for output in built:
        print(f"Built {output}")
    if not built:
        print("No public case files found.")


if __name__ == "__main__":
    main()
