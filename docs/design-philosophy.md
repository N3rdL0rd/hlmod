---
sidebar_position: 16
---

# Design philosophy

- Modify the JIT compiler as LITTLE as possible. The more assembly we generate, the more unstable the VM becomes. Keep your ASM short, and write trampolines to C instead of full routines.
- The end user shouldn't have to memorize internal HL incantations to be able to write a basic mod. When in doubt, cast to and from a similar builtin Python class rather than write a full wrapper that may have incompatibilities with Python's `std`.
- Keep low-level APIs on the C side, then wrap them in nice Pythonic functions in `modcore`. For example, `hlmod.register_hook` is wrapped by a Pythonic decorator in `modcore.hook`.
