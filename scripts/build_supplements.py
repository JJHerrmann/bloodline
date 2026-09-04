from __future__ import annotations

import html
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT.parent / "Shelton Observatory" / "Writing" / "Observation Case File - 03252019.md"
OUTPUT = ROOT / "read" / "shelton-observatory" / "voices-at-lovers-leap" / "index.html"


def strip_frontmatter(text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for index, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                return "\n".join(lines[index + 1 :]).strip()
    return text.strip()


def inline(text: str) -> str:
    escaped = html.escape(text, quote=False)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"_([^_]+)_", r"<em>\1</em>", escaped)
    escaped = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", escaped)
    escaped = re.sub(
        r"^(NEWSOME|KLEIN|WINTERS|VOICE(?: [12])?|UNKNOWN ENTITY(?:,[^:]+)?)(:)",
        r'<strong class="speaker">\1\2</strong>',
        escaped,
    )
    if escaped.startswith("[") and escaped.endswith("]"):
        escaped = f'<em class="stage-direction">{escaped}</em>'
    return escaped


def markdown_body(text: str) -> tuple[str, int]:
    lines = strip_frontmatter(text).splitlines()
    output: list[str] = []
    paragraph: list[str] = []

    def flush() -> None:
        if paragraph:
            value = " ".join(part.strip() for part in paragraph).strip()
            output.append(f"<p>{inline(value)}</p>")
            paragraph.clear()

    for line in lines:
        stripped = line.strip()
        standalone = (
            re.match(r"^(NEWSOME|KLEIN|WINTERS|VOICE(?: [12])?|UNKNOWN ENTITY(?:,[^:]+)?):", stripped)
            or re.match(r"^\*\*[^*]+\*\*:", stripped)
            or re.match(r"^(Case status|Entity status|Access):", stripped)
            or (stripped.startswith("[") and stripped.endswith("]"))
        )
        if not stripped:
            flush()
        elif stripped == "---":
            flush()
            output.append("<hr>")
        elif stripped.startswith("#### "):
            flush()
            output.append(f"<h3>{inline(stripped[5:])}</h3>")
        elif stripped.startswith("### "):
            flush()
            output.append(f"<h2>{inline(stripped[4:])}</h2>")
        elif standalone:
            flush()
            output.append(f"<p>{inline(stripped)}</p>")
        else:
            paragraph.append(stripped)
    flush()
    plain = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", " ".join(output)))
    return "\n".join(output), len(plain.split())


def main() -> None:
    body, words = markdown_body(SOURCE.read_text(encoding="utf-8"))
    minutes = max(1, round(words / 240))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>The Voices at Lover’s Leap | Shelton Observatory | Bloodline</title>
