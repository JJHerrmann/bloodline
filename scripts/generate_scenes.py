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
CHAPTER_MANIFEST_PATH = OUTPUT_DIR / "chapters.json"
MANUAL_SUMMARIES_PATH = OUTPUT_DIR / "manual_chapter_summaries.json"
SUMMARY_PREP_DIR = OUTPUT_DIR / "summary_prep"
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
    plain_text: str
    excerpt: str
    word_count: int
    title: str
    subtitle: str | None
    order_key: tuple[int, str]


@dataclass
class ChapterDoc:
    key: str
    slug: str
    title: str
    scenes: list[SceneDoc]


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


def markdown_to_html(text: str) -> tuple[str, str, int, str]:
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
    return "\n".join(blocks), excerpt, word_count, plain_text


def strip_tags(value: str) -> str:
    return re.sub(r"<[^>]+>", "", value)


def build_scene_document(path: Path) -> SceneDoc:
    raw = path.read_text(encoding="utf-8")
    meta, body = parse_front_matter(raw)
    body_html, excerpt, word_count, plain_text = markdown_to_html(body)

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
        plain_text=plain_text,
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


def chapter_sort_key(key: str) -> tuple[int, str]:
    try:
        return (0, f"{int(key):08d}")
    except ValueError:
        return (1, key.lower())


def chapter_slug(chapter_key: str) -> str:
    if re.fullmatch(r"-?\d+", chapter_key):
        return f"chapter-{chapter_key}"
    slug = re.sub(r"[^a-z0-9]+", "-", chapter_key.lower()).strip("-")
    return f"chapter-{slug or 'unnumbered'}"


def scene_anchor(scene: SceneDoc) -> str:
    return f"scene-{scene.slug}"


def chapter_title(chapter_key: str) -> str:
    return f"Chapter {chapter_key}" if re.fullmatch(r"-?\d+", chapter_key) else chapter_key


def build_chapters(scenes: list[SceneDoc]) -> list[ChapterDoc]:
    grouped: dict[str, list[SceneDoc]] = {}
    for scene in scenes:
        key = str(scene.meta.get("chapter") or "Unnumbered")
        grouped.setdefault(key, []).append(scene)

    chapters: list[ChapterDoc] = []
    for key, items in grouped.items():
        items.sort(key=lambda item: item.order_key)
        chapters.append(ChapterDoc(key=key, slug=chapter_slug(key), title=chapter_title(key), scenes=items))

    chapters.sort(key=lambda chapter: chapter_sort_key(chapter.key))
    return chapters


def chapter_word_count(chapter: ChapterDoc) -> int:
    return sum(scene.word_count for scene in chapter.scenes)


def chapter_read_time(chapter: ChapterDoc) -> int:
    words = chapter_word_count(chapter)
    return max(1, round(words / 250))


def chapter_missing_scene_one(chapter: ChapterDoc) -> bool:
    return not any(str(scene.meta.get("scene") or "") == "1" for scene in chapter.scenes)


def chapter_scene_numbering_preserved(chapter: ChapterDoc) -> bool:
    return chapter_missing_scene_one(chapter) or any(str(scene.meta.get("scene") or "").strip() == "0" for scene in chapter.scenes)


def chapter_number(chapter_key: str) -> int | None:
    if re.fullmatch(r"-?\d+", chapter_key):
        return int(chapter_key)
    return None


def chapter_section_index(chapters: list[ChapterDoc], chapter_index: int) -> int:
    section_index = 0
    previous_number: int | None = None

    for index, chapter in enumerate(chapters):
        current_number = chapter_number(chapter.key)
        if index > 0 and current_number is not None and previous_number is not None and current_number - previous_number > 1:
            section_index += 1
        previous_number = current_number if current_number is not None else previous_number
        if index == chapter_index:
            return section_index

    return section_index


def chapter_meta_value(chapter: ChapterDoc, *keys: str) -> Any:
    for key in keys:
        lead_value = chapter.scenes[0].meta.get(key)
        if lead_value not in (None, "", []):
            return lead_value

    for scene in chapter.scenes:
        for key in keys:
            value = scene.meta.get(key)
            if value not in (None, "", []):
                return value

    return None


def chapter_updated_date(chapter: ChapterDoc) -> str | None:
    raw_dates: list[str] = []
    for scene in chapter.scenes:
        for key in ("updatedAt", "updated_at", "date"):
            raw = str(scene.meta.get(key) or "").strip()
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
                raw_dates.append(raw)
                break

    if not raw_dates:
        return None

    return max(raw_dates)


def normalize_draft_status(value: Any) -> str | None:
    if value in (None, "", []):
        return None

    normalized = str(value).strip().lower().replace("_", "-").replace(" ", "-")
    aliases = {
        "draft": "alpha",
        "alpha-draft": "alpha",
        "in-progress": "alpha",
        "needspass": "needs-pass",
        "needs-pass": "needs-pass",
        "locked": "locked-for-now",
        "locked-for-now": "locked-for-now",
    }
    return aliases.get(normalized, normalized)


def draft_status_label(value: str | None) -> str | None:
    if not value:
        return None

    labels = {
        "alpha": "Alpha",
        "partial": "Partial chapter",
        "revised": "Revised",
        "needs-pass": "Needs pass",
        "locked-for-now": "Locked for now",
    }
    return labels.get(value, value.replace("-", " ").title())


def chapter_reader_labels(chapter: ChapterDoc, detached_section: bool) -> list[str]:
    labels: list[str] = []

    if chapter.key == "0":
        labels.append("Prologue material")

    if detached_section:
        labels.append("Revised out of sequence")

    if chapter_missing_scene_one(chapter):
        labels.append("Partial chapter")

    if chapter_scene_numbering_preserved(chapter):
        labels.append("Scene numbering preserved")

    return labels


def chapter_display_excerpt(chapter: ChapterDoc) -> str:
    excerpts = [scene.excerpt.strip() for scene in chapter.scenes if scene.excerpt.strip()]
    if not excerpts:
        return "Current available draft material for this chapter is collected here for alpha reading."

    summary = " ".join(excerpts[:2]).strip()
    summary = re.sub(r"\s+", " ", summary)
    if len(summary) > 240:
        return summary[:237].rsplit(" ", 1)[0].rstrip(".,;:!?") + "..."
    return summary


def chapter_reading_order(chapter: ChapterDoc, index: int) -> int:
    chapter_num = chapter_number(chapter.key)
    return chapter_num if chapter_num is not None else index + 1


