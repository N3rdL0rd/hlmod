"""dcmod's mutable runtime state.

Tunable settings live in `dcmod.settings` (backed by `hlmod.toml`); this module
is only for values discovered or derived while the game is running.
"""

from . import MOD_INFO
import hlmod
from stubs import ui
from typing import Optional

CONSOLE: Optional[ui.Console] = None
"""The game's debug console, set once `ui.Console`'s constructor has run."""

BUILD_TEXT = f"dcmod {MOD_INFO["version"]} (hlmod {hlmod.version})."
"""Appended to the main-menu build string when `settings.custom_build_text`."""