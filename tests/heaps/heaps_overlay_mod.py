"""Exercises `mods/heaps` end-to-end: registers a loose-file overlay
directory and, once the fixture's own `main()` has run (so `hxd.Res.loader`
is actually set), verifies that a path present in the overlay is served from
disk while a path absent from it still falls through to the base game's
`GameFileSystem`."""

from pathlib import Path

import hlmod
import heaps

MOD_INFO = {"id": "heaps_overlay_test", "dependencies": ["heaps"]}


def initialize() -> None:
    heaps.add_overlay_dir(Path(__file__).parent / "overlay_res")

    from modcore import postfix_hook
    postfix_hook(hlmod.findex_for_name("$HeapsFixture.main"))(_check)


def _check(result, *args) -> None:
    load = hlmod.findex_for_name("$HeapsFixture.loadPath")
    overridden = hlmod.call(load, ("title.txt",))
    passthrough = hlmod.call(load, ("credits.txt",))

    assert overridden == "Overridden Title From Mod", overridden
    assert passthrough == "Base Game Credits", passthrough

    print("HEAPS_OVERLAY_OVERRIDE_OK", flush=True)
    print("HEAPS_OVERLAY_PASSTHROUGH_OK", flush=True)
