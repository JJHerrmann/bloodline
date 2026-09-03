# Bloodline site structure

The site should become a serial reader wrapped in a compact author-and-series
hub. The first release can remain static; each section below maps cleanly to a
directory with an `index.html` page when implemented.

## Public routes

```text
/
├── read/
│   ├── index.html              # Public table of contents
│   └── garnet-shield/
│       └── episode-N/          # Public episode pages
├── story/
│   └── index.html              # Premise, reading order, content guidance
├── world/
│   └── index.html              # Spoiler-controlled lore and setting material
├── books/
│   └── index.html              # Ebook, print, and audio editions
├── community/
│   └── index.html              # Newsletter, Patreon, social links
└── about/
    └── index.html              # Mason Rok biography and contact details
```

## Existing private routes

```text
/alpha/                        # Alpha-reader entry and session handling
/scenes/                       # Current generated, access-controlled episodes
```

These stay in place until the public reader is ready. Public pages must not
link directly into gated drafts or expose unreleased manuscript material.

## Homepage priorities

1. One-sentence hook and cover art.
2. `Start reading` and `Latest episode` actions.
3. Release schedule and the Patreon advance-chapter gap.
4. Short premise and series identity.
5. Newsletter signup.
6. Links to Patreon, Royal Road, books, and community channels as they launch.

## Reader-page requirements

- A narrow, comfortable prose column.
- Previous, contents, and next controls above and below the episode.
- Book, arc, episode number, title, publication date, and reading time.
- Light/dark theme and adjustable type size.
- Optional author note after the episode, visually separated from the prose.
- A restrained Patreon/read-ahead call to action after the story text.
- Canonical URL, social metadata, and structured story metadata.
- No spoilers from later episodes in navigation, excerpts, or world links.

## Source and publication flow

```text
Obsidian episode Markdown
        ↓
scripts/generate_scenes.py
        ↓
generated preview / reader HTML
        ↓
editorial check and release-state selection
        ↓
public site + external-platform mirrors
```

Obsidian remains the source of truth. Royal Road and Patreon are distribution
channels; they should not become the only retained copy of an episode.

## Next implementation slice

1. Generalize the generator from its fixed launch-plan episode list.
2. Separate public, advance, and alpha release manifests.
3. Build `/read/` as a public table of contents.
4. Build a reusable public episode template.
5. Update the homepage navigation and calls to action.

