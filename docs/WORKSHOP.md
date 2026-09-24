# The public workshop

`/workshop/` is a reader-facing production room, not a mirror of the Obsidian vault. Its browser code reads only `content/workshop.json`, a generated file that is safe to deploy.

## Update flow

1. Edit `content/workshop.public.json`. This is the public editorial ledger. Add only reader-safe titles, counts, dates, activity lines, and scored percentages. Keep future books, pitches, vault paths, manuscript excerpts, private notes, and internal status out of it.
2. The production data comes from the canonical episode folder. By default it is `/home/rook/Documents/Runagarthur/Author/Mason Rok/Bloodline/Garnet Shield/Writing/Episodes`; on another machine, set `BLOODLINE_WORKSHOP_SOURCE_DIR` to that folder.
3. Run `python scripts/build_workshop.py` from the repository root.
4. Review `content/workshop.json` before committing and deploy with the ordinary site publish flow.

The build reads only a narrow allowlist from the canonical files: episode number, prose-only word count, publication status, genre/tone scores, scheduled release dates, and aggregate Judah-caused costs. It does not serialize manuscript bodies, titles or links for unpublished episodes, private paths, notes, pitches, or arbitrary frontmatter. `public: false` records in the editorial ledger are excluded.

## One-time setup

No runtime service, API key, or database is needed. Add the two commands above to the existing deploy script or CI job so every publish rebuilds the workshop ledger. If content is hosted with immutable caching, deploy the generated `content/workshop.json` alongside the page; the browser requests it with `cache: no-store` for prompt refreshes.

### Stream overlay

`workshop/twitch-dispatch-overlay.html` is a transparent 1920×1080 browser-source lower third for OBS. Point an OBS Browser Source at `/workshop/twitch-dispatch-overlay.html` and use a 1920×1080 canvas. It intentionally advertises `/dispatch` before that participation route exists; replace the route text or build the moderated submission flow before using it publicly.

### Live Stream Desk

Run `BLOODLINE_STREAM_PORT=4173 python scripts/stream_desk.py` before a stream. It watches the canonical Episodes folder locally and serves both the live overlay and its data feed at `http://127.0.0.1:4173/workshop/twitch-dispatch-overlay.html`; use that address in OBS. Open `http://127.0.0.1:4173/workshop/stream-desk.html` privately to start, break, or end a sprint. The service returns only word counts, episode numbers, release state, and timer/session deltas—never prose.

### Automatic public-data publishing

`scripts/publish_workshop.py` watches the Episodes folder and `content/workshop.public.json`. When either changes, it rebuilds `content/workshop.json`, validates that its fields are reader-safe, commits that one generated file, and pushes it to `origin/main`.

It never stages vault files, prose, frontmatter, or any unrelated site work. If another site change is uncommitted, the publisher pauses and retries instead of bundling it into an automatic commit. The accompanying user service is `systemd/bloodline-workshop-publisher.service`; install it once with:

```sh
mkdir -p ~/.config/systemd/user
cp systemd/bloodline-workshop-publisher.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now bloodline-workshop-publisher.service
```

Check its activity with `journalctl --user -u bloodline-workshop-publisher.service -f`. Stop it with `systemctl --user disable --now bloodline-workshop-publisher.service`.

## Publishing checklist

- Is the item safe for readers who have only read the public episodes?
- Does it reveal no upcoming plot, unreleased title, character secret, or private schedule?
- Is every `nextDrops` entry intentionally marked public?
- Did you inspect the generated JSON rather than relying on the source ledger?
