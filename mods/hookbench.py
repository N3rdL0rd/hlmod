MOD_INFO = {
    "id": "hookbench",
    "name": "Hook Overhead Benchmark",
    "description": "Installs a minimal passthrough hook on Benchmark.work to measure hlmod hook overhead.",
    "version": "0.0.1",
    "dependencies": ["modcore"],
    "enabled": False,
}

import os
from modcore import hook

def initialize():
    pass

if os.environ.get("HLMOD_BENCH_HOOK"):
    @hook("$Benchmark.work")
    def _hook_work(h, x: int) -> int:
        return h.call_original(x)
