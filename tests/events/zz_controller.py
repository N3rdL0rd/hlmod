MOD_INFO = {"id": "zz_controller", "dependencies": ["fixture_core"]}

import hlmod
import fixture_core as core
from modcore import HookContext, hook, load_mod, register_hook, reload_mod, unload_mod
from stubs import FixtureGame


def expected_tick(before: int, *, a: bool = True):
    after = before + 1
    if not a:
        return [("b-before", before), ("b-event", after), ("b-after", after)]
    return [("a-before", before), ("b-before", before), ("a-event", after),
            ("b-event", after), ("b-after", after), ("a-after", after)]


@hook("$EventsFixture.verify")
def verify(context: HookContext[[FixtureGame], None], game: FixtureGame) -> None:
    assert core.initialized == ["a", "b"]
    assert core.trace == sum((expected_tick(tick) for tick in range(3)), [])

    unload_mod("plugin_a")
    assert core.stopped == ["a"]
    core.trace.clear()
    game.update()
    assert core.trace == expected_tick(3, a=False)

    reload_mod("plugin_b")
    assert core.initialized == ["a", "b", "b"]
    assert core.stopped == ["a", "b"]
    core.trace.clear()
    game.update()
    assert core.trace == expected_tick(4, a=False), "reload duplicated a registration"

    load_mod("plugin_a", "plugin_a", ("fixture_core",))
    core.trace.clear()
    game.update()
    assert core.trace == expected_tick(5)

    # Core dependencies cannot disappear beneath live subscribers.
    try:
        unload_mod("fixture_core")
    except (ValueError, RuntimeError):
        pass
    else:
        raise AssertionError("unloaded a core library with active dependents")

    totals = [0] * 500
    tokens = []
    for index in range(len(totals)):
        def subscriber(value: FixtureGame, index=index) -> None:
            totals[index] += value.ticks
        tokens.append(core.game_update.subscribe(subscriber))
    game.update()
    assert totals == [7] * 500

    def bad_subscriber(value: FixtureGame) -> None:
        raise ValueError("intentional event subscriber failure")

    failing = core.game_update.subscribe(bad_subscriber, priority=100)
    game.update()
    assert totals == [15] * 500, "one failing subscriber interrupted broadcast"
    failing.close()
    failing.close()
    for token in tokens:
        token.close()
    game.update()
    assert totals == [15] * 500, "closed subscriptions were still called"

    # An error after next must propagate, not execute the original a second time.
    def fails_after_next(ctx: HookContext[[FixtureGame], None], value: FixtureGame) -> None:
        ctx.call_next(value)
        raise ValueError("intentional composed hook failure")

    broken = register_hook(FixtureGame.update, fails_after_next, priority=100)
    before = game.ticks
    caught = hlmod.call(hlmod.findex_for_name("$EventsFixture.caughtUpdate"), (game,))
    assert caught is True
    assert game.ticks == before + 1
    broken.close()
    core.trace.clear()
    game.update()
    assert core.trace == expected_tick(before + 1)
    print("EVENTS_LIFECYCLE_OK", flush=True)
