---
sidebar_position: 12
---

# GC controls

`hlmod.gc_major()` forces a full collection; `hlmod.gc_stats()` returns a
dict of `total_allocated`/`allocation_count`/`current_memory`;
`hlmod.gc_enable(bool)` toggles collection without stopping allocation.
`hlmod.is_gc_ptr(ptr)`/`hlmod.gc_memsize(ptr)` report whether an `HlPtr` is
GC-managed and its allocation size, for diagnosing memory pressure from a
mod without an external profiler attached.
