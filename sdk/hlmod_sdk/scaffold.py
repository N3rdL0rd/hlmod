"""Generates a starter mod project targeting one registered hlmod install."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .registry import Install

_SLUG_RE = re.compile(r"[^a-zA-Z0-9_]")


def slugify(name: str) -> str:
    slug = _SLUG_RE.sub("_", name).strip("_")
    if not slug:
        raise ValueError(f"{name!r} does not contain a usable identifier")
    if slug[0].isdigit():
        slug = f"_{slug}"
    return slug


def mod_source(mod_id: str) -> str:
    return (
        f'MOD_INFO = {{"id": "{mod_id}", "dependencies": []}}\n'
        "\n"
        "\n"
        "def initialize() -> None:\n"
        f'    print("[{mod_id}] loaded")\n'
    )


def pyright_config(mod_id: str, install: Install) -> str:
    return json.dumps({
        "include": [f"{mod_id}.py"],
        "extraPaths": [install.mods_dir],
        "pythonVersion": "3.12",
        "typeCheckingMode": "standard",
    }, indent=2) + "\n"


def readme(mod_id: str, install: Install, output_dir: Path) -> str:
    is_windows = install.build_type.startswith("Windows")
    launcher = "run_hlmod.bat" if is_windows else "run_hlmod.sh"
    return (
        f"# {mod_id}\n"
        "\n"
        f"An hlmod mod targeting `{install.path}`.\n"
        "\n"
        "## Editor support\n"
        "\n"
        "This directory ships a `pyrightconfig.json` pointing at the target install's\n"
        "`mods/` directory, so `from stubs...`, `from modcore import ...`, and\n"
        "`import hlmod` all resolve with full type checking.\n"
        "\n"
        "## Running\n"
        "\n"
        "Load this mod without copying it into the game's own `mods/` folder, by\n"
        "pointing `HLMOD_EXTRA_MODS` at this directory and launching the game's own\n"
        f"launcher (`{install.path}/{launcher}`) with its bytecode file as usual:\n"
        "\n"
        "```sh\n"
        f'HLMOD_EXTRA_MODS="{output_dir}" "{install.path}/{launcher}" <game>.hl\n'
        "```\n"
    )


def scaffold(mod_name: str, install: Install, output_dir: Path) -> list[Path]:
    """Writes a starter mod project into `output_dir`. Returns the written paths."""
    mod_id = slugify(mod_name)
    output_dir.mkdir(parents=True, exist_ok=False)
    output_dir = output_dir.resolve()
    written = []
    for filename, content in (
        (f"{mod_id}.py", mod_source(mod_id)),
        ("pyrightconfig.json", pyright_config(mod_id, install)),
        ("README.md", readme(mod_id, install, output_dir)),
    ):
        target = output_dir / filename
        target.write_text(content, encoding="utf-8")
        written.append(target)
    return written
