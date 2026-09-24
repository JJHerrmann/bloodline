#!/usr/bin/env python3
"""Synchronize the safe public release ledger from Patreon API v2.

This intentionally knows nothing about manuscript files. It only updates
episodes already explicitly listed in content/publication.json, so a post title
or a future Patreon draft can never accidentally disclose a new episode.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "content" / "publication.json"
API = "https://www.patreon.com/api/oauth2/v2"
NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20,
}


def request_json(url: str, *, data: dict[str, str] | None = None, token: str | None = None) -> dict:
    encoded = urllib.parse.urlencode(data).encode() if data else None
    headers = {"Accept": "application/json"}
    if data:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=encoded, headers=headers), timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        # Patreon error bodies identify configuration problems (for example,
        # an invalid grant) but never need to include a credential in the log.
        detail = error.read().decode("utf-8", errors="replace")[:800]
        raise RuntimeError(f"Patreon API returned HTTP {error.code}: {detail}") from error


def access_token() -> str:
    required = ("PATREON_CLIENT_ID", "PATREON_CLIENT_SECRET", "PATREON_REFRESH_TOKEN")
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise RuntimeError(f"Missing required environment variable(s): {', '.join(missing)}")
    payload = request_json(
        "https://www.patreon.com/api/oauth2/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": os.environ["PATREON_REFRESH_TOKEN"],
            "client_id": os.environ["PATREON_CLIENT_ID"],
            "client_secret": os.environ["PATREON_CLIENT_SECRET"],
        },
    )
    if not payload.get("access_token"):
        raise RuntimeError("Patreon did not return an access token")
    return payload["access_token"]


def episode_number(title: str) -> int | None:
    match = re.search(r"\bepisode\s*(\d+|[a-z]+)\b", title, flags=re.IGNORECASE)
    if not match:
        return None
    value = match.group(1).lower()
    return int(value) if value.isdigit() else NUMBER_WORDS.get(value)


def campaign_posts(token: str) -> list[dict]:
    campaigns = request_json(f"{API}/campaigns", token=token).get("data", [])
    if not campaigns:
        raise RuntimeError("No Patreon campaign was returned for this creator token")
    campaign_id = campaigns[0]["id"]
    fields = urllib.parse.urlencode({"fields[post]": "title,url,is_public,published_at"})
    next_url = f"{API}/campaigns/{campaign_id}/posts?{fields}"
    posts: list[dict] = []
    while next_url:
        payload = request_json(next_url, token=token)
        posts.extend(payload.get("data", []))
        next_url = payload.get("links", {}).get("next")
    return posts


def iso_day(value: str | None) -> str | None:
    return value[:10] if value else None


def main() -> None:
    token = access_token()
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    episodes = ledger.get("episodes", [])
    known = {item.get("number"): item for item in episodes if isinstance(item.get("number"), int)}
    now = datetime.now(UTC)

    for post in campaign_posts(token):
        attrs = post.get("attributes", {})
        number = episode_number(str(attrs.get("title") or ""))
        if number not in known:
            continue
        published_at = attrs.get("published_at")
        # Posts without a live timestamp are drafts; leave their deliberately
        # curated scheduled record alone.
        if not published_at:
            continue
        try:
            published_time = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        except ValueError:
            continue
        item = known[number]
        item["patreon_url"] = attrs.get("url") or item.get("patreon_url")
        if published_time > now:
            item["status"] = "scheduled"
            item["patreon_published"] = iso_day(published_at)
        elif attrs.get("is_public"):
            item["status"] = "public"
            item["published"] = iso_day(published_at)
            item.pop("patreon_published", None)
        else:
            item["status"] = "advance"
            item["patreon_published"] = iso_day(published_at)
            item.pop("published", None)

    rendered = json.dumps(ledger, indent=2) + "\n"
    if LEDGER.read_text(encoding="utf-8") == rendered:
        print("Patreon ledger already current")
        return
    LEDGER.write_text(rendered, encoding="utf-8")
    print("Updated content/publication.json from Patreon")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Patreon sync failed: {error}", file=sys.stderr)
        raise SystemExit(1)
