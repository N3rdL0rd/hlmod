"""
Measures the per-call overhead that hlmod hook interception adds.
Runs Benchmark.hl twice via hlmod-hl: once baseline (no hook installed),
once with a minimal passthrough hook. Parses each run's BENCH_RESULT line.
"""

import subprocess
import re
import statistics
import os
import sys

HL_EXE = "./hlmod-hl/build/bin/hl.exe"
HL_FILE = "Benchmark.hl"
TRIALS = 5

RESULT_RE = re.compile(r"BENCH_RESULT:([\d.e+]+)\|sink=(-?\d+)")


def decode_hl_stdout(raw: bytes) -> str:
    # HL on Windows mixes C printf (ASCII, 1 byte/char) with Haxe Sys.println
    # (UTF-16 LE, 2 bytes/char). Stripping null bytes collapses both to ASCII.
    return raw.replace(b"\x00", b"").decode("utf-8", errors="replace")

ENV_BASE = {**os.environ, "PYTHONPATH": ""}


def run_one(hook: bool, trial: int) -> float | None:
    env = {**ENV_BASE}
    if hook:
        env["HLMOD_BENCH_HOOK"] = "1"
    else:
        env.pop("HLMOD_BENCH_HOOK", None)

    label = "hooked  " if hook else "baseline"
    try:
        result = subprocess.run(
            [HL_EXE, HL_FILE],
            capture_output=True,
            env=env,
            cwd=os.path.dirname(os.path.abspath(__file__)) or ".",
        )
    except FileNotFoundError:
        print(f"  ERROR: hl.exe not found at {HL_EXE}", file=sys.stderr)
        return None

    stdout = decode_hl_stdout(result.stdout)
    m = RESULT_RE.search(stdout)
    if m:
        ns = float(m.group(1))
        print(f"  trial {trial} [{label}]: {ns:.2f} ns/call")
        return ns
    else:
        print(f"  trial {trial} [{label}]: no BENCH_RESULT found", file=sys.stderr)
        print("  stdout tail:", stdout[-300:], file=sys.stderr)
        return None


def main():
    print(f"hlmod hook overhead benchmark — {TRIALS} trials each\n")

    baseline_times: list[float] = []
    hooked_times: list[float] = []

    print("--- Baseline (no hook) ---")
    for i in range(1, TRIALS + 1):
        t = run_one(hook=False, trial=i)
        if t is not None:
            baseline_times.append(t)

    print("\n--- Hooked (passthrough) ---")
    for i in range(1, TRIALS + 1):
        t = run_one(hook=True, trial=i)
        if t is not None:
            hooked_times.append(t)

    print("\n--- Results ---")
    if not baseline_times or not hooked_times:
        print("Not enough data to compute overhead.")
        return

    base_mean = statistics.mean(baseline_times)
    hooked_mean = statistics.mean(hooked_times)
    overhead_ns = hooked_mean - base_mean
    overhead_us = overhead_ns / 1000

    def fmt(times: list[float], label: str):
        mean = statistics.mean(times)
        if len(times) > 1:
            sd = statistics.stdev(times)
            print(f"  {label}: {mean:.2f} ns/call  (±{sd:.2f}  median {statistics.median(times):.2f})")
        else:
            print(f"  {label}: {mean:.2f} ns/call")

    fmt(baseline_times, "baseline")
    fmt(hooked_times,   "hooked  ")
    print(f"\n  Hook overhead: {overhead_ns:.2f} ns/call  ({overhead_us:.2f} µs/call)")


if __name__ == "__main__":
    main()
