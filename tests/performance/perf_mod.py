MOD_INFO = {"id": "bridge_performance", "dependencies": ["modcore"]}

import gc
import time

import hlmod
from modcore import Event
from stubs import PerfObject


class Proxy(PerfObject):
    pass


def measure(hook):
    for count in (100, 500, 1000):
        values = [Proxy(index) for index in range(count)]
        gc.collect()
        start = time.perf_counter()
        for _ in range(3):
            gc.collect()
        elapsed = (time.perf_counter() - start) / 3
        assert values[-1].value == count - 1
        print(f"GC_SECONDS_{count}={elapsed:.9f}", flush=True)
        values.clear()
        gc.collect()
    event: Event[[int]] = Event("performance.broadcast")
    delivered = 0

    def receive(value: int) -> None:
        nonlocal delivered
        delivered += value

    registrations = [event.subscribe(receive) for _ in range(1000)]
    start = time.perf_counter()
    for _ in range(1000):
        event.emit(1)
    elapsed = time.perf_counter() - start
    assert delivered == 1000000
    print(f"EVENT_SECONDS={elapsed:.9f}", flush=True)
    for registration in registrations:
        registration.close()
    # Measure composed dispatch cost for the loop that follows this hook.
    hlmod.register_hook(hlmod.findex_for_name("$PerfFixture.step"), lambda context, value: value + 1)


hlmod.register_hook(hlmod.findex_for_name("$PerfFixture.pythonWork"), measure)
