#!/usr/bin/env python3
"""Local-only Bloodline Stream Desk.

Serves the overlay plus a safe, live status feed. It never returns manuscript
text, frontmatter, filenames, loglines, or private notes.
"""
from __future__ import annotations

import json
import mimetypes
import os
import re
import threading
import time
from datetime import date
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import yaml

ROOT = Path(__file__).resolve().parent.parent
EPISODES = Path(os.environ.get(
    "BLOODLINE_STREAM_EPISODES",
    "/home/rook/Documents/Runagarthur/Author/Mason Rok/Bloodline/Garnet Shield/Writing/Episodes",
))
PORT = int(os.environ.get("BLOODLINE_STREAM_PORT", "4174"))
LOCK = threading.Lock()
STATE = {"phase": "idle", "active_episode": None, "started_at": None, "baseline_novel_words": 0, "baseline_episode_words": {}, "duration_seconds": 25 * 60}


def split_frontmatter(path: Path) -> tuple[dict, str]:
    raw = path.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", raw, re.DOTALL)
    return (yaml.safe_load(match.group(1)) or {}, match.group(2)) if match else ({}, raw)


def prose_word_count(body: str) -> int:
    if body.strip() == "Begin manuscript here.":
        return 0
    body = re.sub(r"<!--[\s\S]*?-->|%%[\s\S]*?%%", "", body)
    body = re.sub(r"^> ?\[![^\n]*(\n>[^\n]*)*", "", body, flags=re.MULTILINE)
    body = re.sub(r"^\s*(#{1,6}\s.*|-{3,}|\*{3,}|_{3,}|[-*] \[.\].*)\s*$", "", body, flags=re.MULTILINE)
    return len(re.findall(r"\b[\w’'-]+\b", body))


def released(meta: dict) -> bool:
    if str(meta.get("publication_status", "")).lower() == "published":
        return True
    today = date.today().isoformat()
    for key in ("scheduled paid post", "scheduled free post"):
        value = str(meta.get(key) or "")
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) and value <= today:
            return True
    return False


def snapshot() -> dict:
    episodes = []
    for path in sorted(EPISODES.glob("Episode *.md"), key=lambda item: int(re.search(r"\d+", item.stem).group())):
        meta, body = split_frontmatter(path)
        number = meta.get("episode")
        if not isinstance(number, int):
            continue
        words = prose_word_count(body)
        episodes.append({"number": number, "words": words, "started": words > 0, "released": released(meta) if words else False, "modified": path.stat().st_mtime})
    written = [episode for episode in episodes if episode["started"]]
    total = sum(episode["words"] for episode in written)
    with LOCK:
        active = STATE["active_episode"]
        if active is None and written:
            active = max(written, key=lambda episode: episode["modified"])["number"]
        current = next((episode for episode in episodes if episode["number"] == active), None)
        now = time.time()
        elapsed = int(now - STATE["started_at"]) if STATE["phase"] == "writing" and STATE["started_at"] else 0
        current_words = current["words"] if current else 0
        episode_deltas = [
            {"number": episode["number"], "deltaWords": episode["words"] - STATE["baseline_episode_words"].get(str(episode["number"]), episode["words"]), "currentWords": episode["words"]}
            for episode in episodes
            if episode["words"] - STATE["baseline_episode_words"].get(str(episode["number"]), episode["words"]) != 0
        ]
        return {
            "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "phase": STATE["phase"],
            "activeEpisode": active,
            "episodeWords": current_words,
            "novelWords": total,
            "writtenEpisodes": len(written),
            "episodes": [{key: value for key, value in episode.items() if key != "modified"} for episode in episodes],
            "sprint": {
                "durationSeconds": STATE["duration_seconds"],
                "elapsedSeconds": elapsed,
                "secondsRemaining": max(0, STATE["duration_seconds"] - elapsed),
                "deltaWords": total - STATE["baseline_novel_words"],
                "episodeDeltas": episode_deltas,
            },
        }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_: object) -> None:
        pass

    def send_json(self, value: dict) -> None:
        body = json.dumps(value).encode("utf-8")
        self.send_response(HTTPStatus.OK); self.send_header("Content-Type", "application/json"); self.send_header("Cache-Control", "no-store"); self.send_header("Access-Control-Allow-Origin", "*"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/status":
            self.send_json(snapshot()); return
        relative = "index.html" if path == "/" else path.lstrip("/")
        target = (ROOT / relative).resolve()
        if target.is_dir():
            target = target / "index.html"
        if ROOT not in target.parents and target != ROOT or not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND); return
        body = target.read_bytes()
        self.send_response(HTTPStatus.OK); self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", "0")); payload = json.loads(self.rfile.read(length) or b"{}")
        current = snapshot()
        with LOCK:
            if path == "/api/sprint/start":
                STATE["active_episode"] = current["activeEpisode"]
                STATE.update(phase="writing", started_at=time.time(), baseline_novel_words=current["novelWords"], baseline_episode_words={str(item["number"]): item["words"] for item in current["episodes"]}, duration_seconds=int(payload.get("minutes", 25)) * 60)
            elif path == "/api/sprint/break":
                STATE["phase"] = "break"
            elif path == "/api/sprint/end":
                STATE["phase"] = "complete"
            else:
                self.send_error(HTTPStatus.NOT_FOUND); return
        self.send_json(snapshot())


if __name__ == "__main__":
    print(f"Bloodline Stream Desk: http://127.0.0.1:{PORT}/workshop/twitch-dispatch-overlay.html")
    print(f"Watching: {EPISODES}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