def chapter_feedback_href(chapter: ChapterDoc) -> str | None:
    explicit = chapter_meta_value(chapter, "feedbackHref", "feedback_href")
    if explicit:
        return str(explicit)
    return None


def chapter_notes_anchor(chapter: ChapterDoc) -> str | None:
    explicit = chapter_meta_value(chapter, "notesAnchor", "notes_anchor")
    if explicit:
        return str(explicit)
    return None


def chapter_manifest_item(chapter: ChapterDoc, index: int, story_so_far: str, detached_section: bool) -> dict[str, Any]:
    lead_scene = chapter.scenes[0]
    chapter_url = f"./{chapter.slug}.html"
    first_scene = chapter.scenes[0]
    draft_status = normalize_draft_status(chapter_meta_value(chapter, "draftStatus", "draft_status", "status"))
    updated_at = chapter_updated_date(chapter)

    return {
        "chapterSlug": chapter.slug,
        "chapterTitle": chapter.title,
        "chapterUrl": chapter_url,
        "storySoFar": story_so_far,
        "excerpt": chapter_display_excerpt(chapter),
        "draftStatus": draft_status,
        "draftStatusLabel": draft_status_label(draft_status),
        "spoilerThrough": chapter_meta_value(chapter, "spoilerThrough", "spoiler_through"),
        "readingOrder": chapter_reading_order(chapter, index),
        "updatedAt": format_date(updated_at) if updated_at else None,
        "updatedAtRaw": updated_at,
        "act": chapter_meta_value(chapter, "arc"),
        "wordCount": chapter_word_count(chapter),
        "sceneCount": len(chapter.scenes),
        "estimatedReadMinutes": chapter_read_time(chapter),
        "feedbackHref": chapter_feedback_href(chapter),
        "notesAnchor": chapter_notes_anchor(chapter),
        "feedbackLine": "Leave notes after scene sections",
        "readerLabels": chapter_reader_labels(chapter, detached_section),
        "detachedSection": detached_section,
        "firstScene": {
            "label": f"Scene {first_scene.meta.get('scene')}" if first_scene.meta.get("scene") else "Scene preview",
            "title": first_scene.title,
            "href": f"{chapter_url}#{scene_anchor(first_scene)}",
        },
    }


def render_json_script(data: Any) -> str:
    return json.dumps(data, indent=2).replace("</", "<\\/")


def chapter_summary(previous_scenes: list[SceneDoc]) -> str:
    excerpts = [scene.excerpt.strip() for scene in previous_scenes if scene.excerpt.strip()]
    if not excerpts:
        return "This chapter begins the currently available material, so there is no prior-story recap before this point."

    summary = " ".join(excerpts[-3:]).strip()
    summary = re.sub(r"\s+", " ", summary)
    if len(summary) > 280:
        summary = summary[:277].rsplit(" ", 1)[0].rstrip(".,;:!?") + "..."
    return summary


def load_manual_summaries() -> dict[str, str]:
    if not MANUAL_SUMMARIES_PATH.exists():
        return {}
    try:
        data = json.loads(MANUAL_SUMMARIES_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): str(value).strip() for key, value in data.items() if str(value).strip()}


def save_manual_summaries_template(chapters: list[ChapterDoc]) -> None:
    if MANUAL_SUMMARIES_PATH.exists():
        return
    template = {chapter.key: "" for chapter in chapters}
    MANUAL_SUMMARIES_PATH.write_text(json.dumps(template, indent=2), encoding="utf-8")


def build_recent_context(chapters: list[ChapterDoc], chapter_index: int, context_chapters: int = 2) -> str:
    prior_chapters = chapters[max(0, chapter_index - context_chapters):chapter_index]
    chunks: list[str] = []

    for prior in prior_chapters:
        chunks.append(f"{prior.title}")
        for scene in prior.scenes:
            scene_num = scene.meta.get("scene")
            label = f"Scene {scene_num}" if scene_num else "Scene"
            excerpt = re.sub(r"\s+", " ", scene.excerpt or "").strip()
            if len(excerpt) > 320:
                excerpt = excerpt[:317].rsplit(" ", 1)[0].rstrip(".,;:!?") + "..."
            subtitle = f" ({scene.subtitle})" if scene.subtitle else ""
            chunks.append(f"{label}: {scene.title}{subtitle}\n{excerpt}")

    return "\n\n".join(chunks)


def write_summary_prep_files(chapters: list[ChapterDoc], manual_summaries: dict[str, str]) -> None:
    SUMMARY_PREP_DIR.mkdir(parents=True, exist_ok=True)
    prompt = (
        "Write a concise \"story so far\" recap for the reader before {chapter_title} of this novel.\n\n"
        "Requirements:\n"
        "- 80 to 130 words\n"
        "- summarize only events before this chapter\n"
        "- focus on plot state, character tensions, and unresolved threads\n"
        "- preserve names, relationships, and factual details exactly\n"
        "- do not mention chapter numbers, scenes, source files, or that this is a summary\n"
        "- do not invent events\n"
        "- write in clean, reader-facing prose\n"
    )

    for index, chapter in enumerate(chapters):
        prep_lines = [
            f"# {chapter.title} Summary Prep",
            "",
            "## Status",
            f"Manual summary present: {'yes' if manual_summaries.get(chapter.key) else 'no'}",
            "",
            "## Prompt",
            prompt.format(chapter_title=chapter.title),
            "",
            "## Story So Far Source Material",
        ]
        if index == 0:
            prep_lines.append("No prior scenes exist before this chapter.")
        else:
            prep_lines.append(build_recent_context(chapters, index, context_chapters=index))
        prep_lines.extend(
            [
                "",
                "## Approved Summary",
                manual_summaries.get(chapter.key, ""),
                "",
                "## Save To",
                f'Use key "{chapter.key}" in {MANUAL_SUMMARIES_PATH.name}',
            ]
        )
        (SUMMARY_PREP_DIR / f"{chapter.slug}.md").write_text("\n".join(prep_lines), encoding="utf-8")


def build_story_so_far_summaries(chapters: list[ChapterDoc]) -> dict[str, str]:
    save_manual_summaries_template(chapters)
    manual_summaries = load_manual_summaries()
    write_summary_prep_files(chapters, manual_summaries)
    summaries: dict[str, str] = {}

    for index, chapter in enumerate(chapters):
        fallback = chapter_summary([scene for prior in chapters[:index] for scene in prior.scenes])
        summaries[chapter.key] = manual_summaries.get(chapter.key, fallback)
    return summaries


