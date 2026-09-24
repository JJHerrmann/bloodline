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

### Shelton Observatory share cards

Shelton Observatory case-file links use the full parchment editorial card as
their social image, not a standalone character portrait. The portrait shown on
each card belongs to that file's primary interviewer/researcher (as identified
by `primary_researcher` in the source frontmatter), whether that is Nico, Anne,
or another researcher. The remaining card fields come from the individual case:
case ID and classification, title, pull quote, filing credit, and call to action.

The first published card is
`images/shelton-observatory-voices-share-card.jpg`; Anne's reusable portrait is
`images/hootin-anne-newsome.webp`.

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

To generate from another source directory temporarily:

```bash
BLOODLINE_SOURCE_DIR=/absolute/path/to/episodes python scripts/generate_scenes.py
```

## Planned public structure

The route and content plan is documented in [`docs/SITE_STRUCTURE.md`](docs/SITE_STRUCTURE.md).
