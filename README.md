# Bloodline website

Static website for **Bloodline: Spirits of the Smokies** by Mason Rok.

The repository is intentionally stored inside the Bloodline area of the
Runagarthur Obsidian vault. It is the publishing layer, not the canonical home
of the manuscript.

## Patreon release sync

`content/publication.json` is the reader-safe release ledger for `/status/`.
The GitHub Action in `.github/workflows/sync-patreon-status.yml` polls Patreon
API v2 every ten minutes and updates only the existing episode records. It does
not read or export manuscript text.

Add these GitHub Actions secrets before enabling the workflow:

- `PATREON_CLIENT_ID`
- `PATREON_CLIENT_SECRET`
- `PATREON_REFRESH_TOKEN`

Use a Patreon v2 client with the `campaigns` and `campaigns.posts` scopes.
The access token is deliberately not stored: the workflow exchanges the refresh
token for a short-lived access token on every run.

On the author workstation, `systemd/bloodline-reader-publisher.service` polls
the trusted release ledger and the canonical episode folder. It generates pages
only for already-public ledger records, updates `/read/` and `sitemap.xml`, and
pushes generated output when anything changed. Patreon is never used as a prose
source.

## Content boundary

- Canonical episode drafts: `../Garnet Shield/Writing/Episodes/`
- Canonical supplemental drafts: `../Shelton Observatory/Writing/`
- Generated reader pages and manifests: `scenes/`
- Public landing page: `index.html`
- Alpha-reader login: `alpha/`
- Images and video: `images/` and `video/`

Do not edit generated episode HTML when changing story prose. Edit the episode
Markdown in the vault and regenerate the reader pages.

## Generate the current reader pages

From the repository root:

```bash
python scripts/generate_scenes.py
```

Build the public Shelton Observatory case files from their canonical vault
sources with:

```bash
python scripts/build_supplements.py
```

### Text-message callouts

Shelton Observatory sources can mark a text exchange with Obsidian's native
callout syntax. The supplemental builder renders each separated paragraph as
an outgoing iPhone-style message bubble:

```markdown
> [!text-message]
> **From:** Anne Newsome
> **To:** Nico Shelton
> **Status:** Delivered
>
> First message.
>
> Second message.
```

### Letter correspondence

Roughly half the case files frame their intro/stinger as a plain letter
instead of a text exchange (Nico &lt;-&gt; Director Stane, Director &lt;-&gt;
Mountreich, etc.) rather than the `[!text-message]` callout above. No special
syntax is needed: any paragraph block that sits between top-level `---` rules,
isn't a `[!text-message]` callout, and doesn't contain a heading is treated as
a letter and rendered as an italic parchment-style box, with its closing
signature broken onto its own lines and styled separately from the body.

Because the vault is written for Obsidian's lenient line-break rendering
(every newline is a visual break) rather than strict CommonMark hard breaks,
lines inside a letter paragraph are joined with `<br>`, not a space — so a
short address or signature block should be written one line per line, e.g.:

```markdown
Dear Director,
It's come to my attention that...

Truly,
Nicodemus Shelton
Chairman of the Shelton Observatory
```

### Shelton Observatory share cards

Shelton Observatory case-file links can use either a dedicated editorial card
or the file's credited researcher portrait. Configure this per case with
`share_image`, `share_image_width`, and `share_image_height` in the canonical
source frontmatter.

The Voices at Lover's Leap uses Anne's reusable portrait at
`images/hootin-anne-newsome.webp`. The portrait is adapted from a photograph by
Ron Lach on Pexels; source and license details are recorded in `CREDITS.md`.

Generic, currently non-canonical interviewer portraits live in
`images/shelton-interviewers/`. They are numbered rather than named so using a
portrait does not establish a character until the corresponding case-file
source identifies the interviewer. The initial pool is:

- `interviewer-01.webp` — younger male field investigator
- `interviewer-02.webp` — mid-career Black woman interviewer
- `interviewer-03.webp` — veteran woman oral historian
- `interviewer-04.webp` — Latino male folklorist/audio researcher
- `interviewer-05.webp` — South Asian American woman signal-analysis researcher
- `interviewer-06.webp` — white Appalachian male instrumentation and maintenance technician

General Patreon and Ko-fi links use the owned `go.rook.works/patreon/` and
`go.rook.works/kofi/` redirects. Those routes record anonymous aggregate click
counts before continuing to the external support page; tier checkout and
individual post links continue to point directly at their exact destinations.

To generate from another source directory temporarily:

```bash
BLOODLINE_SOURCE_DIR=/absolute/path/to/episodes python scripts/generate_scenes.py
```

## Planned public structure

The route and content plan is documented in [`docs/SITE_STRUCTURE.md`](docs/SITE_STRUCTURE.md).
