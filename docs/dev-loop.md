---
sidebar_position: 4
---

# Dev loop

Mods are plain Python with no compile step, so the only friction in local
iteration is noticing an edit and restarting `hl` by hand. `tools/dev.py`
closes that gap:

```sh
just dev game.hl      # or: python3 tools/dev.py game.hl --hl path/to/hl
```

It launches `hl game.hl`, watches `mods/**/*.py` (excluding the generated
`mods/stubs/` tree) plus `hlmod.toml`/`typing_overlays.json`, and restarts the
process on any change. This is a local iteration tool, not packaging: it does
not build anything and has no relation to the installer or the nightly build.
