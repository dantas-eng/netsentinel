#!/usr/bin/env python3
"""Verifica links relativos Markdown contra arquivos existentes."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PATTERN = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def targets(text):
    for raw in PATTERN.findall(text):
        href = raw.split()[0].strip("<>")
        if href.startswith(("http://", "https://", "mailto:", "#")):
            continue
        href = href.split("#", 1)[0]
        if href:
            yield href


def main():
    broken = []
    for path in sorted(ROOT.rglob("*.md")):
        if ".venv" in path.parts or "node_modules" in path.parts:
            continue
        for href in targets(path.read_text(encoding="utf-8")):
            dest = (path.parent / href).resolve()
            if not dest.exists():
                broken.append(f"{path.relative_to(ROOT)} -> {href}")
    if broken:
        print("\n".join(broken))
        raise SystemExit(1)
    print("ok")


if __name__ == "__main__":
    main()
