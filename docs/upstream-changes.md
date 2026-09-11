---
sidebar_position: 18
---

# What's changed upstream

`hlmod-hl` is a hard fork of [HashLink](https://github.com/HaxeFoundation/hashlink), not a submodule pinned to a tag and left alone - Python embedding touches the JIT, the GC, and the thread model closely enough that living entirely off upstream releases isn't really an option. That cuts both ways: hlmod carries its own patches indefinitely, but it also periodically reviews upstream `master` and pulls back the small, self-contained bugfixes that landed there, so this fork doesn't slowly drift into carrying bugs upstream already solved. Large or risky upstream changes (new backends, platform rework) are deliberately left for a dedicated look rather than merged opportunistically.

The following fixes and tweaks have been pulled from or merged upstream so far:

- HaxeFoundation/hashlink#795 (Add newline to `--version` print)
- HaxeFoundation/hashlink#482 and HaxeFoundation/hashlink#831 (Fix MinGW build)
- HaxeFoundation/hashlink#856 (Fix `hl_dyni32` for systems with unsigned `char`,
  plus its `2cd7a78` prerequisite optimizing small `null<int>` allocation)
- HaxeFoundation/hashlink#940 (Fix `Reflect.compare` on overflow values)
- `0da6cb5` (Fixed a potential buffer overflow when compact align passes bounds)
- HaxeFoundation/hashlink#867 (Fix a GC segfault from allocation tracking)
- HaxeFoundation/hashlink#872 (Fix `Single` large-value printing to an empty string)
- HaxeFoundation/hashlink#868 (Add `hl_gc_safepoint`)
- `cab50ba` (Fixed a `check_same_type` stack overflow with hot-reloaded plugins)
- HaxeFoundation/hashlink#949 (Fix x86 register names leaking into aarch64 profiles)
- HaxeFoundation/hashlink#870 (Fix a null access in `ProfileGen.hx` on a
  finished thread, the flamegraph converter referenced above)

None of these are hlmod-specific fixes dressed up as upstream contributions - they're bugs in HashLink itself, several of which would bite a Python-embedded VM harder than a normal one (GC segfaults and stack overflows are not things you want compounding with a second garbage-collected runtime in the same process), and all of which are equally real for anyone running vanilla HashLink.
