"""Exercise an isolated generated SDK with Pyright; never load a game or user mods."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


GOOD = '''from typing import assert_type
from stubs import BridgeBase, BridgeChild
from hlobj import HlArray, HlRef
from modcore import Event, HookContext, hook, register_hook

obj = BridgeBase(1)
assert_type(obj, BridgeBase)
assert_type(obj.value, int)
assert_type(obj.compute(2), int)
assert_type(obj.peer, BridgeBase | None)
assert_type(obj.nullable(None), int | None)
assert_type(BridgeBase.twice(2), int)
assert_type(BridgeBase.total, int)
assert_type(BridgeChild(2), BridgeChild)
assert_type(obj.values, HlArray[int] | None)
array = obj.array()
if array is not None:
    assert_type(array[0], int)
    array[0] = 2
obj.value = 3
obj.changeable = lambda delta: delta + 1
assert_type(obj.changeable(2), int)

class PythonChild(BridgeBase):
    def compute(self, delta: int) -> int:
        return super().compute(delta) + 1

update: Event[[BridgeBase, float]] = Event("update")
@update.listen()
def on_update(value: BridgeBase, dt: float) -> None:
    value.value += int(dt)
update.subscribe(on_update)
update.emit(obj, 0.5)

@hook(BridgeBase.compute)
def compute(ctx: HookContext[[BridgeBase, int], int], value: BridgeBase, delta: int) -> int:
    assert_type(ctx.call_next(value, delta), int)
    assert_type(ctx.call_original(value, delta), int)
    return ctx.call_next(value, delta)
register_hook(BridgeBase.compute, compute).close()

@hook(BridgeBase.twice)
def twice(ctx: HookContext[[int], int], value: int) -> int:
    return ctx.call_next(value)

ref = HlRef[int].create(0, 1)
assert_type(ref.value, int)
ref.value = 2
'''

BAD = {
    "constructor_type": ('BridgeBase("wrong")', "reportArgumentType"),
    "constructor_arity": ("BridgeBase()", "reportCallIssue"),
    "field_type": ('BridgeBase(1).value = "wrong"', "reportAttributeAccessIssue"),
    "field_typo": ("BridgeBase(1).vlaue", "reportAttributeAccessIssue"),
    "class_typo": ("BridgeBase.typo", "reportAttributeAccessIssue"),
    "method_type": ('BridgeBase(1).compute("wrong")', "reportArgumentType"),
    "static_type": ('BridgeBase.twice("wrong")', "reportArgumentType"),
    "override": ('class Bad(BridgeBase):\n    def compute(self, delta: str) -> str:\n        return delta', "reportIncompatibleMethodOverride"),
    "dynamic_assignment": ('def wrong(delta: str) -> str:\n    return delta\nBridgeBase(1).changeable = wrong', "reportAttributeAccessIssue"),
    "array_write": ('values = BridgeBase(1).array()\nif values is not None:\n    values[0] = "wrong"', "reportArgumentType"),
    "event_emit": ('event: Event[[int]] = Event("tick")\nevent.emit("wrong")', "reportArgumentType"),
    "event_subscriber": ('event: Event[[int]] = Event("tick")\ndef wrong(value: str) -> None: pass\nevent.subscribe(wrong)', "reportArgumentType"),
    "hook_argument": ('@hook(BridgeBase.compute)\ndef wrong(ctx: HookContext[[BridgeBase, int], int], value: BridgeBase, delta: str) -> int:\n    return 1', "reportArgumentType"),
    "hook_result": ('@hook(BridgeBase.compute)\ndef wrong(ctx: HookContext[[BridgeBase, int], int], value: BridgeBase, delta: int) -> str:\n    return "wrong"', "reportArgumentType"),
    "hook_next": ('def wrong(ctx: HookContext[[BridgeBase, int], int], value: BridgeBase) -> int:\n    return ctx.call_next(value, "wrong")', "reportArgumentType"),
    "ref_write": ('ref = HlRef[int].create(0, 1)\nref.value = "wrong"', "reportAttributeAccessIssue"),
}

OVERLAY = {
    "version": 1,
    "imports": {"NativeArray": "hlobj.HlArray"},
    "types": {
        "BridgeBase": {
            "fields": {"values": "NativeArray[int] | None"},
            "methods": {"array": {"args": [], "returns": "HlArray[int] | None"}},
        }
    },
}


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    fixture = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hl", type=Path, default=root / "hlmod-hl/build/bin/hl")
    parser.add_argument("--haxe", default="haxe")
    parser.add_argument("--pyright", default="pyright")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="hlmod-editor-") as temporary:
        work = Path(temporary)
        mods = work / "mods"
        mods.mkdir()
        for name in ("hlobj.py", "hlobj.pyi", "hlmod.pyi", "hlvalues.py"):
            shutil.copy2(root / "mods" / name, mods / name)
        shutil.copytree(root / "mods/modcore", mods / "modcore", ignore=shutil.ignore_patterns("__pycache__"))
        overlay = mods / "typing_overlays.json"
        overlay.write_text(json.dumps(OVERLAY), encoding="utf-8")
        bytecode = work / "EditorFixture.hl"
        subprocess.run([args.haxe, "-cp", str(fixture), "-main", "EditorFixture", "-debug", "-hl", str(bytecode)], check=True, timeout=60)
        environment = {**os.environ, "PYTHONUNBUFFERED": "1", "HLMOD_TYPING_OVERLAY": str(overlay)}

        def generate() -> str:
            result = subprocess.run([str(args.hl.resolve()), "--generate-stubs", str(bytecode)], cwd=work, env=environment,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=90)
            print(result.stdout, end="")
            if result.returncode:
                raise AssertionError("Isolated editor SDK generation failed")
            return result.stdout

        generate()
        (work / "good.py").write_text(GOOD, encoding="utf-8")
        for name, (source, _) in BAD.items():
            (work / f"bad_{name}.py").write_text(
                "from stubs import BridgeBase\nfrom modcore import Event, HookContext, hook\nfrom hlobj import HlRef\n" + source + "\n",
                encoding="utf-8",
            )
        # Relative search paths are portable; this config never points at a user's install.
        (work / "pyrightconfig.json").write_text(json.dumps({
            "include": ["good.py", *[f"bad_{name}.py" for name in BAD]],
            "extraPaths": ["mods"], "pythonVersion": "3.12", "typeCheckingMode": "standard",
        }), encoding="utf-8")
        result = subprocess.run([args.pyright, "--outputjson", "--project", str(work)], cwd=work,
                                capture_output=True, text=True, timeout=90)
        if result.returncode not in (0, 1):
            raise AssertionError(result.stderr or result.stdout)
        diagnostics = json.loads(result.stdout)["generalDiagnostics"]
        by_file: dict[str, list[dict]] = {}
        for diagnostic in diagnostics:
            if diagnostic["severity"] == "error":
                by_file.setdefault(Path(diagnostic["file"]).name, []).append(diagnostic)
        unexpected = {name: errors for name, errors in by_file.items() if name not in {f"bad_{key}.py" for key in BAD}}
        if unexpected:
            raise AssertionError(json.dumps(unexpected, indent=2))
        for name, (_, rule) in BAD.items():
            errors = by_file.get(f"bad_{name}.py", [])
            if not any(error.get("rule") == rule for error in errors):
                raise AssertionError(f"{name}: expected {rule}, got {errors}")
        # Exercise the real generator cache: unchanged input skips, overlay changes regenerate.
        if "skipping generation" not in generate():
            raise AssertionError("Unchanged SDK was not cached")
        changed = json.loads(json.dumps(OVERLAY))
        changed["types"]["BridgeBase"]["fields"]["values"] = "HlArray[str] | None"
        overlay.write_text(json.dumps(changed), encoding="utf-8")
        if "skipping generation" in generate():
            raise AssertionError("Overlay change did not invalidate the cache")
        changed_result = subprocess.run([args.pyright, "--outputjson", "--project", str(work)], cwd=work,
                                        capture_output=True, text=True, timeout=90)
        changed_diagnostics = json.loads(changed_result.stdout)["generalDiagnostics"]
        if not any(Path(error["file"]).name == "good.py" and error.get("rule") == "reportAssertTypeFailure"
                   for error in changed_diagnostics):
            raise AssertionError("Changed overlay did not change the inferred array element type")
        overlay.write_text(json.dumps(OVERLAY), encoding="utf-8")
        generate()
        invalid_overlays = [
            {"version": 2},
            {"version": 1, "imports": {"Missing": "unknown.Type"}},
            {"version": 1, "types": {"NoSuchNativeType": {}}},
            {"version": 1, "types": {"BridgeBase": {"fields": {"typo": "int"}}}},
            {"version": 1, "types": {"BridgeBase": {"fields": {"value": "UnknownType"}}}},
            {"version": 1, "types": {"BridgeBase": {"fields": {"value": "__import__('os').system('false')"}}}},
            {"version": 1, "types": {"BridgeBase": {"methods": {"compute": {"args": [], "returns": "int"}}}}},
        ]
        for invalid in invalid_overlays:
            overlay.write_text(json.dumps(invalid), encoding="utf-8")
            rejected = subprocess.run([str(args.hl.resolve()), "--generate-stubs", str(bytecode)], cwd=work,
                                      env=environment, capture_output=True, text=True, timeout=90)
            if rejected.returncode == 0:
                raise AssertionError(f"Invalid overlay was accepted: {invalid}")
        overlay.write_text(json.dumps(OVERLAY), encoding="utf-8")
        print("EDITOR_ACCEPTANCE_OK: inferred types, rejected invalid programs, overlay cache")


if __name__ == "__main__":
    main()
