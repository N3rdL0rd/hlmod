from . import globals
from typing import Optional

def log(*args, use_prefix: bool = True, color: Optional[int] = None, **kwargs) -> None:
    if use_prefix:
        print("[dcmod] ", end="")
    print(*args, **kwargs)
    if globals.CONSOLE is not None and globals.INGAME_LOGS:
        if use_prefix:
            globals.CONSOLE.log(f"[dcmod] {' '.join(args)}", color if color is not None else globals.LOG_COLOR)
        else:
            globals.CONSOLE.log(' '.join(args), color if color is not None else globals.LOG_COLOR)

def set_build_text(text: str) -> None:
    globals.BUILD_TEXT = text