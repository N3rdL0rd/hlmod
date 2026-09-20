MOD_INFO = {
    "id": "dcmod",
    "name": "Dead Cells core for hlmod",
    "description": "Core utilities for modding Dead Cells.",
    "version": "0.0.1",
    "dependencies": ["modcore"],
    "enabled": True
}

from hlmod import assert_code_sha
from modcore import load_all_stubs
from . import events, hooks
from .settings import settings as settings
from .util import *

def initialize() -> None:
    # Register a Python proxy class for every type in the bytecode. Without
    # this, only the handful of `stubs.*` modules some mod happened to import
    # are registered, and every other native value - a field read, a hook
    # argument - arrives as an opaque `hlmod.HlPtr` with no fields or methods.
    load_all_stubs()
    # assert_code_sha("376564ab2173ddcbadf53d73baf2fc335793e4d14a637fc1829569c314f39667") # TODO: support matching a list of hashes
    # assert_code_sha("d5d17575f4bec6ab674a9cac56fba5fd696576f23fc1b22e32629bcafba92ad3")