def render_scene_notes_form(scene: SceneDoc) -> str:
    scene_title_attr = html.escape(scene.title, quote=True)
    scene_slug_attr = html.escape(scene.slug, quote=True)
    return f"""
      <div data-fs-success class="hidden mt-6 rounded-2xl border border-emerald-900/60 bg-emerald-950/40 px-4 py-3 text-sm text-emerald-100"></div>
      <div data-fs-error class="hidden mt-4 rounded-2xl border border-red-900/60 bg-red-950/40 px-4 py-3 text-sm text-red-100"></div>

      <form id="reader-note-form-{scene.slug}" class="reader-note-form mt-6 grid gap-4 md:grid-cols-2" action="{NOTES_FORM_ACTION}" method="POST" data-scene-title="{scene_title_attr}">
        <input type="hidden" name="form_type" value="alpha_reader_note">
        <input type="hidden" name="scene_title" value="{scene_title_attr}">
        <input type="hidden" name="scene_slug" value="{scene_slug_attr}">

        <label class="block">
          <span class="mb-2 block text-sm font-medium text-neutral-200">Name</span>
          <input type="text" name="reader_name" required data-fs-field class="w-full rounded-2xl border border-neutral-700 bg-neutral-950 px-4 py-3 text-base text-neutral-100 outline-none transition focus:border-rose-500 focus:ring-2 focus:ring-rose-500/30" placeholder="Reader name">
          <span data-fs-error="reader_name" class="mt-2 block text-sm text-red-300"></span>
        </label>

        <label class="block">
          <span class="mb-2 block text-sm font-medium text-neutral-200">Email <span class="text-neutral-500">(optional)</span></span>
          <input type="email" name="reader_email" data-fs-field class="w-full rounded-2xl border border-neutral-700 bg-neutral-950 px-4 py-3 text-base text-neutral-100 outline-none transition focus:border-rose-500 focus:ring-2 focus:ring-rose-500/30" placeholder="reader@domain.com">
          <span data-fs-error="reader_email" class="mt-2 block text-sm text-red-300"></span>
        </label>

        <label class="block md:col-span-2">
          <span class="mb-2 block text-sm font-medium text-neutral-200">Notes</span>
          <textarea name="reader_notes" required rows="6" data-fs-field class="w-full rounded-2xl border border-neutral-700 bg-neutral-950 px-4 py-3 text-base text-neutral-100 outline-none transition focus:border-rose-500 focus:ring-2 focus:ring-rose-500/30" placeholder="What worked, what dragged, what confused you, what line hit, where you want more..."></textarea>
          <span data-fs-error="reader_notes" class="mt-2 block text-sm text-red-300"></span>
        </label>

        <div class="md:col-span-2 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <p class="text-xs leading-5 text-neutral-500">Scene metadata is included automatically so submissions stay attached to the correct section.</p>
          <button type="submit" data-fs-submit-btn class="inline-flex items-center justify-center rounded-2xl bg-rose-600 px-5 py-3 text-sm font-semibold text-neutral-50 transition hover:bg-rose-500">Submit notes</button>
        </div>
      </form>
"""


def render_scene_block(scene: SceneDoc) -> str:
    subtitle_html = (
        f'<p class="mt-2 text-lg text-rose-200">{html.escape(scene.subtitle, quote=False)}</p>' if scene.subtitle else ""
    )
    scene_label = f"Scene {scene.meta.get('scene')}" if scene.meta.get("scene") else "Scene"
    pov_list = render_list(scene.meta.get("pov"))
    location_list = render_list(scene.meta.get("locations"))
    return f"""
    <section id="{scene_anchor(scene)}" class="scroll-mt-24 rounded-3xl border border-neutral-800 bg-neutral-900/65 p-6 md:p-8">
      <div class="border-b border-neutral-800 pb-6">
        <p class="text-xs uppercase tracking-[0.24em] text-rose-300">{html.escape(scene_label, quote=False)}</p>
        <h2 class="mt-3 text-3xl font-bold tracking-tight text-neutral-50">{html.escape(scene.title, quote=False)}</h2>
        {subtitle_html}
        <div class="mt-4 flex flex-wrap gap-2">
          {render_meta_chips(scene)}
        </div>
        <p class="mt-4 text-sm text-neutral-400">Please leave comments on the scene using the form at the end of this section.</p>
      </div>

      <div class="mt-8 grid gap-6 md:grid-cols-[0.68fr_0.32fr]">
        <article>
          <div class="scene-copy">
            {scene.body_html}
          </div>
        </article>
        <aside class="space-y-6">
          <section class="rounded-3xl border border-neutral-800 bg-neutral-950/50 p-6">
            <h3 class="text-lg font-semibold text-neutral-50">Point of view</h3>
            <div class="mt-3">{pov_list or '<p class="text-sm text-neutral-400">Not specified.</p>'}</div>
          </section>
          <section class="rounded-3xl border border-neutral-800 bg-neutral-950/50 p-6">
            <h3 class="text-lg font-semibold text-neutral-50">Locations</h3>
            <div class="mt-3">{location_list or '<p class="text-sm text-neutral-400">Not specified.</p>'}</div>
          </section>
        </aside>
      </div>

      <div class="mt-8 rounded-3xl border border-neutral-800 bg-neutral-950/35 p-6">
        <div class="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div>
            <p class="text-xs uppercase tracking-[0.24em] text-rose-300">Reader Feedback</p>
            <h3 class="mt-2 text-2xl font-semibold text-neutral-50">Notes on this scene</h3>
            <p class="mt-2 max-w-2xl text-sm leading-6 text-neutral-300">Alpha readers can send reactions, line notes, continuity catches, or general impressions directly from this section.</p>
          </div>
          <p class="text-xs text-neutral-500">Submits to the current Formspree inbox.</p>
        </div>
        {render_scene_notes_form(scene)}
      </div>
    </section>
"""


