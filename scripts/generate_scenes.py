from __future__ import annotations

import json
import html
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


SOURCE_DIR = Path(r"R:\RookVault\01_Active\Mindpalace\Authorship\Mason Rok\Bloodline\Garnet\01_Story\Scenes")
OUTPUT_DIR = Path(r"R:\Rookworks\bloodline\scenes")
MANIFEST_PATH = OUTPUT_DIR / "scenes.json"
NOTES_FORM_ACTION = "https://formspree.io/f/xzdyknwz"

SKIP_FILES = {"compiled_scenes.md", "Scenes.md"}
WIKI_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
EMPHASIS_RE = re.compile(r"(\*|_)([^*_]+)\1")


@dataclass
class SceneDoc:
    source_name: str
    slug: str
    meta: dict[str, Any]
    body_html: str
    excerpt: str
    word_count: int
    title: str
    subtitle: str | None
    order_key: tuple[int, str]


def parse_front_matter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
      return {}, text

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text

    end_index = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_index = i
            break

    if end_index is None:
        return {}, text

    front_lines = lines[1:end_index]
    body = "\n".join(lines[end_index + 1 :]).lstrip("\n")

    data: dict[str, Any] = {}
    current_key: str | None = None
    current_list: list[str] | None = None

    for raw_line in front_lines:
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith("- "):
            if current_key is None:
                continue
            if current_list is None:
                current_list = []
                data[current_key] = current_list
            current_list.append(clean_meta_value(stripped[2:]))
            continue

        if ":" in line:
            key, value = line.split(":", 1)
            current_key = key.strip()
            value = value.strip()
            if value:
                data[current_key] = clean_meta_value(value)
                current_list = None
            else:
                data[current_key] = []
                current_list = data[current_key]
            continue

    return data, body


def clean_meta_value(value: str) -> str:
    value = value.strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        value = value[1:-1]
    return value.strip()


def strip_dataview_blocks(text: str) -> str:
    lines = text.splitlines()
    kept: list[str] = []
    in_code = False
    code_lang = ""

    for line in lines:
        if line.strip().startswith("```"):
            marker = line.strip()[3:].strip().lower()
            if not in_code:
                in_code = True
                code_lang = marker
                continue
            if in_code:
                in_code = False
                code_lang = ""
                continue

        if in_code and code_lang == "dataviewjs":
            continue

        if in_code:
            kept.append(line)
        else:
            kept.append(line)

    return "\n".join(kept)


def render_inline(text: str) -> str:
    text = normalize_wiki_links(text)
    escaped = html.escape(text, quote=False)
    escaped = EMPHASIS_RE.sub(lambda m: f"<em>{m.group(2)}</em>", escaped)
    return escaped.replace("&mdash;", "—")


