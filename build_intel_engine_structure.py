"""Utility script to scaffold the modular AI-driven OSINT and PI intelligence engine."""
from pathlib import Path

BASE = Path(__file__).parent / "intel_engine"

DIRECTORIES = {
    BASE: "Root package tying together the modular OSINT and PI intelligence engine assets.",
    BASE / "core": "Hosts the central orchestrator, shared utilities, and baseline logic for running intelligence workflows.",
    BASE / "modules": "Contains independent intelligence modules that plug into the core orchestration layer.",
    BASE / "schemas": "Stores JSON schema contracts that define the input/output payloads between modules and services.",
    BASE / "ai": "Provides AI-driven planning, decision making, and controller components that guide investigations.",
    BASE / "reports": "Holds generated exports, summaries, and other human-readable reporting artifacts.",
    BASE / "tests": "Includes automated test suites verifying module contracts and engine behaviours.",
}


def ensure_directory(path: Path) -> None:
    """Create directory and __init__.py placeholder."""
    path.mkdir(parents=True, exist_ok=True)
    init_file = path / "__init__.py"
    init_file.touch(exist_ok=True)


def write_readme() -> None:
    lines = ["# Intel Engine Structure", "",]
    for directory, description in DIRECTORIES.items():
        folder_name = directory.relative_to(BASE.parent)
        lines.append(f"- {folder_name}: {description}")
    (BASE / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    for directory in DIRECTORIES:
        ensure_directory(directory)
    write_readme()


if __name__ == "__main__":
    main()
