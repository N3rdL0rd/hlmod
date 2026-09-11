---
sidebar_position: 10
---

# Hooking native functions

`hook()`/`register_hook()` also accept the findex of an `@:hlNative`
function, resolved with `hlmod.native_findex(lib, name)`:

```python
from modcore import hook
import hlmod

@hook(hlmod.native_findex("std", "sys_time"))
def frozen_clock(context):
    return 0.0
```

Bytecode functions are hookable because their JIT-compiled bodies carry an
injected check; natives are raw C pointers with no such body, and every
caller bakes their address in as a constant at JIT-compile time. The first
hook on a native lazily installs a small x86-64 inline detour at its entry
point instead, so `call_next`/`call_original` and hook composition behave
identically either way. Installing the detour requires hlmod to recognize a
safely-overwritable instruction sequence at the native's entry; if it can't,
hooking raises `RuntimeError` rather than guessing at an instruction
boundary. x86-64 only, matching hlmod's supported JIT targets.
