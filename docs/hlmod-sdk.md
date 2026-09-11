---
sidebar_position: 6
---

# hlmod-sdk

[`sdk/`](https://github.com/N3rdL0rd/hlmod/tree/main/sdk) is a globally-installable CLI (`uv tool install sdk` from this
repo, or `pipx install`) that automates the workflow above:

```sh
hlmod-sdk install /path/to/game            # download and install hlmod, no GUI needed
hlmod-sdk list                             # every install hlmod-sdk or the GUI installer has made
hlmod-sdk new my_mod --install /path/to/game --dir ~/projects/my_mod
```

Every install (from `hlmod-sdk install` or the GUI installer) is recorded in
a per-user registry keyed by resolved path (`~/.config/hlmod/installs.json`
on Linux, `~/Library/Application Support/hlmod` on macOS, `%APPDATA%\hlmod`
on Windows). `hlmod-sdk new` reads that registry to scaffold a project
exactly as described above - `pyrightconfig.json` pointing at the install's
`mods/`, a starter mod file, and a README - for any install it knows about,
without needing to remember or retype paths.