def render_chapter_page(
    chapter: ChapterDoc,
    previous_chapter: ChapterDoc | None,
    next_chapter: ChapterDoc | None,
    summary: str,
    detached_section: bool = False,
) -> str:
    lead_scene = chapter.scenes[0]
    chapter_total_words = chapter_word_count(chapter)
    chapter_minutes = chapter_read_time(chapter)
    missing_scene_one = chapter_missing_scene_one(chapter)
    scene_numbering_note = chapter_scene_numbering_preserved(chapter)
    chapter_slug_value = chapter.slug
    chapter_url = f"./{chapter.slug}.html"
    summary_section_classes = (
        "rounded-3xl border border-sky-800/70 bg-sky-950/25 p-6"
        if detached_section
        else "rounded-3xl border border-neutral-800 bg-neutral-900/60 p-6"
    )
    detached_chip = (
        '<span class="rounded-full border border-sky-700/70 bg-sky-950/50 px-3 py-1 text-xs uppercase tracking-[0.18em] text-sky-200">Revised out of sequence</span>'
        if detached_section
        else ""
    )
    side_prev = (
        f"""<a href="./{previous_chapter.slug}.html" class="group fixed left-4 top-1/2 z-40 hidden -translate-y-1/2 xl:flex max-w-[13rem] items-center gap-3 rounded-2xl border border-neutral-800 bg-neutral-950/90 px-4 py-3 text-sm font-semibold text-neutral-200 shadow-2xl shadow-black/40 backdrop-blur transition hover:border-rose-800 hover:bg-neutral-900">
  <span class="text-lg text-rose-300 transition group-hover:-translate-x-1">←</span>
  <span class="min-w-0">
    <span class="block text-[11px] uppercase tracking-[0.18em] text-neutral-500">Previous Chapter</span>
    <span class="mt-1 block truncate">{html.escape(previous_chapter.title, quote=False)}</span>
  </span>
</a>"""
        if previous_chapter
        else ""
    )
    side_next = (
        f"""<a href="./{next_chapter.slug}.html" class="group fixed right-4 top-1/2 z-40 hidden -translate-y-1/2 xl:flex max-w-[13rem] items-center justify-end gap-3 rounded-2xl border border-rose-900/60 bg-rose-950/80 px-4 py-3 text-right text-sm font-semibold text-rose-100 shadow-2xl shadow-black/40 backdrop-blur transition hover:bg-rose-900">
  <span class="min-w-0">
    <span class="block text-[11px] uppercase tracking-[0.18em] text-rose-300/70">Next Chapter</span>
    <span class="mt-1 block truncate">{html.escape(next_chapter.title, quote=False)}</span>
  </span>
  <span class="text-lg transition group-hover:translate-x-1">→</span>
</a>"""
        if next_chapter
        else ""
    )
    bottom_prev = (
        f'<a href="./{previous_chapter.slug}.html" class="rounded-2xl border border-neutral-700 px-4 py-3 text-sm font-semibold text-neutral-200 transition hover:bg-neutral-900 xl:hidden">← {html.escape(previous_chapter.title, quote=False)}</a>'
        if previous_chapter
        else '<span></span>'
    )
    bottom_next = (
        f'<a href="./{next_chapter.slug}.html" class="rounded-2xl border border-rose-800 bg-rose-950/60 px-4 py-3 text-sm font-semibold text-rose-100 transition hover:bg-rose-900/80 xl:hidden">{html.escape(next_chapter.title, quote=False)} →</a>'
        if next_chapter
        else ""
    )
    scene_links = "".join(
        f'<a href="#{scene_anchor(scene)}" class="rounded-full border border-neutral-700 bg-neutral-950/60 px-3 py-2 text-xs uppercase tracking-[0.18em] text-neutral-300 transition hover:border-rose-700 hover:text-rose-200">Scene {html.escape(str(scene.meta.get("scene") or "?"), quote=False)}: {html.escape(scene.title, quote=False)}</a>'
        for scene in chapter.scenes
    )
    scene_blocks = "\n".join(render_scene_block(scene) for scene in chapter.scenes)
    page_title = html.escape(chapter.title, quote=False)
    chapter_status = normalize_draft_status(chapter_meta_value(chapter, "draftStatus", "draft_status", "status"))
    chapter_status_label = draft_status_label(chapter_status)
    updated_at = chapter_updated_date(chapter)
    updated_chip = (
        f'<span class="rounded-full border border-neutral-700 bg-neutral-950/80 px-3 py-1 text-xs uppercase tracking-[0.18em] text-neutral-300">Updated {html.escape(format_date(updated_at) or updated_at, quote=False)}</span>'
        if updated_at
        else ""
    )
    status_chip = (
        f'<span class="rounded-full border border-neutral-700 bg-neutral-950/80 px-3 py-1 text-xs uppercase tracking-[0.18em] text-neutral-300">{html.escape(chapter_status_label, quote=False)}</span>'
        if chapter_status_label
        else ""
    )
    chapter_context = render_json_script(
        {
            "chapterSlug": chapter_slug_value,
            "chapterTitle": chapter.title,
            "chapterUrl": chapter_url,
        }
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{page_title} | Bloodline Alpha</title>
  <meta name="description" content="{html.escape((lead_scene.excerpt or chapter.title)[:155])}">
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
    .resume-toast {{
      box-shadow: 0 20px 40px rgba(0, 0, 0, 0.35);
    }}
  </style>
</head>
<body class="min-h-screen bg-neutral-950 text-neutral-100 antialiased">
  <script>
    window.BloodlineAlphaAuth.requireAuth({{ redirectTo: "../alpha/index.html" }});
  </script>
  <script id="chapter-context" type="application/json">{chapter_context}</script>
  {side_prev}
  {side_next}

  <main class="mx-auto max-w-5xl px-6 py-12 md:py-16">
    <header class="border-b border-neutral-800 pb-8">
      <div class="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
        <a href="../scenes/index.html" class="rounded-2xl border border-neutral-700 px-4 py-2 text-sm font-semibold text-neutral-200 transition hover:bg-neutral-900">Chapter Index</a>
        <a href="../alpha/index.html" class="rounded-2xl border border-neutral-700 px-4 py-2 text-sm font-semibold text-neutral-200 transition hover:bg-neutral-900">Portal</a>
      </div>
      <p class="mt-6 text-xs uppercase tracking-[0.24em] text-rose-300">Bloodline Alpha Reader Portal</p>
      <h1 class="mt-3 text-4xl font-bold tracking-tight text-neutral-50 md:text-5xl">{page_title}</h1>
      <div class="mt-8 grid gap-5 lg:grid-cols-[minmax(0,1.3fr)_minmax(18rem,0.7fr)]">
        <section class="{summary_section_classes}">
          <p class="text-xs uppercase tracking-[0.18em] text-neutral-500">To This Point</p>
          <p class="mt-3 text-base leading-7 text-neutral-200">{html.escape(summary, quote=False)}</p>
          <div class="mt-5 flex flex-wrap gap-2">
            <span class="rounded-full border border-neutral-700 bg-neutral-950/80 px-3 py-1 text-xs uppercase tracking-[0.18em] text-neutral-300">{len(chapter.scenes)} scenes included</span>
            <span class="rounded-full border border-neutral-700 bg-neutral-950/80 px-3 py-1 text-xs uppercase tracking-[0.18em] text-neutral-300">{chapter_total_words} words</span>
            <span class="rounded-full border border-neutral-700 bg-neutral-950/80 px-3 py-1 text-xs uppercase tracking-[0.18em] text-neutral-300">~{chapter_minutes} min read</span>
            {f'<span class="rounded-full border border-neutral-700 bg-neutral-950/80 px-3 py-1 text-xs uppercase tracking-[0.18em] text-neutral-300">{html.escape(str(lead_scene.meta.get("arc")), quote=False)}</span>' if lead_scene.meta.get("arc") else ''}
            {f'<span class="rounded-full border border-amber-800/70 bg-amber-950/40 px-3 py-1 text-xs uppercase tracking-[0.18em] text-amber-200">Partial chapter</span>' if missing_scene_one else ''}
            {f'<span class="rounded-full border border-amber-800/70 bg-amber-950/40 px-3 py-1 text-xs uppercase tracking-[0.18em] text-amber-200">Scene numbering preserved</span>' if scene_numbering_note else ''}
            {status_chip}
            {updated_chip}
            {detached_chip}
          </div>
        </section>
        <section class="rounded-3xl border border-neutral-800 bg-neutral-950/45 p-6">
          <div class="flex items-center justify-between gap-3">
            <div>
              <p class="text-xs uppercase tracking-[0.18em] text-neutral-500">Included Scenes</p>
              <p class="mt-2 text-sm leading-6 text-neutral-300">Jump straight into a scene or scroll through the chapter in order.</p>
            </div>
          </div>
          <div class="mt-5 flex flex-wrap gap-2">
            {scene_links}
          </div>
        </section>
      </div>
    </header>

    <div class="mt-8 space-y-8">
      {scene_blocks}
    </div>

    <nav class="mt-8 flex items-center justify-between gap-4 border-t border-neutral-800 pt-8">
      {bottom_prev}
      {bottom_next}
    </nav>
  </main>

  <aside id="resume-prompt" class="resume-toast fixed bottom-4 right-4 z-50 hidden max-w-sm rounded-3xl border border-neutral-800 bg-neutral-950/95 p-5 text-sm text-neutral-200 backdrop-blur">
    <p class="text-xs uppercase tracking-[0.18em] text-rose-300">Resume reading</p>
    <p id="resume-copy" class="mt-3 leading-6 text-neutral-300">Resume where you left off?</p>
    <div class="mt-4 flex flex-col gap-3 sm:flex-row">
      <button id="resume-yes" type="button" class="inline-flex items-center justify-center rounded-2xl bg-rose-600 px-4 py-2 font-semibold text-neutral-50 transition hover:bg-rose-500">Resume</button>
      <button id="resume-no" type="button" class="inline-flex items-center justify-center rounded-2xl border border-neutral-700 px-4 py-2 font-semibold text-neutral-200 transition hover:bg-neutral-900">Start from top</button>
    </div>
  </aside>

  <script>
    window.formspree = window.formspree || function () {{ (formspree.q = formspree.q || []).push(arguments); }};
    document.querySelectorAll(".reader-note-form").forEach((form) => {{
      formspree("initForm", {{
        formElement: `#${{form.id}}`,
        formId: "xzdyknwz",
        onSuccess: function () {{
          const success = form.parentElement.querySelector("[data-fs-success]");
          if (success) {{
            success.textContent = "Notes submitted. Thank you for the read.";
            success.classList.remove("hidden");
          }}
        }},
        onError: function () {{
          const error = form.parentElement.querySelector("[data-fs-error]");
          if (error) {{
            error.textContent = "Could not submit notes right now. Please try again.";
            error.classList.remove("hidden");
          }}
        }}
      }});
    }});

    (() => {{
      const context = JSON.parse(document.getElementById("chapter-context").textContent);
      const LAST_READING_KEY = "bloodline:lastReadingPosition";
      const CHAPTER_SCROLL_PREFIX = "bloodline:chapterScroll:";
      const CHAPTER_STATE_PREFIX = "bloodline:chapterState:";
      const RESUME_PARAM = "resume";
      const resumePrompt = document.getElementById("resume-prompt");
      const resumeCopy = document.getElementById("resume-copy");
      const resumeYes = document.getElementById("resume-yes");
      const resumeNo = document.getElementById("resume-no");
      let pendingRecord = null;
      let saveTimer = null;

      function readJson(key) {{
        try {{
          const raw = localStorage.getItem(key);
          return raw ? JSON.parse(raw) : null;
        }} catch (error) {{
          return null;
        }}
      }}

      function writeJson(key, value) {{
        localStorage.setItem(key, JSON.stringify(value));
      }}

      function chapterScrollKey(slug) {{
        return `${{CHAPTER_SCROLL_PREFIX}}${{slug}}`;
      }}

      function chapterStateKey(slug) {{
        return `${{CHAPTER_STATE_PREFIX}}${{slug}}`;
      }}

      function clamp(value, min, max) {{
        return Math.min(max, Math.max(min, value));
      }}

      function getMaxScroll() {{
        return Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
      }}

      function getScrollSnapshot() {{
        const maxScroll = getMaxScroll();
        const scrollY = clamp(window.scrollY, 0, maxScroll);
        const scrollPercent = maxScroll > 0 ? clamp((scrollY / maxScroll) * 100, 0, 100) : 0;

        return {{
          chapterSlug: context.chapterSlug,
          chapterTitle: context.chapterTitle,
          chapterUrl: context.chapterUrl,
          scrollY: Math.round(scrollY),
          scrollPercent: Math.round(scrollPercent),
          updatedAt: new Date().toISOString(),
        }};
      }}

      function markInProgress(updatedAt) {{
        const key = chapterStateKey(context.chapterSlug);
        const existing = readJson(key) || {{
          chapterSlug: context.chapterSlug,
          status: "not-started",
          openedAt: null,
          markedReadAt: null,
        }};

        if (existing.status !== "read") {{
          existing.status = "in-progress";
          existing.openedAt = existing.openedAt || updatedAt;
          writeJson(key, existing);
        }}
      }}

      function saveReadingPosition() {{
        const snapshot = getScrollSnapshot();
        writeJson(chapterScrollKey(context.chapterSlug), snapshot);
        writeJson(LAST_READING_KEY, snapshot);
        markInProgress(snapshot.updatedAt);
      }}

      function scheduleSave() {{
        if (saveTimer) return;
        saveTimer = window.setTimeout(() => {{
          saveTimer = null;
          saveReadingPosition();
        }}, 700);
      }}

      function restoreFromRecord(record) {{
        const applyRestore = () => {{
          const maxScroll = getMaxScroll();
          const restoredY = typeof record.scrollPercent === "number"
            ? maxScroll * (record.scrollPercent / 100)
            : Number(record.scrollY || 0);
          window.scrollTo({{ top: clamp(restoredY, 0, maxScroll), behavior: "auto" }});
        }};

        requestAnimationFrame(() => {{
          window.setTimeout(applyRestore, 160);
        }});
      }}

      function dismissPrompt() {{
        resumePrompt.classList.add("hidden");
      }}

      function maybeOfferResume() {{
        const record = readJson(chapterScrollKey(context.chapterSlug));
        if (!record) return;
        if (typeof record.scrollPercent === "number" && record.scrollPercent < 4) return;

        const params = new URLSearchParams(window.location.search);
        if (params.get(RESUME_PARAM) === "1") {{
          restoreFromRecord(record);
          dismissPrompt();
          return;
        }}

        pendingRecord = record;
        resumeCopy.textContent = `Resume at about ${{Math.round(record.scrollPercent || 0)}}%?`;
        resumePrompt.classList.remove("hidden");
      }}

      resumeYes.addEventListener("click", () => {{
        if (pendingRecord) {{
          restoreFromRecord(pendingRecord);
        }}
        dismissPrompt();
      }});

      resumeNo.addEventListener("click", () => {{
        const resetRecord = {{
          ...getScrollSnapshot(),
          scrollY: 0,
          scrollPercent: 0,
        }};
        writeJson(chapterScrollKey(context.chapterSlug), resetRecord);
        writeJson(LAST_READING_KEY, resetRecord);
        dismissPrompt();
        window.scrollTo({{ top: 0, behavior: "auto" }});
      }});

      window.addEventListener("scroll", scheduleSave, {{ passive: true }});
      window.addEventListener("pagehide", saveReadingPosition);
      window.addEventListener("beforeunload", saveReadingPosition);

      document.addEventListener("DOMContentLoaded", () => {{
        markInProgress(new Date().toISOString());
        maybeOfferResume();
      }});
    }})();
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
            "href": f"./{chapter_slug(str(scene.meta.get('chapter') or 'Unnumbered'))}.html#{scene_anchor(scene)}",
        }
        for scene in scenes
    ]


