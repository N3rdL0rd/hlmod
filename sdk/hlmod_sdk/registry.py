"""Cross-platform hlmod install registry.

`hlmod_sdk.installer.install()` writes one entry here per successful install,
keyed by the install's resolved absolute path. `hlmod-sdk list`/`hlmod-sdk new`
read the same file to discover installs and scaffold mod projects for them.

Schema (schema_version 1):
{
  "schema_version": 1,
  "installs": {
    "<absolute install path>": {
      "mods_dir": "<absolute path to mods/ inside the install>",
      "version": "<git commit sha installed>",
      "build_type": "<e.g. Linux-gcc-Release>",
      "installed_at": "<ISO-8601 UTC timestamp>"
    },
    ...
  }
}
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
REGISTRY_FILENAME = "installs.json"


def config_dir(environ: dict | None = None, platform: str | None = None) -> Path:
    """The platform-conventional per-user config directory for hlmod."""
    env = environ if environ is not None else os.environ
    plat = platform if platform is not None else sys.platform
    if plat == "win32":
        base = env.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "hlmod"
    if plat == "darwin":
        return Path.home() / "Library" / "Application Support" / "hlmod"
    base = env.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "hlmod"


def registry_path(environ: dict | None = None, platform: str | None = None) -> Path:
    return config_dir(environ, platform) / REGISTRY_FILENAME


def _load_raw(path: Path) -> dict:
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"schema_version": SCHEMA_VERSION, "installs": {}}
    if not isinstance(data, dict) or not isinstance(data.get("installs"), dict):
        return {"schema_version": SCHEMA_VERSION, "installs": {}}
    return data


def record_install(install_path: str, *, version: str, build_type: str, path: Path | None = None) -> None:
    """Adds or updates one install entry, keyed by its resolved absolute path."""
    resolved = str(Path(install_path).resolve())
    reg_path = path or registry_path()
    reg_path.parent.mkdir(parents=True, exist_ok=True)
    data = _load_raw(reg_path)
    data["schema_version"] = SCHEMA_VERSION
    data["installs"][resolved] = {
        "mods_dir": str(Path(resolved) / "mods"),
        "version": version,
        "build_type": build_type,
        "installed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    tmp_path = reg_path.with_suffix(reg_path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    tmp_path.replace(reg_path)


@dataclass(frozen=True)
class Install:
    path: str
    mods_dir: str
    version: str
    build_type: str
    installed_at: str


def list_installs(path: Path | None = None) -> list[Install]:
    reg_path = path or registry_path()
    data = _load_raw(reg_path)
    result = []
    for install_path, entry in data["installs"].items():
        if not isinstance(entry, dict):
            continue
        result.append(Install(
            path=install_path,
            mods_dir=entry.get("mods_dir", str(Path(install_path) / "mods")),
            version=entry.get("version", "unknown"),
            build_type=entry.get("build_type", "unknown"),
            installed_at=entry.get("installed_at", "unknown"),
        ))
    result.sort(key=lambda i: i.installed_at, reverse=True)
    return result


def find_install(selector: str, installs: list[Install] | None = None, path: Path | None = None) -> Install:
    """Resolves `selector` to one Install: a 1-based index into `list_installs()`
    order, an exact path, or a unique case-insensitive substring of the path."""
    installs = installs if installs is not None else list_installs(path)
    if not installs:
        raise LookupError("No hlmod installs are registered. Run `hlmod-sdk install` first.")
    if selector.isdigit():
        index = int(selector)
        if 1 <= index <= len(installs):
            return installs[index - 1]
        raise LookupError(f"No install at index {index}; there are {len(installs)} registered.")
    exact = [i for i in installs if str(Path(i.path)) == str(Path(selector))]
    if exact:
        return exact[0]
    matches = [i for i in installs if selector.lower() in i.path.lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise LookupError(f"{selector!r} matches multiple installs; be more specific: " + ", ".join(m.path for m in matches))
    raise LookupError(f"No registered install matches {selector!r}.")
