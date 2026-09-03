from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EPISODES = ROOT.parent / "Garnet Shield" / "Writing" / "Episodes"
EPISODE_RE = re.compile(r"^Episode\s+(\d+)\.md$", re.IGNORECASE)


def episode_number(path: Path) -> int:
    match = EPISODE_RE.match(path.name)
    return int(match.group(1)) if match else 999_999


def split_frontmatter(text: str) -> tuple[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", text

    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            frontmatter = "\n".join(lines[: index + 1])
            body = "\n".join(lines[index + 1 :])
            return frontmatter, body

    return "", text


def normalize_body(body: str) -> str:
    paragraphs = [line.rstrip() for line in body.splitlines() if line.strip()]
    if not paragraphs:
        return ""
    return "\n\n".join(paragraphs)


def normalize_document(text: str) -> str:
    frontmatter, body = split_frontmatter(text)
    normalized_body = normalize_body(body)
    if frontmatter and normalized_body:
        return f"{frontmatter}\n\n{normalized_body}\n"
    if frontmatter:
        return f"{frontmatter}\n"
    # Preserve empty placeholder episodes as a one-line blank file.
    return f"{normalized_body}\n" if normalized_body else "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Separate each line-authored novel paragraph with one blank Markdown line."
    )
    parser.add_argument("--check", action="store_true", help="Report files that need formatting without changing them.")
    parser.add_argument("--episodes", type=Path, default=DEFAULT_EPISODES)
    args = parser.parse_args()

    files = sorted(
        (path for path in args.episodes.glob("Episode *.md") if EPISODE_RE.match(path.name)),
        key=episode_number,
    )
    changed: list[Path] = []
    for path in files:
        original = path.read_text(encoding="utf-8")
        normalized = normalize_document(original)
        if normalized == original:
            continue
        changed.append(path)
        if not args.check:
            path.write_text(normalized, encoding="utf-8")

    action = "Need formatting" if args.check else "Formatted"
    print(f"{action}: {len(changed)} episode files")
    for path in changed:
        print(path.name)
    if args.check and changed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
