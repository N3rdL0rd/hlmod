MOD_INFO = {"id": "plugin_b", "dependencies": ["fixture_core"]}

from modcore import HookContext, hook
from stubs import FixtureGame
import fixture_core as core


@core.game_update.listen(priority=10)
def on_update(game: FixtureGame) -> None:
    core.trace.append(("b-event", game.ticks))


@hook(FixtureGame.update, priority=10)
def wrap(context: HookContext[[FixtureGame], None], game: FixtureGame) -> None:
    core.trace.append(("b-before", game.ticks))
    context.call_next(game)
    core.trace.append(("b-after", game.ticks))


def initialize() -> None:
    core.initialized.append("b")


def shutdown() -> None:
    core.stopped.append("b")
