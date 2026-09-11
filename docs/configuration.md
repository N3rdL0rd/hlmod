---
sidebar_position: 15
---

# Global configuration

`modcore.config` stores mod settings in one `hlmod.toml` file, one table per
mod, deliberately not JSON:

```python
from modcore import config

settings = config.section(defaults={"volume": 5, "show_hud": True})
settings["volume"] = 8   # marks the file dirty
```

`section()` defaults to the currently-loading mod's id and fills in any key
missing from the file (so a fresh install always ends up with a complete,
saved config), without touching keys a user already changed. The file is
written automatically when mods shut down, or immediately via
`config.save()`. `tomllib` (stdlib since Python 3.11) reads the file back;
since it's read-only, hlmod ships a small writer (`modcore._toml_writer`)
covering the value shapes a config file actually needs - bool, int, float,
str, list, and nested tables - rather than pull in a third-party TOML
dependency for round-tripping plain data.
