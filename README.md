# Bloodline website

Static website for **Bloodline: Spirits of the Smokies** by Mason Rok.

The repository is intentionally stored inside the Bloodline area of the
Runagarthur Obsidian vault. It is the publishing layer, not the canonical home
of the manuscript.

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

To generate from another source directory temporarily:

```bash
BLOODLINE_SOURCE_DIR=/absolute/path/to/episodes python scripts/generate_scenes.py
```

## Planned public structure

The route and content plan is documented in [`docs/SITE_STRUCTURE.md`](docs/SITE_STRUCTURE.md).
