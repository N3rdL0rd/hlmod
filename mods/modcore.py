"""
Common modding routines for Hashlink games.
"""

import inspect
import hlmod
from typing import List, Callable
import stubs

MOD_INFO = {
    "id": "modcore",
    "name": "hlmod Modding Core",
    "description": "Core utilities, tools, and functions for instrumenting Hashlink.",
    "version": "0.0.1",
    "dependencies": []
}

def hook(target: str|int|List[int]):
    """
    A decorator that registers the decorated function as a hook for a given
    Hashlink function index (findex).

    Usage:
    ```
    @hook(296)
    def my_hook(hook, *args):
        # ... your hook logic ...
        hook.call_original(*args)
    ```
    """
    if not isinstance(target, (int, list, str)):
        raise TypeError("The @hook decorator requires an integer findex or a list of integer findexes.")

    def decorator(func: Callable):
        if isinstance(target, int):
            hlmod.register_hook(target, func) # pyright: ignore[reportAttributeAccessIssue]
        elif isinstance(target, str):
            fidx = hlmod.findex_for_name(target)
            print(f"[hlmod DEBUG] Hooking {target} to {fidx} with {func.__name__}")
            hlmod.register_hook(fidx, func)
        else:
            for fidx in target:
                hlmod.register_hook(fidx, func) # pyright: ignore[reportAttributeAccessIssue]
        return func
    
    return decorator