def normalize_wiki_links(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        inner = match.group(1).strip()
        if "|" in inner:
            return inner.split("|")[-1].strip()
        return inner

    return WIKI_LINK_RE.sub(repl, text)


def normalize_plain_text(text: str) -> str:
    text = normalize_wiki_links(text)
    text = text.replace("—", "—")
    text = re.sub(r"(\*|_)([^*_]+)\1", r"\2", text)
    return text


def markdown_to_html(text: str) -> tuple[str, str, int]:
    lines = strip_dataview_blocks(text).splitlines()
    blocks: list[str] = []
    paragraph: list[str] = []
    excerpt = ""

    def flush_paragraph() -> None:
        nonlocal excerpt
        if not paragraph:
            return
        raw = " ".join(part.strip() for part in paragraph if part.strip()).strip()
        if not raw:
            paragraph.clear()
            return
        raw = normalize_plain_text(raw)
        rendered = render_inline(raw)
        blocks.append(f"<p>{rendered}</p>")
        if not excerpt:
            excerpt = raw
        paragraph.clear()

    in_code = False
    code_lines: list[str] = []

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()

        if stripped.startswith("```"):
            if in_code:
                code_html = html.escape("\n".join(code_lines))
                blocks.append(f'<pre class="overflow-x-auto rounded-2xl border border-neutral-800 bg-neutral-950/80 p-4 text-sm text-neutral-200"><code>{code_html}</code></pre>')
                code_lines = []
                in_code = False
            else:
                flush_paragraph()
                in_code = True
            continue

        if in_code:
            code_lines.append(raw_line)
            continue

        if not stripped or stripped == "-------------":
            flush_paragraph()
            continue

        if stripped.startswith("## "):
            flush_paragraph()
            blocks.append(f"<h2>{render_inline(stripped[3:])}</h2>")
            continue

        if stripped.startswith("# "):
            flush_paragraph()
            blocks.append(f"<h1>{render_inline(stripped[2:])}</h1>")
            continue

        paragraph.append(raw_line)

    flush_paragraph()

    plain_text = re.sub(r"\s+", " ", normalize_plain_text(strip_tags(" ".join(blocks)))).strip()
    word_count = len(plain_text.split()) if plain_text else 0
    return "\n".join(blocks), excerpt, word_count


def strip_tags(value: str) -> str:
    return re.sub(r"<[^>]+>", "", value)


def build_scene_document(path: Path) -> SceneDoc:
    raw = path.read_text(encoding="utf-8")
    meta, body = parse_front_matter(raw)
    body_html, excerpt, word_count = markdown_to_html(body)

    title = str(meta.get("title") or path.stem.replace("-", " ").replace("_", " ").title())
    subtitle = meta.get("subtitle")
    slug = path.stem
    order_raw = str(meta.get("order") or path.stem)
    order_match = re.search(r"-?\d+", order_raw)
    order_num = int(order_match.group(0)) if order_match else 999999

    return SceneDoc(
        source_name=path.name,
        slug=slug,
        meta=meta,
        body_html=body_html,
        excerpt=excerpt,
        word_count=word_count,
        title=title,
        subtitle=subtitle if subtitle else None,
        order_key=(order_num, path.name.lower()),
    )


def format_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%B %d, %Y")
    except ValueError:
        return value


def render_meta_chips(scene: SceneDoc) -> str:
    chips: list[str] = []
    for label in [
        format_date(scene.meta.get("date")),
        scene.meta.get("arc"),
        f'Chapter {scene.meta.get("chapter")}' if scene.meta.get("chapter") else None,
        f'Scene {scene.meta.get("scene")}' if scene.meta.get("scene") else None,
        scene.meta.get("status"),
        f"{scene.word_count} words",
    ]:
        if label:
            chips.append(
                f'<span class="rounded-full border border-neutral-700 bg-neutral-900/70 px-3 py-1 text-xs uppercase tracking-[0.18em] text-neutral-300">{html.escape(str(label))}</span>'
            )
    return "\n".join(chips)


def render_list(items: Any) -> str:
    if not items:
        return ""
    if isinstance(items, str):
        items = [items]
    rows = "".join(f"<li>{render_inline(str(item))}</li>" for item in items if str(item).strip())
    if not rows:
        return ""
    return f'<ul class="space-y-2 text-sm leading-6 text-neutral-300">{rows}</ul>'


def render_scene_page(scene: SceneDoc, previous_scene: SceneDoc | None, next_scene: SceneDoc | None) -> str:
    scene_title_text = html.escape(scene.title, quote=False)
    subtitle_html = (
        f'<p class="mt-3 text-lg text-rose-200">{html.escape(scene.subtitle, quote=False)}</p>' if scene.subtitle else ""
    )
    pov_list = render_list(scene.meta.get("pov"))
    location_list = render_list(scene.meta.get("locations"))
    side_prev = (
        f"""<a href="./{previous_scene.slug}.html" class="group fixed left-4 top-1/2 z-40 hidden -translate-y-1/2 xl:flex max-w-[13rem] items-center gap-3 rounded-2xl border border-neutral-800 bg-neutral-950/90 px-4 py-3 text-sm font-semibold text-neutral-200 shadow-2xl shadow-black/40 backdrop-blur transition hover:border-rose-800 hover:bg-neutral-900">
  <span class="text-lg text-rose-300 transition group-hover:-translate-x-1">←</span>
  <span class="min-w-0">
    <span class="block text-[11px] uppercase tracking-[0.18em] text-neutral-500">Previous</span>
    <span class="mt-1 block truncate">{html.escape(previous_scene.title, quote=False)}</span>
  </span>
</a>"""
        if previous_scene
        else ""
    )
    side_next = (
        f"""<a href="./{next_scene.slug}.html" class="group fixed right-4 top-1/2 z-40 hidden -translate-y-1/2 xl:flex max-w-[13rem] items-center justify-end gap-3 rounded-2xl border border-rose-900/60 bg-rose-950/80 px-4 py-3 text-right text-sm font-semibold text-rose-100 shadow-2xl shadow-black/40 backdrop-blur transition hover:bg-rose-900">
  <span class="min-w-0">
    <span class="block text-[11px] uppercase tracking-[0.18em] text-rose-300/70">Next</span>
    <span class="mt-1 block truncate">{html.escape(next_scene.title, quote=False)}</span>
  </span>
  <span class="text-lg transition group-hover:translate-x-1">→</span>
</a>"""
        if next_scene
        else ""
    )
    bottom_prev = (
        f'<a href="./{previous_scene.slug}.html" class="rounded-2xl border border-neutral-700 px-4 py-3 text-sm font-semibold text-neutral-200 transition hover:bg-neutral-900 xl:hidden">← {html.escape(previous_scene.title, quote=False)}</a>'
        if previous_scene
        else '<span></span>'
    )
    bottom_next = (
        f'<a href="./{next_scene.slug}.html" class="rounded-2xl border border-rose-800 bg-rose-950/60 px-4 py-3 text-sm font-semibold text-rose-100 transition hover:bg-rose-900/80 xl:hidden">{html.escape(next_scene.title, quote=False)} →</a>'
        if next_scene
        else ""
    )
    scene_title_attr = html.escape(scene.title, quote=True)
    scene_slug_attr = html.escape(scene.slug, quote=True)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{scene_title_text} | Bloodline Alpha</title>
  <meta name="description" content="{html.escape((scene.excerpt or scene.title)[:155])}">
  <meta name="robots" content="noindex,nofollow,noarchive,noimageindex">
  <meta name="theme-color" content="#111827">
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="../alpha/auth.js"></script>
  <style>
    .scene-copy h1, .scene-copy h2 {{
      color: #fff7ed;
      font-weight: 700;
      line-height: 1.2;
    }}
    .scene-copy h1 {{ font-size: 1.6rem; margin-top: 2rem; }}
    .scene-copy h2 {{ font-size: 1.35rem; margin-top: 2rem; }}
    .scene-copy p {{
      margin-top: 1rem;
      color: rgb(229 229 229);
      line-height: 1.9;
      font-size: 1.05rem;
    }}
    .scene-copy ul {{
      margin-top: 1rem;
      padding-left: 1.25rem;
      list-style: disc;
    }}
    .scene-copy li {{ margin-top: 0.35rem; }}
  </style>
</head>
<body class="min-h-screen bg-neutral-950 text-neutral-100 antialiased">
  <script>
    window.BloodlineAlphaAuth.requireAuth({{ redirectTo: "../alpha/index.html" }});
  </script>
  {side_prev}
  {side_next}

  <main class="mx-auto max-w-5xl px-6 py-12 md:py-16">
    <header class="border-b border-neutral-800 pb-8">
      <div class="flex flex-wrap items-center gap-3">
        <a href="../scenes/index.html" class="rounded-2xl border border-neutral-700 px-4 py-2 text-sm font-semibold text-neutral-200 transition hover:bg-neutral-900">Scene Index</a>
        <a href="../alpha/index.html" class="rounded-2xl border border-neutral-700 px-4 py-2 text-sm font-semibold text-neutral-200 transition hover:bg-neutral-900">Portal</a>
      </div>
      <p class="mt-6 text-xs uppercase tracking-[0.24em] text-rose-300">{html.escape(scene.source_name)}</p>
      <h1 class="mt-3 text-4xl font-bold tracking-tight text-neutral-50 md:text-5xl">{scene_title_text}</h1>
      {subtitle_html}
      <div class="mt-6 flex flex-wrap gap-2">
        {render_meta_chips(scene)}
      </div>
      <p class="mt-4 text-sm text-neutral-400">Please leave comments on the scene using the form at the end of the page.</p>
    </header>

    <section class="mt-8 grid gap-6 md:grid-cols-[0.68fr_0.32fr]">
      <article class="rounded-3xl border border-neutral-800 bg-neutral-900/65 p-6 md:p-8">
        <div class="scene-copy">
          {scene.body_html}
        </div>
      </article>

      <aside class="space-y-6">
        <section class="rounded-3xl border border-neutral-800 bg-neutral-900/65 p-6">
          <h2 class="text-lg font-semibold text-neutral-50">Point of view</h2>
          <div class="mt-3">{pov_list or '<p class="text-sm text-neutral-400">Not specified.</p>'}</div>
        </section>
        <section class="rounded-3xl border border-neutral-800 bg-neutral-900/65 p-6">
          <h2 class="text-lg font-semibold text-neutral-50">Locations</h2>
          <div class="mt-3">{location_list or '<p class="text-sm text-neutral-400">Not specified.</p>'}</div>
        </section>
      </aside>
    </section>

    <section class="mt-8 rounded-3xl border border-neutral-800 bg-neutral-900/65 p-6 md:p-8">
      <div class="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <p class="text-xs uppercase tracking-[0.24em] text-rose-300">Reader Feedback</p>
          <h2 class="mt-2 text-2xl font-semibold text-neutral-50">Notes on this scene</h2>
          <p class="mt-2 max-w-2xl text-sm leading-6 text-neutral-300">
            Alpha readers can send reactions, line notes, continuity catches, or general impressions directly from the page.
          </p>
        </div>
        <p class="text-xs text-neutral-500">Submits to the current Formspree inbox.</p>
      </div>

      <div data-fs-success class="hidden mt-6 rounded-2xl border border-emerald-900/60 bg-emerald-950/40 px-4 py-3 text-sm text-emerald-100"></div>
      <div data-fs-error class="hidden mt-4 rounded-2xl border border-red-900/60 bg-red-950/40 px-4 py-3 text-sm text-red-100"></div>

      <form id="reader-note-form" class="reader-note-form mt-6 grid gap-4 md:grid-cols-2" action="{NOTES_FORM_ACTION}" method="POST" data-scene-title="{scene_title_attr}">
        <input type="hidden" name="form_type" value="alpha_reader_note">
        <input type="hidden" name="scene_title" value="{scene_title_attr}">
        <input type="hidden" name="scene_slug" value="{scene_slug_attr}">

        <label class="block">
          <span class="mb-2 block text-sm font-medium text-neutral-200">Name</span>
          <input
            type="text"
            name="reader_name"
            required
            data-fs-field
            class="w-full rounded-2xl border border-neutral-700 bg-neutral-950 px-4 py-3 text-base text-neutral-100 outline-none transition focus:border-rose-500 focus:ring-2 focus:ring-rose-500/30"
            placeholder="Reader name">
          <span data-fs-error="reader_name" class="mt-2 block text-sm text-red-300"></span>
        </label>

        <label class="block">
          <span class="mb-2 block text-sm font-medium text-neutral-200">Email <span class="text-neutral-500">(optional)</span></span>
          <input
            type="email"
            name="reader_email"
            data-fs-field
            class="w-full rounded-2xl border border-neutral-700 bg-neutral-950 px-4 py-3 text-base text-neutral-100 outline-none transition focus:border-rose-500 focus:ring-2 focus:ring-rose-500/30"
            placeholder="reader@domain.com">
          <span data-fs-error="reader_email" class="mt-2 block text-sm text-red-300"></span>
        </label>

        <label class="block md:col-span-2">
          <span class="mb-2 block text-sm font-medium text-neutral-200">Notes</span>
          <textarea
            name="reader_notes"
            required
            rows="7"
            data-fs-field
            class="w-full rounded-2xl border border-neutral-700 bg-neutral-950 px-4 py-3 text-base text-neutral-100 outline-none transition focus:border-rose-500 focus:ring-2 focus:ring-rose-500/30"
            placeholder="What worked, what dragged, what confused you, what line hit, where you want more..."></textarea>
          <span data-fs-error="reader_notes" class="mt-2 block text-sm text-red-300"></span>
        </label>

        <div class="md:col-span-2 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <p class="text-xs leading-5 text-neutral-500">
            Scene metadata is included automatically so submissions stay attached to the correct page.
          </p>
          <button
            type="submit"
            data-fs-submit-btn
            class="inline-flex items-center justify-center rounded-2xl bg-rose-600 px-5 py-3 text-sm font-semibold text-neutral-50 transition hover:bg-rose-500">
            Submit notes
          </button>
        </div>
      </form>
    </section>

    <nav class="mt-8 flex items-center justify-between gap-4 border-t border-neutral-800 pt-8">
      {bottom_prev}
      {bottom_next}
    </nav>
  </main>

  <script>
    window.formspree = window.formspree || function () {{ (formspree.q = formspree.q || []).push(arguments); }};
    formspree("initForm", {{
      formElement: "#reader-note-form",
      formId: "xzdyknwz",
      onSuccess: function () {{
        const success = document.querySelector("[data-fs-success]");
        if (success) {{
          success.textContent = "Notes submitted. Thank you for the read.";
          success.classList.remove("hidden");
        }}
      }},
      onError: function () {{
        const error = document.querySelector("[data-fs-error]");
        if (error) {{
          error.textContent = "Could not submit notes right now. Please try again.";
          error.classList.remove("hidden");
        }}
      }}
    }});
  </script>
  <script src="https://unpkg.com/@formspree/ajax@1" defer></script>
</body>
</html>
"""


def render_manifest(scenes: list[SceneDoc]) -> list[dict[str, Any]]:
    return [
        {
            "slug": scene.slug,
            "title": scene.title,
            "subtitle": scene.subtitle,
            "date": format_date(scene.meta.get("date")),
            "arc": scene.meta.get("arc"),
            "chapter": scene.meta.get("chapter"),
            "scene": scene.meta.get("scene"),
            "status": scene.meta.get("status"),
            "word_count": scene.word_count,
            "excerpt": scene.excerpt[:220] if scene.excerpt else "",
        }
        for scene in scenes
    ]


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    source_files = sorted(
        [path for path in SOURCE_DIR.glob("*.md") if path.name not in SKIP_FILES],
        key=lambda p: p.name.lower(),
    )
    scenes = [build_scene_document(path) for path in source_files]
    scenes.sort(key=lambda scene: scene.order_key)

    for index, scene in enumerate(scenes):
        previous_scene = scenes[index - 1] if index > 0 else None
        next_scene = scenes[index + 1] if index + 1 < len(scenes) else None
        output_path = OUTPUT_DIR / f"{scene.slug}.html"
        output_path.write_text(render_scene_page(scene, previous_scene, next_scene), encoding="utf-8")

    MANIFEST_PATH.write_text(json.dumps(render_manifest(scenes), indent=2), encoding="utf-8")
    print(f"Generated {len(scenes)} scene pages into {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
