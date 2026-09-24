#!/usr/bin/env python3
"""Publish public reader pages after the Patreon release ledger changes.

Patreon supplies only release state. The prose always comes from the local
canonical vault, and build_public.py will only read episodes already marked
public in content/publication.json.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = Path(os.environ.get(
    "BLOODLINE_PUBLIC_SOURCE_DIR",
    "/home/rook/Documents/Runagarthur/Author/Mason Rok/Bloodline/Garnet Shield/Writing/Episodes",
))
LEDGER = ROOT / "content" / "publication.json"
INTERVAL = max(30, int(os.environ.get("BLOODLINE_PUBLIC_POLL_SECONDS", "60")))


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=check)


def signature() -> tuple[tuple[str, int, int], ...]:
    if not SOURCE.is_dir():
        raise RuntimeError(f"Episode folder is unavailable: {SOURCE}")
    files = tuple((path.name, path.stat().st_mtime_ns, path.stat().st_size) for path in sorted(SOURCE.glob("Episode *.md")))
    return files + (("publication.json", LEDGER.stat().st_mtime_ns, LEDGER.stat().st_size),)


def changed_paths() -> set[str]:
    return {line[3:] for line in run("git", "status", "--porcelain").stdout.splitlines() if len(line) > 3}


def sync_repo() -> None:
    if changed_paths():
        raise RuntimeError("Repository has uncommitted edits; reader publisher is standing by")
    run("git", "fetch", "origin", "main")
    if run("git", "rev-list", "--count", "HEAD..origin/main").stdout.strip() != "0":
        run("git", "pull", "--ff-only", "origin", "main")


def build_commit_push() -> bool:
    before = changed_paths()
    if before:
        raise RuntimeError("Repository has uncommitted edits; refusing to mix generated pages with them")
    run(sys.executable, "scripts/build_public.py")
    changed = changed_paths()
    allowed = {"read/index.html", "sitemap.xml"}
    if any(path not in allowed and not path.startswith("read/garnet-shield/episode-") for path in changed):
        raise RuntimeError(f"Reader builder changed unexpected files: {sorted(changed)}")
    if not changed:
        return False
    run("git", "add", "--", "read", "sitemap.xml")
    run("git", "commit", "-m", "reader: publish confirmed public episodes")
    run("git", "push", "origin", "main")
    return True


def main() -> None:
    print(f"Bloodline Reader Publisher watching: {SOURCE}", flush=True)
    previous: tuple[tuple[str, int, int], ...] | None = None
    while True:
        try:
            sync_repo()
            current = signature()
            if current != previous:
                previous = current
                changed = build_commit_push()
                print("Published reader pages." if changed else "Reader pages already current.", flush=True)
        except Exception as error:
            print(f"Reader publisher paused: {error}", file=sys.stderr, flush=True)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
