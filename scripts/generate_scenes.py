from __future__ import annotations

import html
import json
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
# The repository lives beside the canonical Obsidian manuscript inside the
# Bloodline folder. Keep prose in the vault and generated reader pages here.
DEFAULT_SOURCE_DIR = REPO_ROOT.parent / "Garnet Shield" / "Writing" / "Episodes"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "scenes"

SOURCE_DIR = Path(os.environ.get("BLOODLINE_SOURCE_DIR", str(DEFAULT_SOURCE_DIR)))
OUTPUT_DIR = Path(os.environ.get("BLOODLINE_OUTPUT_DIR", str(DEFAULT_OUTPUT_DIR)))
MANIFEST_PATH = OUTPUT_DIR / "episodes.json"
LEGACY_MANIFEST_PATH = OUTPUT_DIR / "chapters.json"
LEGACY_SOURCE_MANIFEST_PATH = OUTPUT_DIR / "scenes.json"
NOTES_FORM_ACTION = "https://formspree.io/f/xzdyknwz"

LAUNCH_PLAN = {
    0: "live",
    1: "live",
    2: "week-ahead",
}

SKIP_FILES = {
    "Episodes.md",
    "Episode 1-Gjallergrisnir.md",
}
WIKI_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
EMPHASIS_RE = re.compile(r"(\*|_)([^*_]+)\1")
EPISODE_FILE_RE = re.compile(r"^Episode\s+(\d+)\.md$", re.IGNORECASE)


@dataclass
class EpisodeDoc:
    number: int
    slug: str
    title: str
    source_name: str
    body_html: str
    plain_text: str
    excerpt: str
    word_count: int
    section_count: int
    updated_at: str
    updated_at_raw: str
    release_state: str


