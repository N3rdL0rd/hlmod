"""
Converts hlprofile.dump → hlprofile.json (Chrome DevTools format).
Drag the .json into Chrome DevTools > Performance tab, or open ui.perfetto.dev.

Usage:
    python convert_profile.py [hlprofile.dump] [--min-time-ms N]
"""

import subprocess
import sys
import os

HAXE       = "haxe"
PROFILE_GEN_CP = os.path.join(os.path.dirname(__file__), "hlmod-hl", "other", "haxelib")

def main():
    dump_file = "hlprofile.dump"
    min_time_ms = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--min-time-ms" and i + 1 < len(args):
            min_time_ms = args[i + 1]
            i += 2
        else:
            dump_file = args[i]
            i += 1

    if not os.path.exists(dump_file):
        print(f"ERROR: {dump_file} not found.", file=sys.stderr)
        sys.exit(1)

    out_file = os.path.splitext(dump_file)[0] + ".json"

    cmd = [HAXE, "--run", "hlprof.ProfileGen", "-cp", PROFILE_GEN_CP]
    if min_time_ms:
        cmd += ["--min-time-ms", min_time_ms]
    cmd += [dump_file, "-o", out_file]

    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode == 0:
        print(f"\nDone. Open {out_file} in Chrome DevTools > Performance tab.")
    else:
        print(f"\nFailed (exit {result.returncode}).", file=sys.stderr)
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
