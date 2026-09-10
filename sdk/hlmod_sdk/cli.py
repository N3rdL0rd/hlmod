"""hlmod-sdk: install hlmod, discover registered installs, and scaffold new
mod projects for them - all from one CLI, no GUI required."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .installer import (
    InstallCallbacks,
    InstallCancelled,
    InstallError,
    TWEAK_ALIASES,
    default_build_types,
    install,
)
from .registry import find_install, list_installs
from .scaffold import scaffold


def cmd_install(args: argparse.Namespace) -> int:
    build_types = default_build_types()
    build_type = build_types.get(args.type)
    if build_type is None:
        print(f"error: unknown build type {args.type!r}; choose from: {', '.join(build_types)}", file=sys.stderr)
        return 1

    tweaks = set()
    for name in args.tweak or ():
        tweak = TWEAK_ALIASES.get(name)
        if tweak is None:
            print(f"error: unknown tweak {name!r}; choose from: {', '.join(TWEAK_ALIASES)}", file=sys.stderr)
            return 1
        tweaks.add(tweak)

    os.makedirs(args.directory, exist_ok=True)

    last_percent = [-1]

    def on_status(text: str) -> None:
        if last_percent[0] != -1:
            print()
            last_percent[0] = -1
        print(f"[hlmod-sdk] {text}")

    def on_progress(percent: int) -> None:
        if percent == last_percent[0]:
            return
        last_percent[0] = percent
        print(f"\r[hlmod-sdk] {percent}%", end="", flush=True)

    callbacks = InstallCallbacks(on_status=on_status, on_progress=on_progress)
    try:
        install(
            str(args.directory), build_type, version=args.version,
            tweaks=tweaks, auto_detect=not args.no_auto_detect, callbacks=callbacks,
        )
    except (InstallError, InstallCancelled) as error:
        if last_percent[0] != -1:
            print()
        print(f"error: {error}", file=sys.stderr)
        return 1
    if last_percent[0] != -1:
        print()
    print(f"Installed hlmod ({build_type}) into {args.directory}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    installs = list_installs()
    if not installs:
        print("No hlmod installs are registered. Run `hlmod-sdk install` first.")
        return 1
    for index, entry in enumerate(installs, start=1):
        print(f"{index}. {entry.path}")
        print(f"   build: {entry.build_type}  version: {entry.version[:7]}  installed: {entry.installed_at}")
    return 0


def cmd_new(args: argparse.Namespace) -> int:
    installs = list_installs()
    if args.install:
        try:
            target = find_install(args.install, installs)
        except LookupError as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
    elif len(installs) == 1:
        target = installs[0]
    elif not installs:
        print("error: no hlmod installs are registered. Run `hlmod-sdk install` first.", file=sys.stderr)
        return 1
    else:
        print("error: multiple hlmod installs are registered; pick one with --install:", file=sys.stderr)
        for index, candidate in enumerate(installs, start=1):
            print(f"  {index}. {candidate.path}", file=sys.stderr)
        return 1

    output_dir = args.dir or (Path.cwd() / args.name)
    if output_dir.exists():
        print(f"error: {output_dir} already exists", file=sys.stderr)
        return 1
    try:
        written = scaffold(args.name, target, output_dir)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Created mod project for {target.path} in {output_dir}:")
    for path in written:
        print(f"  {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hlmod-sdk", description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    install_parser = subparsers.add_parser("install", help="Download and install hlmod into a directory")
    install_parser.add_argument("directory", type=Path, help="Target game directory")
    install_parser.add_argument("--type", default=next(iter(default_build_types())),
                                 help=f"Build type, one of: {', '.join(default_build_types())}")
    install_parser.add_argument("--version", default="latest", help="'latest' or a specific git commit SHA")
    install_parser.add_argument("--tweak", action="append",
                                 help=f"Manually apply a tweak (repeatable), one of: {', '.join(TWEAK_ALIASES)}")
    install_parser.add_argument("--no-auto-detect", action="store_true",
                                 help="Disable tweak auto-detection; apply only --tweak selections")
    install_parser.set_defaults(func=cmd_install)

    list_parser = subparsers.add_parser("list", help="List registered hlmod installs")
    list_parser.set_defaults(func=cmd_list)

    new_parser = subparsers.add_parser("new", help="Scaffold a new mod project for a registered install")
    new_parser.add_argument("name", help="Mod name/id")
    new_parser.add_argument("--install", help="Target install: index from `list`, exact path, or a path substring")
    new_parser.add_argument("--dir", type=Path, default=None, help="Output directory (default: ./<name>)")
    new_parser.set_defaults(func=cmd_new)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
