"""
Targeted profiler trigger: starts hlmod's sampling profiler when a specific
function is entered and stops it after a configurable number of calls.

Usage:
  1. Set TRIGGER_FUNC to the function you want to profile around.
  2. Adjust SAMPLES_PER_SEC and CALLS_TO_RECORD.
  3. Run the game and trigger the attack / action once.
  4. hlprofile.dump is written on the Nth call (and again at exit).
  5. Convert to Chrome JSON:
       haxe --run hlprof.ProfileGen -cp hlmod-hl/other/haxelib hlprofile.dump
     Then open the resulting .json in Chrome DevTools > Performance tab (drag & drop).
"""

MOD_INFO = {
    "id": "profiler_trigger",
    "name": "Targeted Profiler Trigger",
    "description": "Starts/stops the HL sampling profiler around a specific function call window.",
    "version": "0.0.1",
    "dependencies": ["modcore"],
    "enabled": True,
}

import hlmod
from modcore import hook

# --- Configuration ---
TRIGGER_FUNC   = "module.Class.method"    # function that starts the profiling window
SAMPLES_PER_SEC = 5000                    # higher = finer resolution, more overhead
CALLS_TO_RECORD = 1                       # stop after this many entries of TRIGGER_FUNC
# ---------------------

_call_count = 0
_profiling  = False


def initialize():
    pass


@hook(TRIGGER_FUNC)
def _profiler_trigger(h, *args):
    global _call_count, _profiling

    if not _profiling:
        _profiling = True
        _call_count = 0
        hlmod.profile_start(SAMPLES_PER_SEC)
        print(f"[profiler] started ({SAMPLES_PER_SEC} samples/s)")

    result = h.call_original(*args)

    _call_count += 1
    if _call_count >= CALLS_TO_RECORD:
        hlmod.profile_end()
        _profiling = False
        print(f"[profiler] stopped after {_call_count} call(s) — hlprofile.dump written")

    return result
