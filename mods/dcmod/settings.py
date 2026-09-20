"""dcmod's persistent settings, stored in the `[dcmod]` table of `hlmod.toml`.

Every setting is read back out of the live config document on each access, so
flipping one from the REPL (or from another mod) takes effect immediately and
is written to disk by `modcore.config`'s autosave at shutdown. Defaults are
declared once, here, and filled into the file on first run.

`hlmod.toml` is meant to be hand-edited, which means a value can arrive with
the wrong type. A mistyped setting falls back to its default and logs once,
rather than handing a `str` to a native call that wants an `Int` and failing
somewhere much less obvious.
"""

from __future__ import annotations

import logging
from typing import Generic, TypeVar

from modcore import config

_log = logging.getLogger("dcmod.settings")

T = TypeVar("T", bool, int, str)


class _Setting(Generic[T]):
    """One typed key in dcmod's config table, resolved live on every read."""

    __slots__ = ("_key", "_default", "_doc", "_complained")

    def __init__(self, default: T, doc: str) -> None:
        self._default = default
        self._doc = doc
        self._complained = False

    def __set_name__(self, owner: type, name: str) -> None:
        self._key = name

    @property
    def default(self) -> T:
        return self._default

    @property
    def doc(self) -> str:
        """What this setting does, for `hlmod.toml` documentation and tooling."""
        return self._doc

    def __get__(self, instance: Settings | None, owner: type | None = None) -> T:
        if instance is None:
            return self._default
        value = instance.section.get(self._key, self._default)
        # `type(...) is not` rather than isinstance: bool is a subclass of int,
        # so `remove_news = 1` would otherwise pass as a boolean.
        if type(value) is not type(self._default):
            if not self._complained:
                self._complained = True
                _log.warning("Config key [dcmod].%s should be %s, got %r; using %r",
                             self._key, type(self._default).__name__, value, self._default)
            return self._default
        return value

    def __set__(self, instance: Settings, value: T) -> None:
        instance.section[self._key] = value


class Settings:
    """Typed, live view onto dcmod's `hlmod.toml` table."""

    __slots__ = ("section",)

    predictable_stamp = _Setting(True, "Return a fixed value from "
                                 "`tools.PakUtils.getPakStampHash`, so changes to the game's "
                                 "version info don't invalidate your paks.")
    ingame_logs = _Setting(True, "Mirror dcmod and other mods' `log()` output into the "
                           "in-game debug console.")
    log_color = _Setting(0xFFFFFF, "Default color for mods' debug messages.")
    custom_build_text = _Setting(True, "Append `globals.BUILD_TEXT` to the build string on "
                                 "the main menu.")
    remove_news = _Setting(True, "Remove the update logo and the advertisement in the top "
                           "right corner of the main menu.")
    hide_controller_warning = _Setting(True, "Hide the \"we recommend playing with a "
                                       "controller\" warning on the main menu.")

    def __init__(self) -> None:
        # An explicit name, not the implicit `current_mod()` one, so importing
        # this module from the REPL or a test resolves the same table.
        self.section = config.section("dcmod", defaults={
            name: setting.default for name, setting in vars(type(self)).items()
            if isinstance(setting, _Setting)
        })


settings = Settings()
