---
sidebar_position: 9
---

# Harmony-style patches

`modcore.prefix_hook`/`postfix_hook`/`patch` install ordinary entries on the
same per-findex chain `hook()` uses, so plain hooks and patches on one target
interleave by priority:

```python
from modcore import patch, postfix_hook, prefix_hook

@prefix_hook(Weapon.create, priority=10)
def reject_locked(hero, item):
    if not hero.hasUnlocked(item):
        return False  # skip the original and every lower-priority hook/patch

@postfix_hook(Weapon.create, priority=0)
def log_result(result, hero, item):
    log(f"created {result}")

@patch(Weapon.create, priority=5)
class DoubleDamage:
    @staticmethod
    def postfix(result, hero, item):
        result.damage *= 2
```

A prefix returning `False` skips the rest of the chain for its own link
(neither lower-priority entries nor the original run); returning a tuple
replaces the positional arguments seen downstream; `None` continues
unchanged. A postfix's non-`None` return replaces the result. This composes
strictly (each patch wraps the *rest of the chain*, not an independent flat
list), which is narrower than C# Harmony's model but shares its ergonomics
and its one-hook-chain-per-target guarantee with DCCM's HarmonyX bridge.
