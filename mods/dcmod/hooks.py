
from typing import Any, Optional
from modcore import HookContext, hook
from stubs import ui
from stubs import h2d
from stubs.pr import Game, TitleScreen
from stubs.ui import NewsPanel
from . import events, globals
from .util import log


@hook("ui.$Console.__constructor__")
def hook_console_ctor(self: HookContext[[ui.Console], None], this: ui.Console) -> None:
    globals.CONSOLE = this
    self.call_next(this)
    this.activateDebug()
    log("Console initialized!")
    events.console_ready.emit(this)

@hook("ui.Console.log")
def hook_console_log(self: HookContext[[ui.Console, str, Optional[int]], None], this: ui.Console, logText: str, color: Optional[int]) -> None:
    print(f"[dcmod] [Console] {logText}")
    h2d.Console.log(this, logText, color)

@hook("pr.TitleScreen.setMiscTexts")
def hook_titlescreen_setMiscTexts(self: HookContext[[TitleScreen], None], this: TitleScreen) -> None:
    self.call_next(this)
    if globals.CUSTOM_BUILD_TEXT:
        this.build.set_text(this.build.text + " " + globals.BUILD_TEXT)

@hook("tools.pak.$PakUtils.getPakStampHash")
def hook_pakutils_getPakStampHash(self: HookContext[[], str]) -> str:
    if not globals.PREDICTABLE_STAMP:
        return self.call_next()
    return "0022228129b0973a12d14548434b3741debcd3a38734f1e0dd1f3b3f7acdd91c" # for commit 50ed44f, latest v35. in case you fuck something up version-wise ;)

@hook("tool.log.$LogUtils.log")
def hook_logutils_log(self: HookContext[[str, Any, Any], None], text: str, severity: Any, pos: Any) -> None:
    print(text)
    if globals.CONSOLE:
        globals.CONSOLE.log(text, 0xb8fcf7)
    self.call_next(text, severity, pos)

@hook("ui.NewsPanel.updateVisible")
def hook_ui_NewsPanel_updateVisible(self: HookContext[[NewsPanel], None], this: NewsPanel) -> None:
    if not globals.REMOVE_NEWS:
        return self.call_next(this)

@hook("ui.NewsPanel.focusIn")
def hook_ui_NewsPanel_focusIn(self: HookContext[[NewsPanel], None], this: NewsPanel) -> None:
    if not globals.REMOVE_NEWS:
        return self.call_next(this)
    
@hook("pr.TitleScreen.update")
def hook_pr_TitleScreen_update(self: HookContext[[TitleScreen], None], this: TitleScreen) -> None:
    self.call_next(this)

    if globals.REMOVE_NEWS:
        if this.isMainMenu:
            this.updateBtn.set_visible(False)

@hook("pr.TitleScreen.postUpdate")
def hook_pr_TitleScreen_postUpdate(self: HookContext[[TitleScreen], None], this: TitleScreen) -> None:
    self.call_next(this)

    if globals.HIDE_CONTROLLER_WARNING:
        pad_warning = this.padWarning
        if pad_warning is not None:
            pad_warning.visible = False

@hook("pr.Game.update")
def hook_game_update(context: HookContext[[Game], None], game: Game) -> None:
    context.call_next(game)
    events.game_update.emit(game)


@hook("pr.Game.postUpdate")
def hook_game_post_update(context: HookContext[[Game], None], game: Game) -> None:
    context.call_next(game)
    events.game_post_update.emit(game)
