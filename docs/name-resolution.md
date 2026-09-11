---
sidebar_position: 11
---

# Resolving names to indices

`hlmod.findex_for_name("$Class.method")` resolves a bytecode function; the
companion `hlmod.type_index_for_name("Class")` resolves an obj/struct/enum
type the same way, for `alloc_obj`, `create_subclass`, `enum_new`, and
anywhere else a type index is otherwise a hardcoded magic number. Both raise
rather than guess when nothing matches (`KeyError` for a missing type,
`NameError` for a missing function).
