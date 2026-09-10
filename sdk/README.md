# hlmod-sdk

A CLI companion to [hlmod](https://github.com/N3rdL0rd/hlmod). Installs hlmod
into any game directory, and scaffolds new mod projects that target any
install it knows about - all without the GUI installer.

## Install

```sh
uv tool install hlmod-sdk
# or: pipx install hlmod-sdk
```

## Usage

Install hlmod into a game directory (defaults to the platform's typical
release build; override with `--type`):

```sh
hlmod-sdk install /path/to/game
hlmod-sdk install /path/to/game --type gcc-debug --version <commit-sha>
hlmod-sdk install /path/to/game --no-auto-detect --tweak dcmod --tweak steam
```

Every successful install is recorded in a per-user registry (`installs.json`
under the platform's config directory - `~/.config/hlmod` on Linux,
`~/Library/Application Support/hlmod` on macOS, `%APPDATA%\hlmod` on
Windows), keyed by the install's resolved path. This is the same registry the
GUI installer writes to, so installs made either way show up in both.

List registered installs:

```sh
hlmod-sdk list
```

Scaffold a new mod project targeting one of them (auto-selected if only one
is registered, otherwise pick by index, exact path, or a unique substring):

```sh
hlmod-sdk new my_mod
hlmod-sdk new my_mod --install 2
hlmod-sdk new my_mod --install /path/to/game --dir ~/projects/my_mod
```

This writes a `pyrightconfig.json` pointing at the target install's `mods/`
directory (so editor intellisense for `stubs`/`modcore`/`hlmod` works from
the new project directory without copying anything into the game's own
`mods/` folder), a starter mod file, and a README explaining how to load it
via `HLMOD_EXTRA_MODS` without touching the game's install at all.