<meta name="description" content="A recorded interview concerning Jeffrey Winters, a homemade observation pod, and the voices heard above Lover’s Leap.">
<link rel="canonical" href="https://bloodline.rook.works/read/shelton-observatory/voices-at-lovers-leap/">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Bloodline">
<meta property="og:title" content="The Voices at Lover’s Leap | Shelton Observatory">
<meta property="og:description" content="A recorded interview concerning Jeffrey Winters, a homemade observation pod, and the voices heard above Lover’s Leap.">
<meta property="og:url" content="https://bloodline.rook.works/read/shelton-observatory/voices-at-lovers-leap/">
<meta property="og:image" content="https://bloodline.rook.works/images/shelton-observatory-voices-share-card.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="From the Shelton Observatory: The Voices at Lover’s Leap, filed by Anne Newsome">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="The Voices at Lover’s Leap | Shelton Observatory">
<meta name="twitter:description" content="A recorded interview concerning Jeffrey Winters, a homemade observation pod, and the voices heard above Lover’s Leap.">
<meta name="twitter:image" content="https://bloodline.rook.works/images/shelton-observatory-voices-share-card.jpg">
<meta name="twitter:image:alt" content="From the Shelton Observatory: The Voices at Lover’s Leap, filed by Anne Newsome">
<link rel="icon" href="/favicon.ico"><link rel="stylesheet" href="/assets/reader.css"><meta name="theme-color" content="#171312">
<style>
.case-hero{{display:grid;grid-template-columns:150px 1fr;gap:30px;align-items:center;width:min(780px,calc(100% - 36px));margin:auto;padding:48px 0 34px}}
.case-hero img{{display:block;width:100%;aspect-ratio:2/3;object-fit:cover;border:1px solid var(--rule);filter:saturate(.8)}}
.case-hero h1{{font-size:clamp(38px,6vw,62px)}}.case-id{{color:var(--gold);font-size:11px;font-weight:700;letter-spacing:.16em;text-transform:uppercase}}
.case-deck{{max-width:590px;color:var(--muted);font:17px/1.55 Georgia,serif}}
.case-copy h2{{margin:2.2em 0 .65em;color:var(--gold);font-size:1.5em;text-align:center;letter-spacing:.04em}}
.case-copy h3{{margin:1.8em 0 .8em;color:var(--gold);font-size:1.2em;letter-spacing:.06em;text-align:center}}
.case-copy hr{{margin:3em 0;border:0;border-top:1px solid #644b3d}}
.case-copy code{{color:var(--gold);font:0.82em ui-monospace,SFMono-Regular,Consolas,monospace}}
.speaker{{color:#e6c985;font-family:Arial,Helvetica,sans-serif;font-size:.78em;letter-spacing:.04em}}
.stage-direction{{color:var(--muted)}}
@media(max-width:600px){{.case-hero{{grid-template-columns:92px 1fr;gap:18px;align-items:start}}.case-hero h1{{font-size:36px}}}}
</style></head><body>
<header class="site-header"><div class="header-inner"><a class="brand" href="/">Bloodline</a><nav class="site-nav" aria-label="Primary"><a href="/read/">Read</a><a href="/#story">Story</a><a href="/#world" aria-current="page">World</a><a href="/#membership">Community</a><a href="/#about">About</a></nav></div></header>
<main><header class="case-hero"><img src="/images/hootin-anne-newsome.webp" alt="Anne Newsome, associate researcher at the Shelton Observatory"><div><p class="case-id">Shelton Observatory · Case File SO-18-LL-04</p><h1>The Voices at Lover’s Leap</h1><p class="case-deck">A recorded interview concerning Jeffrey Winters, a homemade observation pod, and the voices heard above Lover’s Leap.</p><div class="episode-meta-line" style="justify-content:flex-start"><span>Public case file</span><span>{words:,} words</span><span>About {minutes} minutes</span></div></div></header>
<div class="reading-tools" aria-label="Reading controls"><button type="button" data-size-down aria-label="Decrease text size">A−</button><button type="button" data-size-up aria-label="Increase text size">A+</button><button type="button" data-theme>Light / dark</button></div>
<article class="episode-copy case-copy">{body}</article>
<aside class="support"><p class="eyebrow">Beyond the main trail</p><h2>More files are waiting.</h2><p>Read <em>The Garnet Shield</em> free, or support Bloodline on Patreon for early episodes and stories from the wider setting.</p><div class="actions"><a class="button secondary" href="/read/">Read The Garnet Shield</a><a class="button" href="https://www.patreon.com/checkout/masonrok?rid=28657908">Follow the wider story</a></div></aside>
<footer class="episode-footer"><nav class="episode-nav" aria-label="Case file navigation"><span></span><a href="/#field-note">Return to the archive</a><span></span></nav></footer></main>
<footer class="site-footer">Bloodline: Spirits of the Smokies · Mason Rok</footer><script src="/assets/reader.js"></script></body></html>'''
    OUTPUT.write_text(page, encoding="utf-8")
    print(f"Built {OUTPUT.relative_to(ROOT)} from {SOURCE}")


if __name__ == "__main__":
    main()
