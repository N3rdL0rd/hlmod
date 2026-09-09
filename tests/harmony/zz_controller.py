MOD_INFO = {"id": "zz_controller", "dependencies": ["modcore"]}

import hlmod
from modcore import HookContext, hook, patch, postfix_hook, prefix_hook, register_hook
from stubs import Calculator, HarmonyFixture

trace: list[str] = []


def _check_prologue_decoder() -> None:
    """Exercises the native-hook engine's x86-64 prologue decoder directly,
    independent of whatever prologue the loaded bytecode's own natives
    happen to have. In particular this pins the fix for a real bug: MSVC's
    Windows x64 ABI treats XMM6-15 as callee-saved, so any native using them
    spills via `movaps [rsp+N], xmmN` in its prologue - an encoding the
    decoder didn't recognize until it broke hooking `std.sys_time` on
    Windows (System V/Linux never needs this spill, since all XMM registers
    are caller-saved there, which is why the bug was Windows-only)."""
    pad = b"\x90" * 32  # NOP padding so the decoder never reads past our buffer

    def decode(prologue: bytes, min_len: int | None = None) -> int:
        return hlmod.native_hook_test_prologue(prologue + pad, len(prologue) if min_len is None else min_len)

    assert decode(b"\xf3\x0f\x1e\xfa") == 4, "endbr64"
    assert decode(b"\x55") == 1, "push rbp"
    assert decode(b"\x48\x83\xec\x38") == 4, "sub rsp, 0x38"
    assert decode(b"\x48\xb8" + b"\x00" * 8) == 10, "mov rax, imm64"
    assert decode(b"\x0f\xb6\x01") == 3, "movzx eax, byte [rcx]"

    movaps_xmm6 = b"\x0f\x29\x74\x24\x20"  # movaps [rsp+0x20], xmm6
    assert decode(movaps_xmm6) == 5, "movaps [rsp+N], xmm6"
    real_bug_prologue = b"\x48\x83\xec\x38" + movaps_xmm6 + b"\x0f\x29\x7c\x24\x30"
    assert len(real_bug_prologue) == 14, "sanity: matches HLMOD_JUMP_SIZE"
    assert decode(real_bug_prologue) == 14, "sub rsp + two xmm spills, exact HLMOD_JUMP_SIZE"

    # Unrecognized or control-flow instructions must still be refused, not guessed at.
    assert decode(b"\xd8\x00", min_len=1) == -1, "unrecognized x87 opcode"
    assert decode(b"\xc3", min_len=4) == -1, "ret reached before min_len"

    print("NATIVE_HOOK_DECODER_OK", flush=True)


_check_prologue_decoder()

# --- Prefix replacing positional arguments ---------------------------------

@prefix_hook(Calculator.add, priority=10)
def scale_second_arg(a: int, b: int):
    return (a, b * 10)


# --- Postfix replacing the result -------------------------------------------

@postfix_hook(Calculator.multiply, priority=10)
def add_one(result: int, a: int, b: int):
    return result + 1


# --- Combined prefix+postfix patch class (Harmony-style patch unit) --------

@patch(Calculator.accumulate, priority=10)
class AccumulateGuard:
    @staticmethod
    def prefix(self: Calculator, delta: int):
        if delta < 0:
            return False
        return None

    @staticmethod
    def postfix(result, self: Calculator, delta: int):
        if result is None:
            return self.total
        return min(result, 100)


# --- Interleaving of prefix/hook/postfix on one shared chain ---------------

@prefix_hook(Calculator.chained, priority=10)
def chained_prefix(self: Calculator, value: int):
    trace.append("prefix")


@hook(Calculator.chained, priority=5)
def chained_hook(context: HookContext[[Calculator, int], int], self: Calculator, value: int) -> int:
    trace.append("hook-before")
    result = context.call_next(self, value)
    trace.append("hook-after")
    return result


@postfix_hook(Calculator.chained, priority=0)
def chained_postfix(result: int, self: Calculator, value: int):
    trace.append("postfix")
    return result * 2


@hook("$HarmonyFixture.verify")
def verify(context: HookContext[[], None]) -> None:
    assert Calculator.add(2, 3) == 32, "prefix did not replace positional arguments"
    assert Calculator.multiply(2, 3) == 7, "postfix did not replace the result"

    calc = Calculator(10)
    assert calc.accumulate(-5) == 10, "prefix skip must leave total unchanged"
    assert calc.accumulate(50) == 60, "normal path must still run"
    assert calc.accumulate(9000) == 100, "postfix clamp did not run after a real call"

    assert Calculator.chained(calc, 21) == 42
    assert trace == ["prefix", "hook-before", "postfix", "hook-after"], trace

    # --- Native hooking: hook a real @:hlNative function by (lib, name). ---
    findex = hlmod.native_findex("std", "sys_time")
    calls: list[str] = []

    @hook(findex, priority=10)
    def outer(context: HookContext[[], float]) -> float:
        calls.append("outer-before")
        result = context.call_next()
        calls.append("outer-after")
        return result

    def inner(context: HookContext[[], float]) -> float:
        calls.append("inner")
        return 12345.5

    inner_registration = register_hook(findex, inner, priority=0)

    direct = hlmod.call(findex, ())
    assert direct == 12345.5, direct
    assert calls == ["outer-before", "inner", "outer-after"], calls

    wrapper_findex = hlmod.findex_for_name("$HarmonyFixture.nativeTime")
    from_haxe = hlmod.call(wrapper_findex, ())
    assert from_haxe == 12345.5, "hook must also intercept calls reached from compiled Haxe code"

    inner_registration.close()
    calls.clear()
    real_time = hlmod.call(findex, ())
    assert calls == ["outer-before", "outer-after"], calls
    assert real_time != 12345.5 and real_time > 1e9, real_time

    print("HARMONY_FIXTURE_OK", flush=True)
