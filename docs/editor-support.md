---
sidebar_position: 13
---

# Editor support

Generated proxies ship with `.pyi` interfaces, so a type checker infers
`BridgeBase(1)` as `BridgeBase`, checks constructor and method arguments, field
types, overrides, hook signatures and event payloads. Point your editor at the
`mods` directory. Where the bytecode has erased detail, such as native array
element types, `mods/typing_overlays.json` supplies annotations that apply only
to the generated interfaces:

```json
{"version": 1,
 "imports": {"NativeArray": "hlobj.HlArray"},
 "types": {"pr.Game": {"fields": {"players": "NativeArray[int] | None"}}}}
```
