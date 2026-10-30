"""Validate curated portfolio links/config and Python syntax without services."""
from __future__ import annotations

import ast
import configparser
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    errors: list[str] = []
    documents = [ROOT / "README.md", *sorted((ROOT / "docs/portfolio").rglob("*.md"))]
    links = 0
    for document in documents:
        text = document.read_text()
        for target in re.findall(r"\]\(([^)]+)\)", text):
            if target.startswith(("https://", "http://", "mailto:", "#")):
                continue
            path = target.split("#", 1)[0]
            if not (document.parent / path).exists():
                errors.append(f"{document.relative_to(ROOT)}: missing link {target}")
            links += 1
    for path in [*(ROOT / "backend").rglob("*.py"), *Path(__file__).parent.glob("*.py")]:
        try:
            ast.parse(path.read_text(), filename=str(path.relative_to(ROOT)))
        except SyntaxError as exc:
            errors.append(str(exc))
    config = configparser.ConfigParser()
    config.read(ROOT / "backend/pytest.ini")
    patterns = config.get("pytest", "python_files", fallback="").split()
    if "eval_*.py" not in patterns or config.get("pytest", "testpaths") != "tests":
        errors.append("Keep semantic eval discovery explicit and default testpaths=tests")
    for name in ("backend/.env.example", "frontend/.env.example"):
        if not (ROOT / name).exists():
            errors.append(f"Missing configuration example: {name}")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"PASS: {len(documents)} curated documents, {links} local links, Python syntax and config")


if __name__ == "__main__":
    main()