def normalize_wiki_links(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        inner = match.group(1).strip()
        if "|" in inner:
            return inner.split("|")[-1].strip()
        return inner

    return WIKI_LINK_RE.sub(repl, text)


def strip_obsidian_artifacts(text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        try:
            closing_index = next(
                index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"
            )
            lines = lines[closing_index + 1 :]
        except StopIteration:
            pass
    kept: list[str] = []
    in_code = False
    code_lang = ""

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            marker = stripped[3:].strip().lower()
            if not in_code:
                in_code = True
                code_lang = marker
                if code_lang in {"dataviewjs", "dataview"}:
                    continue
                kept.append(line)
                continue

            if code_lang in {"dataviewjs", "dataview"}:
                in_code = False
                code_lang = ""
                continue

            kept.append(line)
            in_code = False
            code_lang = ""
            continue

        if in_code and code_lang in {"dataviewjs", "dataview"}:
            continue

        kept.append(line)

    return "\n".join(kept).strip()


def render_inline(text: str) -> str:
    text = normalize_wiki_links(text)
    escaped = html.escape(text, quote=False)
    return EMPHASIS_RE.sub(lambda match: f"<em>{match.group(2)}</em>", escaped)


def normalize_plain_text(text: str) -> str:
    text = normalize_wiki_links(text)
    text = re.sub(r"(\*|_)([^*_]+)\1", r"\2", text)
    return text.strip()


def markdown_to_html(text: str) -> tuple[str, str, int, str, int]:
    lines = strip_obsidian_artifacts(text).splitlines()
    blocks: list[str] = []
    paragraph: list[str] = []
    excerpt = ""
    section_count = 1 if any(line.strip() for line in lines) else 0
    in_code = False
    code_lines: list[str] = []

    def flush_paragraph() -> None:
        nonlocal excerpt
        if not paragraph:
            return
        raw = " ".join(part.strip() for part in paragraph if part.strip()).strip()
        paragraph.clear()
        if not raw:
            return
        raw = normalize_plain_text(raw)
        blocks.append(f"<p>{render_inline(raw)}</p>")
        if not excerpt:
            excerpt = raw

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()

        if stripped.startswith("```"):
            if in_code:
                code_html = html.escape("\n".join(code_lines))
                blocks.append(
                    '<pre class="overflow-x-auto rounded-2xl border border-neutral-800 bg-neutral-950/80 p-4 text-sm text-neutral-200"><code>'
                    f"{code_html}</code></pre>"
                )
                code_lines = []
                in_code = False
            else:
                flush_paragraph()
                in_code = True
            continue

        if in_code:
            code_lines.append(raw_line)
            continue

        if stripped == "---":
            flush_paragraph()
            blocks.append('<hr class="my-10 border-neutral-800">')
            section_count += 1
            continue

        if not stripped:
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
    plain_text = re.sub(r"\s+", " ", normalize_plain_text(re.sub(r"<[^>]+>", "", " ".join(blocks)))).strip()
    word_count = len(plain_text.split()) if plain_text else 0
    return "\n".join(blocks), excerpt, word_count, plain_text, section_count


def format_date_for_page(path: Path) -> tuple[str, str]:
    stamp = path.stat().st_mtime
    dt = Path
    from datetime import datetime

    value = datetime.fromtimestamp(stamp)
    return value.strftime("%B %d, %Y"), value.strftime("%Y-%m-%d")


def episode_sort_key(path: Path) -> tuple[int, str]:
    match = EPISODE_FILE_RE.match(path.name)
    return (int(match.group(1)) if match else 999999, path.name.lower())


def build_episode_document(path: Path) -> EpisodeDoc | None:
    match = EPISODE_FILE_RE.match(path.name)
    if not match:
        return None

    number = int(match.group(1))
    if number not in LAUNCH_PLAN:
        return None

    raw = path.read_text(encoding="utf-8")
    body_html, excerpt, word_count, plain_text, section_count = markdown_to_html(raw)
    updated_at, updated_at_raw = format_date_for_page(path)

    return EpisodeDoc(
        number=number,
        slug=f"episode-{number}",
        title=f"Episode {number}",
        source_name=path.name,
        body_html=body_html,
        plain_text=plain_text,
        excerpt=excerpt or "Current episode draft material is collected here for alpha reading.",
        word_count=word_count,
        section_count=section_count,
        updated_at=updated_at,
        updated_at_raw=updated_at_raw,
        release_state=LAUNCH_PLAN[number],
    )


def render_json_script(value: object) -> str:
    return html.escape(json.dumps(value, ensure_ascii=False, indent=2), quote=False)


def estimate_read_minutes(word_count: int) -> int:
    return max(1, math.ceil(word_count / 250))


def release_label(state: str) -> str:
    labels = {
        "live": "Launch Week",
        "week-ahead": "Week Ahead",
    }
    return labels.get(state, state.replace("-", " ").title())


def release_badge_classes(state: str) -> str:
    classes = {
        "live": "border-emerald-900/60 bg-emerald-950/40 text-emerald-100",
        "week-ahead": "border-sky-900/60 bg-sky-950/40 text-sky-100",
    }
    return classes.get(state, "border-neutral-700 bg-neutral-950/80 text-neutral-300")


def render_episode_manifest(episodes: list[EpisodeDoc]) -> list[dict[str, object]]:
    manifest: list[dict[str, object]] = []
    for episode in episodes:
        manifest.append(
            {
                "episodeSlug": episode.slug,
                "episodeTitle": episode.title,
                "episodeUrl": f"./{episode.slug}.html",
                "episodeNumber": episode.number,
                "excerpt": text_excerpt(episode.excerpt),
                "updatedAt": episode.updated_at,
                "updatedAtRaw": episode.updated_at_raw,
                "wordCount": episode.word_count,
                "sectionCount": episode.section_count,
                "estimatedReadMinutes": estimate_read_minutes(episode.word_count),
                "releaseState": episode.release_state,
                "releaseLabel": release_label(episode.release_state),
                "releaseDescription": (
                    "Available now for launch week readers."
                    if episode.release_state == "live"
                    else "Next week’s episode is visible here for readers staying one week ahead."
                ),
            }
        )
    return manifest


def text_excerpt(value: str, limit: int = 240) -> str:
    clean = re.sub(r"\s+", " ", value).strip()
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3].rstrip() + "..."


def render_feedback_form(episode: EpisodeDoc) -> str:
    return f"""
      <div data-fs-success class="hidden mt-6 rounded-2xl border border-emerald-900/60 bg-emerald-950/40 px-4 py-3 text-sm text-emerald-100"></div>
      <div data-fs-error class="hidden mt-4 rounded-2xl border border-red-900/60 bg-red-950/40 px-4 py-3 text-sm text-red-100"></div>

      <form id="reader-note-form-{episode.slug}" class="reader-note-form mt-6 grid gap-4 md:grid-cols-2" action="{NOTES_FORM_ACTION}" method="POST" data-episode-title="{html.escape(episode.title, quote=True)}">
        <input type="hidden" name="form_type" value="alpha_reader_note">
        <input type="hidden" name="episode_title" value="{html.escape(episode.title, quote=True)}">
        <input type="hidden" name="episode_slug" value="{html.escape(episode.slug, quote=True)}">
        <input type="hidden" name="episode_number" value="{episode.number}">

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
          <textarea name="reader_notes" required rows="6" data-fs-field class="w-full rounded-2xl border border-neutral-700 bg-neutral-950 px-4 py-3 text-base text-neutral-100 outline-none transition focus:border-rose-500 focus:ring-2 focus:ring-rose-500/30" placeholder="What worked, what dragged, what confused you, and what hit hardest?"></textarea>
          <span data-fs-error="reader_notes" class="mt-2 block text-sm text-red-300"></span>
        </label>

        <div class="md:col-span-2 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <p class="text-xs leading-5 text-neutral-500">Episode metadata is attached automatically so each note stays tied to the right release.</p>
          <button type="submit" data-fs-submit-btn class="inline-flex items-center justify-center rounded-2xl bg-rose-600 px-5 py-3 text-sm font-semibold text-neutral-50 transition hover:bg-rose-500">Submit notes</button>
        </div>
      </form>
    """


def render_episode_page(episode: EpisodeDoc, previous_episode: EpisodeDoc | None, next_episode: EpisodeDoc | None) -> str:
    previous_link = (
        f'<a href="./{previous_episode.slug}.html" class="group fixed left-4 top-1/2 z-40 hidden -translate-y-1/2 xl:flex max-w-[13rem] items-center gap-3 rounded-2xl border border-neutral-800 bg-neutral-950/90 px-4 py-3 text-sm font-semibold text-neutral-200 shadow-2xl shadow-black/40 backdrop-blur transition hover:border-rose-800 hover:bg-neutral-900"><span class="text-lg transition group-hover:-translate-x-1">←</span><span class="min-w-0"><span class="block text-[11px] uppercase tracking-[0.18em] text-neutral-500">Previous Episode</span><span class="mt-1 block truncate">{html.escape(previous_episode.title, quote=False)}</span></span></a>'
        if previous_episode
        else ""
    )
    next_link = (
        f'<a href="./{next_episode.slug}.html" class="group fixed right-4 top-1/2 z-40 hidden -translate-y-1/2 xl:flex max-w-[13rem] items-center justify-end gap-3 rounded-2xl border border-rose-900/60 bg-rose-950/80 px-4 py-3 text-right text-sm font-semibold text-rose-100 shadow-2xl shadow-black/40 backdrop-blur transition hover:bg-rose-900"><span class="min-w-0"><span class="block text-[11px] uppercase tracking-[0.18em] text-rose-300/70">Next Episode</span><span class="mt-1 block truncate">{html.escape(next_episode.title, quote=False)}</span></span><span class="text-lg transition group-hover:translate-x-1">→</span></a>'
        if next_episode
        else ""
    )
    previous_nav = (
        f'<a href="./{previous_episode.slug}.html" class="rounded-2xl border border-neutral-700 px-4 py-3 text-sm font-semibold text-neutral-200 transition hover:bg-neutral-900 xl:hidden">← {html.escape(previous_episode.title, quote=False)}</a>'
        if previous_episode
        else "<span></span>"
    )
    next_nav = (
        f'<a href="./{next_episode.slug}.html" class="rounded-2xl border border-rose-800 bg-rose-950/60 px-4 py-3 text-sm font-semibold text-rose-100 transition hover:bg-rose-900/80 xl:hidden">{html.escape(next_episode.title, quote=False)} →</a>'
        if next_episode
        else "<span></span>"
    )
    badge = f'<span class="rounded-full border px-3 py-1 text-xs uppercase tracking-[0.18em] {release_badge_classes(episode.release_state)}">{html.escape(release_label(episode.release_state), quote=False)}</span>'
    episode_context = render_json_script(
        {
            "episodeSlug": episode.slug,
            "episodeTitle": episode.title,
            "episodeUrl": f"./{episode.slug}.html",
        }
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(episode.title, quote=False)} | Bloodline Alpha</title>
  <meta name="description" content="{html.escape(text_excerpt(episode.excerpt, 155), quote=True)}">
  <meta name="robots" content="noindex,nofollow,noarchive,noimageindex">
  <meta name="theme-color" content="#111827">
  <link rel="icon" type="image/x-icon" href="../favicon.ico">
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="../alpha/auth.js"></script>
  <style>
    .episode-copy h1, .episode-copy h2 {{
      color: #fff7ed;
      font-weight: 700;
      line-height: 1.2;
    }}
    .episode-copy h1 {{ font-size: 1.6rem; margin-top: 2rem; }}
    .episode-copy h2 {{ font-size: 1.35rem; margin-top: 2rem; }}
    .episode-copy p {{
      margin-top: 1rem;
      color: rgb(229 229 229);
      line-height: 1.9;
      font-size: 1.05rem;
    }}
    .episode-copy pre {{
      margin-top: 1.5rem;
      white-space: pre-wrap;
    }}
    .resume-toast {{
      box-shadow: 0 20px 40px rgba(0, 0, 0, 0.35);
    }}
  </style>
</head>
<body class="min-h-screen bg-neutral-950 text-neutral-100 antialiased">
  <script>
    window.BloodlineAlphaAuth.requireAuth({{ redirectTo: "../alpha/index.html" }});
  </script>
  <script id="episode-context" type="application/json">{episode_context}</script>
  {previous_link}
  {next_link}

  <main class="mx-auto max-w-5xl px-6 py-12 md:py-16">
    <header class="border-b border-neutral-800 pb-8">
      <div class="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
        <a href="../scenes/index.html" class="rounded-2xl border border-neutral-700 px-4 py-2 text-sm font-semibold text-neutral-200 transition hover:bg-neutral-900">Episode Index</a>
        <a href="../alpha/index.html" class="rounded-2xl border border-neutral-700 px-4 py-2 text-sm font-semibold text-neutral-200 transition hover:bg-neutral-900">Portal</a>
      </div>
      <p class="mt-6 text-xs uppercase tracking-[0.24em] text-rose-300">Bloodline Alpha Reader Portal</p>
      <h1 class="mt-3 text-4xl font-bold tracking-tight text-neutral-50 md:text-5xl">{html.escape(episode.title, quote=False)}</h1>
      <div class="mt-4 flex flex-wrap gap-2">
        {badge}
        <span class="rounded-full border border-neutral-700 bg-neutral-950/80 px-3 py-1 text-xs uppercase tracking-[0.18em] text-neutral-300">{episode.word_count} words</span>
        <span class="rounded-full border border-neutral-700 bg-neutral-950/80 px-3 py-1 text-xs uppercase tracking-[0.18em] text-neutral-300">~{estimate_read_minutes(episode.word_count)} min read</span>
        <span class="rounded-full border border-neutral-700 bg-neutral-950/80 px-3 py-1 text-xs uppercase tracking-[0.18em] text-neutral-300">{episode.section_count} section{'s' if episode.section_count != 1 else ''}</span>
        <span class="rounded-full border border-neutral-700 bg-neutral-950/80 px-3 py-1 text-xs uppercase tracking-[0.18em] text-neutral-300">Updated {html.escape(episode.updated_at, quote=False)}</span>
      </div>
      <div class="mt-8 grid gap-5 lg:grid-cols-[minmax(0,1.3fr)_minmax(18rem,0.7fr)]">
        <section class="rounded-3xl border border-neutral-800 bg-neutral-900/60 p-6">
          <p class="text-xs uppercase tracking-[0.18em] text-neutral-500">Release Note</p>
          <p class="mt-3 text-base leading-7 text-neutral-200">{html.escape('Available now for launch week readers.' if episode.release_state == 'live' else 'This is the one-week-ahead episode for readers staying ahead of the public launch.', quote=False)}</p>
        </section>
        <section class="rounded-3xl border border-neutral-800 bg-neutral-950/45 p-6">
          <p class="text-xs uppercase tracking-[0.18em] text-neutral-500">Reader Guidance</p>
          <p class="mt-3 text-sm leading-6 text-neutral-300">Read the full episode straight through, then leave notes at the end. Flag confusion, drag, emotional beats, continuity problems, and lines worth keeping.</p>
        </section>
      </div>
    </header>

    <section class="mt-8 rounded-3xl border border-neutral-800 bg-neutral-900/65 p-6 md:p-8">
      <div class="episode-copy">
{episode.body_html}
      </div>
    </section>

    <section class="mt-8 rounded-3xl border border-neutral-800 bg-neutral-950/35 p-6">
      <div class="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <p class="text-xs uppercase tracking-[0.24em] text-rose-300">Reader Feedback</p>
          <h2 class="mt-2 text-2xl font-semibold text-neutral-50">Notes on this episode</h2>
          <p class="mt-2 max-w-2xl text-sm leading-6 text-neutral-300">Alpha readers can send reactions, line notes, continuity catches, or general impressions directly from this page.</p>
        </div>
        <p class="text-xs text-neutral-500">Submits to the current Formspree inbox.</p>
      </div>
      {render_feedback_form(episode)}
    </section>

    <nav class="mt-8 flex items-center justify-between gap-4 border-t border-neutral-800 pt-8">
      {previous_nav}
      {next_nav}
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
      const context = JSON.parse(document.getElementById("episode-context").textContent);
      const LAST_READING_KEY = "bloodline:lastReadingPosition";
      const EPISODE_SCROLL_PREFIX = "bloodline:episodeScroll:";
      const EPISODE_STATE_PREFIX = "bloodline:episodeState:";
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

      function episodeScrollKey(slug) {{
        return `${{EPISODE_SCROLL_PREFIX}}${{slug}}`;
      }}

      function episodeStateKey(slug) {{
        return `${{EPISODE_STATE_PREFIX}}${{slug}}`;
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
          episodeSlug: context.episodeSlug,
          episodeTitle: context.episodeTitle,
          episodeUrl: context.episodeUrl,
          scrollY: Math.round(scrollY),
          scrollPercent: Math.round(scrollPercent),
          updatedAt: new Date().toISOString(),
        }};
      }}

      function markInProgress(updatedAt) {{
        const key = episodeStateKey(context.episodeSlug);
        const existing = readJson(key) || {{
          episodeSlug: context.episodeSlug,
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
        writeJson(episodeScrollKey(context.episodeSlug), snapshot);
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
        const record = readJson(episodeScrollKey(context.episodeSlug));
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
        writeJson(episodeScrollKey(context.episodeSlug), resetRecord);
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


def render_index_page(manifest: list[dict[str, object]]) -> str:
    manifest_json = render_json_script(manifest)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Episode Index | Bloodline Alpha</title>
  <meta name="description" content="Alpha-reader episode index for Bloodline.">
  <meta name="robots" content="noindex,nofollow,noarchive,noimageindex">
  <meta name="theme-color" content="#111827">
  <link rel="icon" type="image/x-icon" href="../favicon.ico">
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="../alpha/auth.js"></script>
</head>
<body class="min-h-screen bg-neutral-950 text-neutral-100 antialiased">
  <script>
    window.BloodlineAlphaAuth.requireAuth({{ redirectTo: "../alpha/index.html" }});
  </script>
  <script id="episode-manifest" type="application/json">{manifest_json}</script>

  <main class="mx-auto max-w-6xl px-6 py-12 md:py-16">
    <div class="flex flex-col gap-6 border-b border-neutral-800 pb-8 md:flex-row md:items-end md:justify-between">
      <div>
        <p class="text-xs uppercase tracking-[0.24em] text-rose-300">Bloodline Alpha Reader Portal</p>
        <h1 class="mt-3 text-4xl font-bold tracking-tight text-neutral-50">Episode launch shelf</h1>
        <p class="mt-3 max-w-3xl text-sm leading-6 text-neutral-300">
          Controlled reading hub for the episode launch set. Episodes 0 and 1 are the opening-week read. Episode 2 is posted here as the one-week-ahead follow-up.
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
          <p class="text-xs uppercase tracking-[0.18em] text-rose-300">Launch Structure</p>
          <h2 class="mt-3 text-2xl font-semibold text-neutral-50">Reader workflow</h2>
          <p class="mt-3 max-w-3xl text-sm leading-6 text-neutral-300">
            Start with Episode 0, move directly into Episode 1, and then use Episode 2 as the week-ahead entry. Leave notes after each episode page once you finish reading it through.
          </p>
        </div>
        <div class="rounded-2xl border border-neutral-800 bg-neutral-950/60 px-4 py-3 text-xs uppercase tracking-[0.18em] text-neutral-400">
          Mission mode: launch week
        </div>
      </div>
    </section>

    <section id="continue-reading-module" class="mt-6 rounded-3xl border border-rose-900/60 bg-rose-950/30 p-6">
      <div class="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <p class="text-xs uppercase tracking-[0.18em] text-rose-300">Continue reading</p>
          <h2 id="continue-title" class="mt-2 text-2xl font-semibold text-neutral-50">Loading reading position...</h2>
          <p id="continue-copy" class="mt-2 text-sm leading-6 text-neutral-300">Checking the last episode you opened.</p>
          <p id="continue-meta" class="mt-3 text-xs uppercase tracking-[0.18em] text-neutral-500"></p>
        </div>
        <a id="continue-link" href="./episode-0.html?resume=1" class="inline-flex items-center justify-center rounded-2xl bg-rose-600 px-5 py-3 text-sm font-semibold text-neutral-50 transition hover:bg-rose-500">
          Continue reading
        </a>
      </div>
    </section>

    <section class="mt-10 grid gap-5 lg:grid-cols-[minmax(0,1.45fr)_minmax(18rem,0.55fr)]">
      <article class="rounded-3xl border border-neutral-800 bg-neutral-900/70 p-6">
        <div class="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 class="text-xl font-semibold text-neutral-50">Episode shelf</h2>
            <p class="mt-2 text-sm leading-6 text-neutral-400">
              Follow the launch set in order, keep your place, and mark each episode finished as you go.
            </p>
          </div>
        </div>
        <div id="episode-list" class="mt-6 space-y-4">
          <div class="rounded-2xl border border-dashed border-neutral-700 bg-neutral-950/60 p-5">
            <p class="text-sm font-medium text-neutral-100">Loading episode shelf...</p>
            <p class="mt-2 text-sm leading-6 text-neutral-400">
              If this stays here, the generated episode manifest is missing or unreadable.
            </p>
          </div>
        </div>
      </article>

      <aside class="rounded-3xl border border-neutral-800 bg-neutral-900/70 p-6">
        <h2 class="text-xl font-semibold text-neutral-50">Reader briefing</h2>
        <p class="mt-4 text-sm leading-6 text-neutral-300">
          Bloodline is currently organized for an episode-first launch pass. The first week contains Episodes 0 and 1, with Episode 2 available here as the one-week-ahead continuation.
        </p>
        <ul class="mt-5 space-y-3 text-sm leading-6 text-neutral-300">
          <li>Read Episode 0 first.</li>
          <li>Read Episode 1 in the same week.</li>
          <li>Use Episode 2 as the week-ahead follow-up.</li>
          <li>Leave notes after each full episode.</li>
        </ul>
        <div class="mt-6 rounded-2xl border border-neutral-800 bg-neutral-950/60 px-4 py-3 text-xs uppercase tracking-[0.18em] text-neutral-400">
          Current repo mode: Episode launch
        </div>
      </aside>
    </section>
  </main>

  <script>
    (() => {{
      const episodeManifest = JSON.parse(document.getElementById("episode-manifest").textContent);
      const LAST_READING_KEY = "bloodline:lastReadingPosition";
      const EPISODE_STATE_PREFIX = "bloodline:episodeState:";
      const formatter = new Intl.DateTimeFormat("en-US", {{ month: "short", day: "numeric", year: "numeric" }});

      const episodeList = document.getElementById("episode-list");
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

      function episodeStateKey(slug) {{
        return `${{EPISODE_STATE_PREFIX}}${{slug}}`;
      }}

      function getEpisodeState(slug) {{
        return readJson(episodeStateKey(slug));
      }}

      function setEpisodeState(episode, status) {{
        const existing = getEpisodeState(episode.episodeSlug) || {{
          episodeSlug: episode.episodeSlug,
          status: "not-started",
          openedAt: null,
          markedReadAt: null,
        }};
        const now = new Date().toISOString();
        existing.episodeSlug = episode.episodeSlug;
        existing.status = status;
        if (status === "not-started") {{
          existing.openedAt = null;
          existing.markedReadAt = null;
        }} else {{
          existing.openedAt = existing.openedAt || now;
          existing.markedReadAt = status === "read" ? (existing.markedReadAt || now) : null;
        }}
        writeJson(episodeStateKey(episode.episodeSlug), existing);
      }}

      function markOpened(episode) {{
        const existing = getEpisodeState(episode.episodeSlug);
        if (existing?.status === "read") return;
        setEpisodeState(episode, "in-progress");
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

      function currentStatus(episode) {{
        const state = getEpisodeState(episode.episodeSlug);
        return state?.status || "not-started";
      }}

      function continueTarget() {{
        const last = readJson(LAST_READING_KEY);
        if (last?.episodeSlug) {{
          const episode = episodeManifest.find((entry) => entry.episodeSlug === last.episodeSlug);
          if (episode) {{
            return {{
              episode,
              position: last,
              mode: "resume",
            }};
          }}
        }}

        return {{
          episode: episodeManifest[0],
          position: null,
          mode: "start",
        }};
      }}

      function renderContinueReading() {{
        const target = continueTarget();
        if (!target.episode) {{
          continueTitle.textContent = "No episode pages available yet";
          continueCopy.textContent = "Run the generator to populate this portal index.";
          continueMeta.textContent = "";
          continueLink.classList.add("pointer-events-none", "opacity-50");
          continueLink.href = "#";
          return;
        }}

        continueTitle.textContent = `Continue reading: ${{target.episode.episodeTitle}}`;
        continueLink.href = target.mode === "resume"
          ? `${{target.episode.episodeUrl}}?resume=1`
          : target.episode.episodeUrl;

        if (target.mode === "resume" && target.position) {{
          continueCopy.textContent = `Last position: about ${{Math.round(target.position.scrollPercent || 0)}}%`;
          const parts = [];
          if (target.position.updatedAt) {{
            parts.push(`Last opened ${{formatDate(target.position.updatedAt)}}`);
          }}
          continueMeta.textContent = parts.join(" • ");
          continueLink.textContent = "Continue reading";
        }} else {{
          continueCopy.textContent = "No saved position yet. Start with Episode 0.";
          continueMeta.textContent = "";
          continueLink.textContent = "Start reading";
        }}
      }}

      function episodeCard(episode) {{
        const status = currentStatus(episode);
        const releaseClasses = episode.releaseState === "live"
          ? "border-emerald-900/60 bg-emerald-950/40 text-emerald-100"
          : "border-sky-900/60 bg-sky-950/40 text-sky-100";

        const metaChips = [
          `<span class="rounded-full border px-3 py-1 text-[11px] uppercase tracking-[0.18em] ${{releaseClasses}}">${{episode.releaseLabel}}</span>`,
          `<span class="rounded-full border border-neutral-700 bg-neutral-950/80 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-neutral-300">Updated ${{episode.updatedAt}}</span>`,
          `<span class="rounded-full border border-neutral-700 bg-neutral-950/80 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-neutral-300">${{episode.sectionCount}} section${{episode.sectionCount === 1 ? "" : "s"}}</span>`,
          `<span class="rounded-full border border-neutral-700 bg-neutral-950/80 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-neutral-300">${{episode.wordCount}} words</span>`,
          `<span class="rounded-full border border-neutral-700 bg-neutral-950/80 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-neutral-300">~${{episode.estimatedReadMinutes}} min read</span>`,
          statusBadge(status),
        ].join("");

        return `
          <article class="rounded-3xl border border-neutral-800 bg-neutral-950/35 p-5">
            <div class="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
              <div class="min-w-0">
                <div class="flex flex-wrap items-center gap-2">
                  <p class="text-xs uppercase tracking-[0.18em] text-neutral-500">Release order ${{episode.episodeNumber + 1}}</p>
                </div>
                <h3 class="mt-3 text-xl font-semibold text-neutral-50">${{episode.episodeTitle}}</h3>
                <p class="mt-3 max-w-3xl text-sm leading-6 text-neutral-300">${{episode.excerpt}}</p>
                <div class="mt-4 flex flex-wrap gap-2">${{metaChips}}</div>
                <div class="mt-4 rounded-2xl border border-neutral-800 bg-neutral-950/60 px-4 py-3">
                  <p class="text-[11px] uppercase tracking-[0.18em] text-neutral-500">Launch note</p>
                  <p class="mt-2 text-sm font-medium text-neutral-100">${{episode.releaseDescription}}</p>
                </div>
              </div>
              <div class="flex w-full flex-col gap-3 md:w-auto md:min-w-[12rem]">
                <a href="${{episode.episodeUrl}}" data-open-episode="${{episode.episodeSlug}}" class="inline-flex items-center justify-center rounded-2xl bg-rose-600 px-4 py-3 text-sm font-semibold text-neutral-50 transition hover:bg-rose-500">
                  Open episode
                </a>
                <button type="button" data-mark-read="${{episode.episodeSlug}}" class="inline-flex items-center justify-center rounded-2xl border border-neutral-700 px-4 py-3 text-sm font-semibold text-neutral-200 transition hover:bg-neutral-900">
                  ${{status === "read" ? "Mark unread" : "Mark read"}}
                </button>
              </div>
            </div>
          </article>
        `;
      }}

      function renderEpisodeList() {{
        if (!episodeManifest.length) {{
          episodeList.innerHTML = `
            <div class="rounded-2xl border border-dashed border-neutral-700 bg-neutral-950/60 p-5">
              <p class="text-sm font-medium text-neutral-100">No episode pages available yet.</p>
              <p class="mt-2 text-sm leading-6 text-neutral-400">Run the episode generator to populate this portal index.</p>
            </div>
          `;
          return;
        }}

        episodeList.innerHTML = episodeManifest.map(episodeCard).join("");

        episodeList.querySelectorAll("[data-open-episode]").forEach((link) => {{
          link.addEventListener("click", () => {{
            const slug = link.getAttribute("data-open-episode");
            const episode = episodeManifest.find((entry) => entry.episodeSlug === slug);
            if (episode) {{
              markOpened(episode);
            }}
          }});
        }});

        episodeList.querySelectorAll("[data-mark-read]").forEach((button) => {{
          button.addEventListener("click", () => {{
            const slug = button.getAttribute("data-mark-read");
            const episode = episodeManifest.find((entry) => entry.episodeSlug === slug);
            if (!episode) return;
            const status = currentStatus(episode);
            setEpisodeState(episode, status === "read" ? "not-started" : "read");
            renderContinueReading();
            renderEpisodeList();
          }});
        }});
      }}

      renderContinueReading();
      renderEpisodeList();
    }})();
  </script>
</body>
</html>
"""


def render_source_manifest(episodes: list[EpisodeDoc]) -> list[dict[str, object]]:
    return [
        {
            "episode": episode.number,
            "title": episode.title,
            "slug": episode.slug,
            "source": episode.source_name,
            "wordCount": episode.word_count,
            "releaseState": episode.release_state,
        }
        for episode in episodes
    ]


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    source_files = sorted(
        [path for path in SOURCE_DIR.glob("Episode*.md") if path.name not in SKIP_FILES],
        key=episode_sort_key,
    )
    episodes = [episode for path in source_files if (episode := build_episode_document(path))]
    episodes.sort(key=lambda episode: episode.number)

    manifest = render_episode_manifest(episodes)

    keep_html = {"index.html"}
    for index, episode in enumerate(episodes):
        previous_episode = episodes[index - 1] if index > 0 else None
        next_episode = episodes[index + 1] if index + 1 < len(episodes) else None
        output_name = f"{episode.slug}.html"
        keep_html.add(output_name)
        (OUTPUT_DIR / output_name).write_text(
            render_episode_page(episode, previous_episode, next_episode),
            encoding="utf-8",
        )

    (OUTPUT_DIR / "index.html").write_text(render_index_page(manifest), encoding="utf-8")

    for existing in OUTPUT_DIR.glob("*.html"):
        if existing.name not in keep_html:
            existing.unlink()

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    LEGACY_MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    LEGACY_SOURCE_MANIFEST_PATH.write_text(json.dumps(render_source_manifest(episodes), indent=2), encoding="utf-8")
    print(f"Generated {len(episodes)} episode pages from {SOURCE_DIR} into {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
