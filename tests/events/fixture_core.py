MOD_INFO = {"id": "fixture_core", "dependencies": ["modcore"]}

from modcore import Event, HookContext, hook
from stubs import FixtureGame


game_update: Event[[FixtureGame]] = Event("fixture_core.game_update")
trace: list[tuple[str, int]] = []
initialized: list[str] = []
stopped: list[str] = []


@hook(FixtureGame.update)
def publish_update(context: HookContext[[FixtureGame], None], game: FixtureGame) -> None:
    context.call_next(game)
    game_update.emit(game)
