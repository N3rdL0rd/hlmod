---
sidebar_position: 17
---

# Known issues

- Anything that depends on older versions of HL's DirectX APIs will crash and sometimes even segfault.
  - Dead Cells provides an OpenGL-only executable, use that if possible.
- Native hooking is x86-64 only and requires hlmod to recognize a safely
  overwritable instruction sequence at the target's entry point; a native
  compiled with an unrecognized prologue raises `RuntimeError` instead of
  installing a hook. This is a deliberate fail-closed limit, not a bug: see
  [Hooking native functions](./native-hooks.md).
