---
sidebar_position: 12
---

# GC controls

`hlmod` exposes five thin bindings onto HashLink's own garbage collector: `gc_major()`, `gc_stats()`, `gc_enable(bool)`, `is_gc_ptr(ptr)`, and `gc_memsize(ptr)`. All five talk to *HL's* GC - the native mark-and-sweep collector that owns every `vobj`, `varray`, `vdynamic`, and byte buffer the HL runtime allocates. This is not CPython's GC. Your Python objects - the `HlObjectMeta`-generated wrapper instances, the plain Python lists and dicts a mod's own code creates, the `HlPtr` handles themselves - are managed by CPython's reference counting and cycle collector exactly as they would be in any other embedded Python, and none of these five functions touch it. `hlmod.gc_enable(False)` does not pause Python's collector, `gc_stats()` does not report Python heap size, and disabling one has zero effect on the other. They are two separate collectors, running two separate allocators, for two separate heaps, and the only thing they have in common is the letters "GC."

## Where the numbers come from

`hl_gc_stats()` (implemented in `gc.c`, exported through `hlmod_py_gc_stats` in `hlmod_api.c`) reads three counters straight off the collector's internal `gc_stats` struct:

- **`total_allocated`** - the cumulative number of bytes ever requested from the GC page allocator, since the process started. It only goes up. A page that gets freed during a major collection doesn't get subtracted back out of this number; it's a lifetime counter, not a live-memory figure.
- **`allocation_count`** - the cumulative number of individual GC allocations, same lifetime-counter behavior as above.
- **`current_memory`** - the number of bytes currently held in GC pages (`gc_stats.pages_total_memory`). This one actually moves in both directions: it grows when the allocator maps a new page from the OS, and it shrinks when a major collection finds a page with nothing left alive in it and hands it back. This is the number that tells you what the collector is holding right now.

```
>>> hlmod.gc_stats()
{'total_allocated': 41823744, 'allocation_count': 128841, 'current_memory': 52428800}
```

(See [REPL](./repl.md) for how to get an interactive prompt inside a running game to try this against.)

`gc_major()` calls `hl_gc_major()`, which grabs the GC's global lock and runs a full stop-the-world mark-and-sweep unconditionally - it does not check whether the collector is enabled, more on that below. `is_gc_ptr(ptr)` and `gc_memsize(ptr)` both take an `HlPtr` and answer per-pointer questions: whether the address falls inside a page the GC owns, and if so, how many bytes the allocator actually reserved for that block (`gc_memsize` returns `None` for a pointer that isn't GC-managed - a stack address or something living outside the collector's pages entirely).

## Automatic collection, and what disabling it actually does

HL doesn't collect on a timer. Every allocation runs `gc_check_mark()`, which compares bytes and allocation-count deltas since the last mark against the page pool's current size (scaled by a threshold), and triggers a major collection the moment the growth looks large enough relative to what's already resident. `gc_enable(False)` flips a single flag (`gc_is_active`) that this check reads - when it's false, `gc_check_mark()` never fires `gc_major()` no matter how much the process allocates. It does not stop allocation itself; requests keep succeeding, pages keep getting mapped, `total_allocated` and `current_memory` both keep climbing, and nothing comes back to look for garbage until you either call `gc_enable(True)` again or invoke `gc_major()` by hand (which, as noted above, ignores the flag entirely and always runs).

That's the tradeoff, stated plainly: `gc_enable(False)` gets you a stretch of execution with zero mark-and-sweep pauses, which is exactly what you want when you're profiling allocation-heavy code and don't want a GC pause landing in the middle of your timing window and making a well-behaved function look like the slow one. The risk is that memory really does grow without bound for as long as it stays off - there's no backstop, no emergency collection when memory pressure gets bad, nothing. If the code under test is actually allocation-heavy, leaving `gc_enable(False)` set past the measurement window is a good way to turn a profiling session into an out-of-memory kill. Turn it back on (or call `gc_major()` explicitly) as soon as you have the numbers you came for.

```python
import hlmod

hlmod.gc_enable(False)
try:
    run_the_suspicious_hot_path()
finally:
    hlmod.gc_enable(True)
    hlmod.gc_major()  # catch up on whatever accumulated while collection was off
```

## Using gc_stats() to hunt a leak

The lifetime counters (`total_allocated`, `allocation_count`) aren't much use for spotting a leak on their own - they only ever increase, leak or no leak. `current_memory`, taken before and after a forced major collection, is the useful signal: force a collection so you know you're looking at live memory rather than "stuff not yet noticed", snapshot it, run the operation under suspicion, force another collection, and compare.

```python
import hlmod

hlmod.gc_major()
before = hlmod.gc_stats()["current_memory"]

for _ in range(1000):
    run_suspected_leaky_operation()

hlmod.gc_major()
after = hlmod.gc_stats()["current_memory"]

print(f"current_memory delta after 1000 iterations: {after - before} bytes")
```

A delta that stays roughly flat across repeated runs of the loop means whatever those iterations allocated got collected as expected. A delta that keeps climbing in proportion to the iteration count means something in that operation is holding a reference the collector can't drop - a closure kept alive in a hook table, a growing array somewhere, a root that never gets cleared. `is_gc_ptr()` and `gc_memsize()` are the next step down from there: once you have an `HlPtr` you suspect is the culprit, `gc_memsize()` tells you how big the allocation actually is, which is usually enough to point at which field or container is responsible.

:::note
Because `gc_major()` is a genuine stop-the-world stop-and-mark - the whole process, not just an HL thread - do not call it from a hot path or a hook that runs every frame. Its home is one-off diagnostics from a REPL session or the occasional profiling script, not something you leave running inside a mod's normal execution.
:::

## See also

- [REPL](./repl.md) - the easiest place to actually call these interactively against a running game.
- [Design philosophy](./design-philosophy.md) - why `hlmod.gc_major()` and friends are raw, unergonomic bindings instead of something `modcore` wraps.
