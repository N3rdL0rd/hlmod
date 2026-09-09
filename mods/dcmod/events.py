"""Dead Cells notifications published by the core's native hook bridges.

These describe logical game updates, not render frames or elapsed seconds.
Subscriptions are owned by the subscribing mod and removed when it unloads.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from modcore import Event

if TYPE_CHECKING:
    from stubs.pr import Game
    from stubs.ui import Console


game_update: Event[[Game]] = Event("dcmod.game_update")
"""Emitted after each successful ``pr.Game.update`` call."""

game_post_update: Event[[Game]] = Event("dcmod.game_post_update")
"""Emitted after each successful ``pr.Game.postUpdate`` call."""

console_ready: Event[[Console]] = Event("dcmod.console_ready")
"""Emitted once a native console has been initialized and activated."""
