from __future__ import annotations

from pathlib import Path


def load_prompt(prompts_dir: Path, version: str, filename: str) -> str:
    """Load a versioned prompt file shared by every agent's prompts/ package.

    Layout convention every agent follows: prompts/<version>/<filename>.
    """
    path = prompts_dir / version / filename
    if not path.is_file():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")
