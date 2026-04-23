MOD_INFO = {
    "id": "dcmod",
    "name": "Dead Cells core for hlmod",
    "description": "Core utilities for modding Dead Cells.",
    "version": "0.0.1",
    "dependencies": ["modcore"],
    "enabled": True
}

from hlmod import assert_code_sha
from . import hooks
from .util import *

def initialize() -> None:
    # assert_code_sha("376564ab2173ddcbadf53d73baf2fc335793e4d14a637fc1829569c314f39667") # TODO: support matching a list of hashes
    # assert_code_sha("d5d17575f4bec6ab674a9cac56fba5fd696576f23fc1b22e32629bcafba92ad3")
    pass
