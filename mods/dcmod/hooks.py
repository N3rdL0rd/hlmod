
from typing import Any, Optional
from hlmod import Hook
from modcore import hook
from stubs import ui
from stubs import h2d
from stubs.pr import TitleScreen
from . import globals
from .util import log

@hook("ui.$Console.__constructor__")
def hook_console_ctor(self: Hook, this: ui.Console):
    globals.CONSOLE = this
    self.call_original(this)
    this.activateDebug()
    log("Console initialized!")
    
@hook("ui.Console.log")
def hook_console_log(self: Hook, this: ui.Console, logText: str, color: Optional[int]):
    print(f"[dcmod] [Console] {logText}")
    h2d.Console.log(this, logText, color)

@hook("pr.TitleScreen.setMiscTexts")
def hook_titlescreen_setMiscTexts(self: Hook, this: TitleScreen):
    self.call_original(this)
    if globals.CUSTOM_BUILD_TEXT:
        this.build.set_text(globals.BUILD_TEXT)

@hook("tools.pak.$PakUtils.getPakStampHash")
def hook_pakutils_getPakStampHash(self: Hook) -> str:
    if not globals.PREDICTABLE_STAMP:
        return self.call_original()
    return "0022228129b0973a12d14548434b3741debcd3a38734f1e0dd1f3b3f7acdd91c" # for commit 50ed44f, latest v35. in case you fuck something up version-wise ;)

@hook("tool.log.$LogUtils.log")
def hook_logutils_log(self: Hook, text: str, severity: Any, pos: Any):
    print(text)
    if globals.CONSOLE:
        globals.CONSOLE.log(text, 0xb8fcf7)
    self.call_original(text, severity, pos)
