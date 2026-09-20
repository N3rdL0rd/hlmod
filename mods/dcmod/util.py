from . import globals
from .settings import settings
from typing import Optional

def log(*args, use_prefix: bool = True, color: Optional[int] = None, **kwargs) -> None:
    if use_prefix:
        print("[dcmod] ", end="")
    print(*args, **kwargs)
    if globals.CONSOLE is not None and settings.ingame_logs:
        if use_prefix:
            globals.CONSOLE.log(f"[dcmod] {' '.join(args)}", color if color is not None else settings.log_color)
        else:
            globals.CONSOLE.log(' '.join(args), color if color is not None else settings.log_color)

def set_build_text(text: str) -> None:
    globals.BUILD_TEXT = text