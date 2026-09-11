---
sidebar_position: 18
---

# What's changed upstream

In the HL VM, a few fixes and tweaks have been made or merged from upstream PRs:

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
