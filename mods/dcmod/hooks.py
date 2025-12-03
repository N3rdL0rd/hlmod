
from typing import Any, Callable, Optional
from hlmod import Hook
from modcore import hook
from stubs import ui
from stubs import h2d
from stubs.pr import TitleScreen, LogoSplashscreen
from stubs.ui import NewsPanel, Text
from stubs import Assets
from stubs.h2d import Object as H2DObject
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
        this.build.set_text(this.build.text + " " + globals.BUILD_TEXT)

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

@hook("ui.NewsPanel.updateVisible")
def hook_ui_NewsPanel_updateVisible(self: Hook, this: NewsPanel):
    if not globals.REMOVE_NEWS:
        return self.call_original(this)

@hook("ui.NewsPanel.focusIn")
def hook_ui_NewsPanel_focusIn(self: Hook, this: NewsPanel):
    if not globals.REMOVE_NEWS:
        return self.call_original(this)
    
padWarning: Optional[Text] = None
    
@hook("pr.TitleScreen.update")
def hook_pr_TitleScreen_update(self: Hook, this: TitleScreen):
    global padWarning
    if globals.HIDE_CONTROLLER_WARNING:
        padWarning = this.padWarning
        padWarning.set_visible(False)
    if globals.REMOVE_NEWS:
        if this.isMainMenu:
            this.updateBtn.set_visible(False)
    self.call_original(this)
    
@hook("h2d.Object.set_visible")
def hook_h2d_Object_set_visible(self: Hook, this: H2DObject, val: bool):
    if globals.HIDE_CONTROLLER_WARNING:
        if padWarning is None:
            return self.call_original(this, val)
        if this._hlmod_ptr.ptr == padWarning._hlmod_ptr.ptr: # HACK: lazy but it works
            val = False
    return self.call_original(this, val)