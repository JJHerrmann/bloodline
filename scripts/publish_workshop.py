#!/usr/bin/env python3
"""Safely publish reader-visible Workshop data when the episode folder changes.

This process never reads or stages manuscript files for Git. It runs the
existing allowlisted builder, validates its output, and can commit exactly one
file: content/workshop.json. Any unrelated repository change is a hard stop.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "content" / "workshop.json"
CONFIG = ROOT / "content" / "workshop.public.json"
SOURCE = Path(os.environ.get(
    "BLOODLINE_WORKSHOP_SOURCE_DIR",
    "/home/rook/Documents/Runagarthur/Author/Mason Rok/Bloodline/Garnet Shield/Writing/Episodes",
))
INTERVAL = max(2, int(os.environ.get("BLOODLINE_WORKSHOP_POLL_SECONDS", "5")))
ALLOWED_TOP = {"siteTitle", "intro", "updatedLabel", "generatedAt", "books", "nextDrops", "worldInventory", "judahTotal", "activity", "tone"}
ALLOWED_EPISODE = {"number", "title", "words", "url", "published", "started"}


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=check)


def source_signature() -> tuple[tuple[str, int, int], ...]:
    if not SOURCE.is_dir():
        raise RuntimeError(f"Episode folder is unavailable: {SOURCE}")
    episodes = tuple(
        (path.name, path.stat().st_mtime_ns, path.stat().st_size)
        for path in sorted(SOURCE.glob("Episode *.md"))
    )
    config = CONFIG.stat()
    return episodes + (("workshop.public.json", config.st_mtime_ns, config.st_size),)


def validate_public_data() -> None:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    unexpected = set(data) - ALLOWED_TOP
    if unexpected:
        raise RuntimeError(f"Refusing to publish unexpected top-level fields: {sorted(unexpected)}")
    for book in data.get("books", []):
        for episode in [*book.get("episodes", []), *book.get("plannedEpisodes", [])]:
            unexpected = set(episode) - ALLOWED_EPISODE
            if unexpected:
                raise RuntimeError(f"Refusing to publish unexpected episode fields: {sorted(unexpected)}")
            if episode.get("started") is False and episode.get("words") != 0:
                raise RuntimeError("Refusing to publish an unstarted episode with words")


def changed_paths() -> set[str]:
    result = run("git", "status", "--porcelain")
    return {line[3:] for line in result.stdout.splitlines() if len(line) > 3}


def build_commit_push() -> bool:
    before = changed_paths()
    # Do not ever work around someone else's uncommitted site edits.
    if before - {"content/workshop.json"}:
        raise RuntimeError("Repository has unrelated changes; publisher is standing by")
    run(sys.executable, "scripts/build_workshop.py")
    validate_public_data()
    after = changed_paths()
    if not after:
        return False
    if after != {"content/workshop.json"}:
        raise RuntimeError(f"Builder changed files outside its public allowlist: {sorted(after)}")
    run("git", "add", "--", "content/workshop.json")
    run("git", "commit", "-m", "workshop: refresh public production data")
    run("git", "push", "origin", "main")
    return True


def main() -> None:
    print(f"Bloodline Workshop Publisher watching: {SOURCE}", flush=True)
    previous = source_signature()
    pending = False
    while True:
        time.sleep(INTERVAL)
        try:
            current = source_signature()
            if current != previous:
                previous = current
                pending = True
            if pending:
                published = build_commit_push()
                pending = False
                print("Published public Workshop data." if published else "No public data changed.", flush=True)
        except Exception as error:
            # Keep running: a transient drive issue or an in-progress editor save
            # should not turn off the watcher. It retries after the next change.
            print(f"Publisher paused: {error}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