def render_chapter_manifest(chapters: list[ChapterDoc], chapter_summaries: dict[str, str]) -> list[dict[str, Any]]:
    return [
        chapter_manifest_item(
            chapter,
            index,
            chapter_summaries.get(chapter.key, ""),
            chapter_section_index(chapters, index) > 0,
        )
        for index, chapter in enumerate(chapters)
    ]


def render_index_page(chapter_manifest: list[dict[str, Any]]) -> str:
    chapter_json = render_json_script(chapter_manifest)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Chapter Index | Bloodline Alpha</title>
  <meta name="description" content="Alpha-reader chapter index for Bloodline.">
  <meta name="robots" content="noindex,nofollow,noarchive,noimageindex">
  <meta name="theme-color" content="#111827">
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="../alpha/auth.js"></script>
</head>
<body class="min-h-screen bg-neutral-950 text-neutral-100 antialiased">
  <script>
    window.BloodlineAlphaAuth.requireAuth({{ redirectTo: "../alpha/index.html" }});
  </script>
  <script id="chapter-manifest" type="application/json">{chapter_json}</script>

  <main class="mx-auto max-w-6xl px-6 py-12 md:py-16">
    <div class="flex flex-col gap-6 border-b border-neutral-800 pb-8 md:flex-row md:items-end md:justify-between">
      <div>
        <p class="text-xs uppercase tracking-[0.24em] text-rose-300">Bloodline Alpha Reader Portal</p>
        <h1 class="mt-3 text-4xl font-bold tracking-tight text-neutral-50">Alpha reader repo</h1>
        <p class="mt-3 max-w-3xl text-sm leading-6 text-neutral-300">
          Controlled reading hub for the current chapter draft. Use it to move through the manuscript in order, track where you left off, and leave notes where the pages ask for them.
        </p>
      </div>
      <div class="flex flex-col gap-3 sm:flex-row">
        <a href="../alpha/index.html" class="rounded-2xl border border-neutral-700 px-4 py-3 text-sm font-semibold text-neutral-200 transition hover:bg-neutral-900">
          Portal
        </a>
        <button id="sign-out" type="button" class="rounded-2xl bg-rose-600 px-4 py-3 text-sm font-semibold text-neutral-50 transition hover:bg-rose-500">
          Sign out
        </button>
      </div>
    </div>

    <section class="mt-8 rounded-3xl border border-neutral-800 bg-neutral-900/70 p-6">
      <div class="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div class="min-w-0">
          <p class="text-xs uppercase tracking-[0.18em] text-rose-300">How to read</p>
          <h2 class="mt-3 text-2xl font-semibold text-neutral-50">Reader workflow</h2>
          <p class="mt-3 max-w-3xl text-sm leading-6 text-neutral-300">
            Start with the first available chapter unless a card says otherwise. Read in chapter order. Leave notes at the end of each scene section. Flag confusion, pacing drag, continuity issues, emotional impact, and places where more or less detail is needed.
          </p>
        </div>
        <div class="rounded-2xl border border-neutral-800 bg-neutral-950/60 px-4 py-3 text-xs uppercase tracking-[0.18em] text-neutral-400">
          Mission mode: alpha read
        </div>
      </div>
    </section>

    <section id="continue-reading-module" class="mt-6 rounded-3xl border border-rose-900/60 bg-rose-950/30 p-6">
      <div class="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <p class="text-xs uppercase tracking-[0.18em] text-rose-300">Continue reading</p>
          <h2 id="continue-title" class="mt-2 text-2xl font-semibold text-neutral-50">Loading reading position...</h2>
          <p id="continue-copy" class="mt-2 text-sm leading-6 text-neutral-300">Checking the last chapter you opened.</p>
          <p id="continue-meta" class="mt-3 text-xs uppercase tracking-[0.18em] text-neutral-500"></p>
        </div>
        <a id="continue-link" href="./chapter-0.html?resume=1" class="inline-flex items-center justify-center rounded-2xl bg-rose-600 px-5 py-3 text-sm font-semibold text-neutral-50 transition hover:bg-rose-500">
          Continue reading
        </a>
      </div>
    </section>

    <section class="mt-10 grid gap-5 lg:grid-cols-[minmax(0,1.45fr)_minmax(18rem,0.55fr)]">
      <article class="rounded-3xl border border-neutral-800 bg-neutral-900/70 p-6">
        <div class="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 class="text-xl font-semibold text-neutral-50">Chapter shelf</h2>
            <p class="mt-2 text-sm leading-6 text-neutral-400">
              Follow the draft in order, keep track of what is in progress, and mark finished chapters once you are done.
            </p>
          </div>
        </div>
        <div id="chapter-list" class="mt-6 space-y-4">
          <div class="rounded-2xl border border-dashed border-neutral-700 bg-neutral-950/60 p-5">
            <p class="text-sm font-medium text-neutral-100">Loading chapter shelf...</p>
            <p class="mt-2 text-sm leading-6 text-neutral-400">
              If this stays here, the generated chapter manifest is missing or unreadable.
            </p>
          </div>
        </div>
      </article>

      <aside class="rounded-3xl border border-neutral-800 bg-neutral-900/70 p-6">
        <h2 class="text-xl font-semibold text-neutral-50">Reader briefing</h2>
        <p class="mt-4 text-sm leading-6 text-neutral-300">
          Bloodline: Spirits of the Smokies is currently organized by chapter for alpha reading. Some chapters are partial, revised out of sequence, or preserve older scene numbering while the manuscript is being assembled.
        </p>
        <ul class="mt-5 space-y-3 text-sm leading-6 text-neutral-300">
          <li>Read in chapter order.</li>
          <li>Leave notes at scene breaks.</li>
          <li>Flag confusion immediately.</li>
          <li>Call out pacing, emotional impact, continuity snags, and missing context.</li>
        </ul>
        <div class="mt-6 rounded-2xl border border-neutral-800 bg-neutral-950/60 px-4 py-3 text-xs uppercase tracking-[0.18em] text-neutral-400">
          Current repo mode: Alpha draft
        </div>
      </aside>
    </section>
  </main>

  <script>
    (() => {{
      const chapterManifest = JSON.parse(document.getElementById("chapter-manifest").textContent);
      const LAST_READING_KEY = "bloodline:lastReadingPosition";
      const CHAPTER_STATE_PREFIX = "bloodline:chapterState:";
      const formatter = new Intl.DateTimeFormat("en-US", {{ month: "short", day: "numeric", year: "numeric" }});

      const chapterList = document.getElementById("chapter-list");
      const continueTitle = document.getElementById("continue-title");
      const continueCopy = document.getElementById("continue-copy");
      const continueMeta = document.getElementById("continue-meta");
      const continueLink = document.getElementById("continue-link");

      document.getElementById("sign-out").addEventListener("click", () => {{
        window.BloodlineAlphaAuth.signOut();
        window.location.replace("../alpha/index.html");
      }});

      function readJson(key) {{
        try {{
          const raw = localStorage.getItem(key);
          return raw ? JSON.parse(raw) : null;
        }} catch (error) {{
          return null;
        }}
      }}

      function writeJson(key, value) {{
        localStorage.setItem(key, JSON.stringify(value));
      }}

      function chapterStateKey(slug) {{
        return `${{CHAPTER_STATE_PREFIX}}${{slug}}`;
      }}

      function getChapterState(slug) {{
        return readJson(chapterStateKey(slug));
      }}

      function setChapterState(chapter, status) {{
        const existing = getChapterState(chapter.chapterSlug) || {{
          chapterSlug: chapter.chapterSlug,
          status: "not-started",
          openedAt: null,
          markedReadAt: null,
        }};
        const now = new Date().toISOString();
        existing.chapterSlug = chapter.chapterSlug;
        existing.status = status;
        if (status === "not-started") {{
          existing.openedAt = null;
          existing.markedReadAt = null;
        }} else {{
          existing.openedAt = existing.openedAt || now;
          existing.markedReadAt = status === "read" ? (existing.markedReadAt || now) : null;
        }}
        writeJson(chapterStateKey(chapter.chapterSlug), existing);
      }}

      function markOpened(chapter) {{
        const existing = getChapterState(chapter.chapterSlug);
        if (existing?.status === "read") return;
        setChapterState(chapter, "in-progress");
      }}

      function formatDate(value) {{
        if (!value) return "";
        try {{
          return formatter.format(new Date(value));
        }} catch (error) {{
          return "";
        }}
      }}

      function statusBadge(status) {{
        const labels = {{
          "read": ["Read", "border-emerald-900/60 bg-emerald-950/40 text-emerald-100"],
          "in-progress": ["In progress", "border-amber-800/60 bg-amber-950/40 text-amber-100"],
          "not-started": ["Not started", "border-neutral-700 bg-neutral-950/80 text-neutral-300"],
        }};
        const [label, classes] = labels[status] || labels["not-started"];
        return `<span class="rounded-full border px-3 py-1 text-[11px] uppercase tracking-[0.18em] ${{classes}}">${{label}}</span>`;
      }}

      function currentStatus(chapter) {{
        const state = getChapterState(chapter.chapterSlug);
        return state?.status || "not-started";
      }}

      function continueTarget() {{
        const last = readJson(LAST_READING_KEY);
        if (last?.chapterSlug) {{
          const chapter = chapterManifest.find((entry) => entry.chapterSlug === last.chapterSlug);
          if (chapter) {{
            return {{
              chapter,
              position: last,
              mode: "resume",
            }};
          }}
        }}

        return {{
          chapter: chapterManifest[0],
          position: null,
          mode: "start",
        }};
      }}

      function renderContinueReading() {{
        const target = continueTarget();
        if (!target.chapter) {{
          continueTitle.textContent = "No chapter pages available yet";
          continueCopy.textContent = "Run the generator to populate the alpha reader repo.";
          continueMeta.textContent = "";
          continueLink.classList.add("pointer-events-none", "opacity-50");
          continueLink.href = "#";
          return;
        }}

        continueTitle.textContent = `Continue reading: ${{target.chapter.chapterTitle}}`;
        continueLink.href = target.mode === "resume"
          ? `${{target.chapter.chapterUrl}}?resume=1`
          : target.chapter.chapterUrl;

        if (target.mode === "resume" && target.position) {{
          continueCopy.textContent = `Last position: about ${{Math.round(target.position.scrollPercent || 0)}}%`;
          const parts = [];
          if (target.position.updatedAt) {{
            parts.push(`Last opened ${{formatDate(target.position.updatedAt)}}`);
          }}
          continueMeta.textContent = parts.join(" • ");
          continueLink.textContent = "Continue reading";
        }} else {{
          continueCopy.textContent = "No saved position yet. Start with the first available chapter.";
          continueMeta.textContent = "";
          continueLink.textContent = "Start reading";
        }}
      }}

      function chapterCard(chapter, index) {{
        const status = currentStatus(chapter);
        const readerLabels = Array.isArray(chapter.readerLabels) ? chapter.readerLabels : [];
        const metaChips = [
          chapter.act ? `<span class="rounded-full border border-neutral-700 bg-neutral-950/80 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-neutral-300">${{chapter.act}}</span>` : "",
          chapter.updatedAt ? `<span class="rounded-full border border-neutral-700 bg-neutral-950/80 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-neutral-300">Updated ${{chapter.updatedAt}}</span>` : "",
          `<span class="rounded-full border border-neutral-700 bg-neutral-950/80 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-neutral-300">${{chapter.sceneCount}} scene${{chapter.sceneCount === 1 ? "" : "s"}}</span>`,
          `<span class="rounded-full border border-neutral-700 bg-neutral-950/80 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-neutral-300">${{chapter.wordCount}} words</span>`,
          `<span class="rounded-full border border-neutral-700 bg-neutral-950/80 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-neutral-300">~${{chapter.estimatedReadMinutes}} min read</span>`,
          chapter.draftStatusLabel ? `<span class="rounded-full border border-neutral-700 bg-neutral-950/80 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-neutral-300">${{chapter.draftStatusLabel}}</span>` : "",
          statusBadge(status),
        ].filter(Boolean).join("");

        const readerFlags = readerLabels
          .map((label) => `<span class="rounded-full border border-sky-800/60 bg-sky-950/35 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-sky-100">${{label}}</span>`)
          .join("");

        return `
          <article class="rounded-3xl border border-neutral-800 bg-neutral-950/35 p-5">
            <div class="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
              <div class="min-w-0">
                <div class="flex flex-wrap items-center gap-2">
                  <p class="text-xs uppercase tracking-[0.18em] text-neutral-500">Reading order ${{index + 1}}</p>
                  ${{readerFlags}}
                </div>
                <h3 class="mt-3 text-xl font-semibold text-neutral-50">${{chapter.chapterTitle}}</h3>
                <p class="mt-3 max-w-3xl text-sm leading-6 text-neutral-300">${{chapter.excerpt}}</p>
                <div class="mt-4 flex flex-wrap gap-2">${{metaChips}}</div>
                <div class="mt-4 rounded-2xl border border-neutral-800 bg-neutral-950/60 px-4 py-3">
                  <p class="text-[11px] uppercase tracking-[0.18em] text-neutral-500">Scene preview</p>
                  <p class="mt-2 text-sm font-medium text-neutral-100">${{chapter.firstScene.label}}: ${{chapter.firstScene.title}}</p>
                  <p class="mt-2 text-sm text-neutral-400">${{chapter.feedbackLine}}</p>
                </div>
              </div>
              <div class="flex w-full flex-col gap-3 md:w-auto md:min-w-[12rem]">
                <a href="${{chapter.chapterUrl}}" data-open-chapter="${{chapter.chapterSlug}}" class="inline-flex items-center justify-center rounded-2xl bg-rose-600 px-4 py-3 text-sm font-semibold text-neutral-50 transition hover:bg-rose-500">
                  Open chapter
                </a>
                <button type="button" data-mark-read="${{chapter.chapterSlug}}" class="inline-flex items-center justify-center rounded-2xl border border-neutral-700 px-4 py-3 text-sm font-semibold text-neutral-200 transition hover:bg-neutral-900">
                  ${{status === "read" ? "Mark unread" : "Mark read"}}
                </button>
              </div>
            </div>
          </article>
        `;
      }}

      function renderChapterList() {{
        if (!chapterManifest.length) {{
          chapterList.innerHTML = `
            <div class="rounded-2xl border border-dashed border-neutral-700 bg-neutral-950/60 p-5">
              <p class="text-sm font-medium text-neutral-100">No chapter pages available yet.</p>
              <p class="mt-2 text-sm leading-6 text-neutral-400">Run the scene generator to populate this portal index.</p>
            </div>
          `;
          return;
        }}

        chapterList.innerHTML = chapterManifest.map(chapterCard).join("");

        chapterList.querySelectorAll("[data-open-chapter]").forEach((link) => {{
          link.addEventListener("click", () => {{
            const slug = link.getAttribute("data-open-chapter");
            const chapter = chapterManifest.find((entry) => entry.chapterSlug === slug);
            if (chapter) {{
              markOpened(chapter);
            }}
          }});
        }});

        chapterList.querySelectorAll("[data-mark-read]").forEach((button) => {{
          button.addEventListener("click", () => {{
            const slug = button.getAttribute("data-mark-read");
            const chapter = chapterManifest.find((entry) => entry.chapterSlug === slug);
            if (!chapter) return;
            const status = currentStatus(chapter);
            setChapterState(chapter, status === "read" ? "not-started" : "read");
            renderContinueReading();
            renderChapterList();
          }});
        }});
      }}

      renderContinueReading();
      renderChapterList();
    }})();
  </script>
