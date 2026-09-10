MOD_INFO = {"id": "broken_mod", "dependencies": []}


def initialize():
    raise RuntimeError("intentional test failure")


initialize()
