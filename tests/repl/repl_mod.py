"""Registers one real native hook so the REPL's `hooks` command has live
registry state to report, not just the trivial empty case."""

MOD_INFO = {"id": "repl_mod", "dependencies": []}

import hlmod
from modcore import hook


@hook(hlmod.findex_for_name("$ReplFixture.target"))
def on_target(context, x):
    return context.call_next(x)
