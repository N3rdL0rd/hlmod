from .import MOD_INFO
import hlmod
from stubs import ui
from typing import Optional

CONSOLE: Optional[ui.Console] = None
PREDICTABLE_STAMP: bool = True # return a predictable stamp value from $PakUtils.getPakStampHash so changes to version info in the game don't invalidate your paks
INGAME_LOGS: bool = True
LOG_COLOR: int = 0xffffff
CUSTOM_BUILD_TEXT: bool = True
# TODO: config system

BUILD_TEXT = f"dcmod {MOD_INFO["version"]}, powered by hlmod {hlmod.version}"