from .import MOD_INFO
import hlmod
from stubs import ui
from typing import Optional

CONSOLE: Optional[ui.Console] = None

PREDICTABLE_STAMP        :bool = True      # whether or not to return a predictable stamp value from tools.PakUtils.getPakStampHash so changes to version info in the game don't invalidate your paks
INGAME_LOGS              :bool = True      # logs dcmod and other mods' messages to the ingame debug console, and re-enables the debug logging built into the game
LOG_COLOR                :int  = 0xffffff  # the color to use for mods' debug messages by default
CUSTOM_BUILD_TEXT        :bool = True      # use the value in BUILD_TEXT with the build text on the main menu
REMOVE_NEWS              :bool = True      # remove the update logo and the advertisement in the top right corner of the main menu
SKIP_SPLASH              :bool = True      # shorten the opening splash screen (the one that displays the EE and MT logos before starting)
HIDE_CONTROLLER_WARNING  :bool = True      # hides the "we recommend playing with a controller" warning on the main menu
# TODO: config system

BUILD_TEXT = f"dcmod {MOD_INFO["version"]} (hlmod {hlmod.version})."