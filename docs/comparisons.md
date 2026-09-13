---
sidebar_position: 20
---

# hlmod vs. Everything Else

There are two other things worth knowing about if you're evaluating hlmod: [Dead Cells Core Modding](https://github.com/dead-cells-core-modding/core) (DCCM), the other serious Hashlink modding framework, and [pyhl](https://github.com/N3rdL0rd/crashlink/tree/main/pyhl), hlmod's own ancestor. DCCM in particular is a mature, well-supported project that the existing Dead Cells modding community already trusts (and it also hosts a number of impressive mods, including a multiplayer implementation!), and hlmod owes it a fair amount of its own roadmap. This page is as best of a side-by-side comparison as I can muster.

| Aspect | hlmod | DCCM | pyhl | Winner |
|---|---|---|---|---|
| Scope | Any Hashlink game | Dead Cells, by design | Whatever bytecode crashlink's patcher was pointed at | - |
| Primary language | Python, small C core | C# / .NET | C (thin) + Python glue | - |
| Runtime model | CPython embedded in-process, forked `hl` | Hosted .NET runtime + generated typed proxies | Python loaded as an ordinary `.hdll` into a stock `hl` | - |
| GC integration | Deep - native peer table, GC-aware object wrapping | Managed by .NET's own marshalling layer | None - explicitly unintegrated, two independent GCs | hlmod/DCCM |
| Maturity | Young, actively shifting | Established, proven in the wild | Experimental, superseded by hlmod | DCCM |
| Community & docs | Small | Larger, Dead-Cells-specific, well-documented | None | DCCM |
| Platform support | Linux + Windows (MSVC/MinGW) + Roadmapped aarch64 and Mac support | Windows (MSVC only) primarily, experimental Linux | Linux + Windows | hlmod |
| IDE tooling | Pyright or other native Python typecheckers via stubgen stubs | Full Visual Studio/Rider IntelliSense via MDK stubs | None | DCCM* |
| Mod authoring | Single-file sriptable Python mods, or module-based mods with deeper controls | C# DLL with mod metadata compiled against MDK/GameProxy.dll | Hand-patch the target bytecode with crashlink's assembler first | hlmod |
| Bytecode/function hooking | Native detour + JIT trampoline chain, install anywhere | HarmonyX-style hooks via `HashlinkHookManager` | `intercept()` - a manually inserted call site, one at a time | hlmod/DCCM |
| Native hooking | x86-64 inline detour, hand-rolled | MonoMod-based `NativeHooks` | None | DCCM** |
| Hot reload | Yes | No (`Module<T>` throws on reconstruction) | No | hlmod |
| Native subclassing / interfaces | Yes, including brand-new interfaces | Yes, ordinary .NET subclassing | No object model at all | hlmod/DCCM |
| Config persistence | Built in (`Config<T>`, JSON, auto-save) | Built in (Pythonic dict-style TOML) | None | hlmod/DCCM |
| Asset/resource overlay | Generic, any Heaps game | Dead-Cells-bound, but ships real `.pak` build/diff/merge CLI too | None | Split*** |
| CastleDB / `hxbit` / i18n | None yet | All three, mature | None | DCCM |
| Live debugging | In-process TCP/socket REPL | dnSpy + pseudocode dump | `printf`-style debug logging only | hlmod/DCCM |
| Decompilation | Sister project [crashlink](https://n3rdl0rd.github.io/crashlink) | Decompiled sources + `GamePseudocode.dll` | Is a component *of* crashlink | hlmod/pyhl |
| Steam Workshop / publishing | None yet | `DCCMTool` upload/mount | None | DCCM |

\* .NET's IDE ecosystem has had decades to get IntelliSense right; hlmod's typing is dependent on your particular Python IDE and less battle-tested.

\** MonoMod is a far older, more field-tested detour engine than hlmod's own home-rolled x86-64 patcher, which is lazy and fails in edge cases often.

\*** hlmod's overlay needs zero per-game setup and works on any Heaps game; DCCM's is scoped to Dead Cells but comes with actual packing/merging tooling hlmod doesn't have yet.