</body>
</html>
"""


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    source_files = sorted(
        [path for path in SOURCE_DIR.glob("*.md") if path.name not in SKIP_FILES],
        key=lambda p: p.name.lower(),
    )
    scenes = [build_scene_document(path) for path in source_files]
    scenes.sort(key=lambda scene: scene.order_key)

    chapters = build_chapters(scenes)
    chapter_summaries = build_story_so_far_summaries(chapters)
    chapter_manifest = render_chapter_manifest(chapters, chapter_summaries)

    keep_html = {"index.html"}
    for index, chapter in enumerate(chapters):
        previous_chapter = chapters[index - 1] if index > 0 else None
        next_chapter = chapters[index + 1] if index + 1 < len(chapters) else None
        detached_section = chapter_section_index(chapters, index) > 0
        output_name = f"{chapter.slug}.html"
        keep_html.add(output_name)
        output_path = OUTPUT_DIR / output_name
        output_path.write_text(
            render_chapter_page(
                chapter,
                previous_chapter,
                next_chapter,
                chapter_summaries.get(chapter.key, chapter_summary([scene for prior in chapters[:index] for scene in prior.scenes])),
                detached_section=detached_section,
            ),
            encoding="utf-8",
        )

    (OUTPUT_DIR / "index.html").write_text(render_index_page(chapter_manifest), encoding="utf-8")

    for existing in OUTPUT_DIR.glob("*.html"):
        if existing.name not in keep_html:
            existing.unlink()

    MANIFEST_PATH.write_text(json.dumps(render_manifest(scenes), indent=2), encoding="utf-8")
    CHAPTER_MANIFEST_PATH.write_text(json.dumps(chapter_manifest, indent=2), encoding="utf-8")
    print(f"Generated {len(chapters)} chapter pages from {len(scenes)} scenes into {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
