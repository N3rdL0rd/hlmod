"""
Common modding routines for Hashlink games.
"""

import inspect
import hlmod
from typing import List, Callable
import stubs
from os.path import isfile
import glob
from importlib import import_module

MOD_INFO = {
    "id": "modcore",
    "name": "hlmod Modding Core",
    "description": "Core utilities, tools, and functions for instrumenting Hashlink.",
    "version": "0.0.1",
    "dependencies": []
}

def load_all_stubs(base_dir: str = "./mods/stubs"):
    """
    Loads all stubs generated from the HL bytecode.
    If this function is not called, you may experience issues working with stubbed types
    wrapped in Dyn being passed from HL to Python, but there may be issues in stub generation 
    that prevent this from working. You should only really ever call this once.
    
    Thanks to @snoopinou30 on the Hashlink Modding Community Discord for figuring this out!
    """
    stub_files = glob.glob(base_dir + "/**", recursive=True)
    for f in stub_files:
        if isfile(f) and not f.endswith("__init__.py") and not "__pycache__" in f:
            f = f[:-3].removeprefix(base_dir + "/").replace("/", ".")
            import_module("stubs." + f)

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

