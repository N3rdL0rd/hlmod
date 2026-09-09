MOD_INFO = {"id": "plugin_a", "dependencies": ["fixture_core"]}

from modcore import HookContext, hook
from stubs import FixtureGame
import fixture_core as core


@core.game_update.listen(priority=20)
def on_update(game: FixtureGame) -> None:
    core.trace.append(("a-event", game.ticks))


@hook(FixtureGame.update, priority=20)
def wrap(context: HookContext[[FixtureGame], None], game: FixtureGame) -> None:
    core.trace.append(("a-before", game.ticks))
    context.call_next(game)
    core.trace.append(("a-after", game.ticks))


def initialize() -> None:
    core.initialized.append("a")


def shutdown() -> None:
    core.stopped.append("a")
