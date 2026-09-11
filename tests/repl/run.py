"""Run the native REPL server against a live process: protocol correctness
(shorthand commands, expression/statement evaluation, multi-line buffering,
exceptions), per-connection namespace isolation, and shutdown never hanging
on an idle client."""

import argparse
import os
import socket
import subprocess
import tempfile
import time
from pathlib import Path
import shutil

REPL_PORT = 17734
# Keep in sync with ReplFixture.hx's Sys.sleep call.
FIXTURE_SLEEP_SECONDS = 5.0


def _read_until_prompt(sock: socket.socket, timeout: float = 10.0) -> str:
    sock.settimeout(timeout)
    buffer = ""
    while not buffer.endswith(">>> ") and not buffer.endswith("... "):
        chunk = sock.recv(4096)
        if not chunk:
            raise SystemExit(f"REPL connection closed early; got: {buffer!r}")
        buffer += chunk.decode("utf-8")
    return buffer


def _send_line(sock: socket.socket, line: str) -> str:
    sock.sendall((line + "\n").encode("utf-8"))
    return _read_until_prompt(sock)


def _wait_for_listening(process: subprocess.Popen, timeout: float = 20.0) -> list[str]:
    lines: list[str] = []
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        line = process.stdout.readline()
        if not line:
            if process.poll() is not None:
                raise SystemExit("hl exited before the REPL started:\n" + "".join(lines))
            continue
        lines.append(line)
        if "REPL listening" in line:
            return lines
    raise SystemExit("Timed out waiting for the REPL to start:\n" + "".join(lines))


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hl", type=Path, default=root / "hlmod-hl/build/bin/hl")
    parser.add_argument("--haxe", default="haxe")
    args = parser.parse_args()
    fixture = Path(__file__).resolve().parent

    with tempfile.TemporaryDirectory(prefix="hlmod-repl-") as temporary:
        work = Path(temporary)
        mods = work / "mods"
        mods.mkdir()
        for name in ("hlobj.py", "hlvalues.py"):
            shutil.copy2(root / "mods" / name, mods / name)
        shutil.copytree(root / "mods/modcore", mods / "modcore", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2(fixture / "repl_mod.py", mods / "repl_mod.py")
        bytecode = work / "ReplFixture.hl"
        subprocess.run(
            [args.haxe, "-cp", str(fixture), "-main", "ReplFixture", "-hl", str(bytecode)],
            check=True, timeout=60,
        )

        start = time.monotonic()
        process = subprocess.Popen(
            [str(args.hl.resolve()), str(bytecode)], cwd=work,
            env={**os.environ, "PYTHONUNBUFFERED": "1", "HLMOD_REPL_PORT": str(REPL_PORT)},
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        try:
            _wait_for_listening(process)

            # Protocol correctness + live hook introspection, on one connection.
            first = socket.create_connection(("127.0.0.1", REPL_PORT), timeout=10)
            try:
                banner = _read_until_prompt(first)
                if "hlmod REPL" not in banner:
                    raise SystemExit(f"Missing REPL banner: {banner!r}")

                reply = _send_line(first, "mods")
                if "repl_mod [loaded]" not in reply:
                    raise SystemExit(f"`mods` did not report repl_mod: {reply!r}")

                reply = _send_line(first, "hooks")
                if "owner=repl_mod" not in reply:
                    raise SystemExit(f"`hooks` did not report the registered hook: {reply!r}")

                reply = _send_line(first, "21 * 2")
                if "42" not in reply:
                    raise SystemExit(f"Expression evaluation failed: {reply!r}")

                _send_line(first, "x = 40")
                _send_line(first, "def f():")
                _send_line(first, "    return x + 2")
                _send_line(first, "")
                reply = _send_line(first, "f()")
                if "42" not in reply:
                    raise SystemExit(f"Multi-line def evaluation failed: {reply!r}")

                reply = _send_line(first, "1 / 0")
                if "ZeroDivisionError" not in reply:
                    raise SystemExit(f"Exception was not reported: {reply!r}")
            finally:
                first.close()
            print("REPL_PROTOCOL_OK", flush=True)

            # A fresh connection must not see the first connection's namespace.
            second = socket.create_connection(("127.0.0.1", REPL_PORT), timeout=10)
            try:
                _read_until_prompt(second)
                reply = _send_line(second, "x")
                if "NameError" not in reply:
                    raise SystemExit(f"REPL connections are not isolated: {reply!r}")
            finally:
                second.close()
            print("REPL_ISOLATION_OK", flush=True)

            # Leave a third connection open and idle, then let the fixture's
            # entrypoint finish naturally: shutdown must close it and exit
            # promptly, not hang until the wait() timeout below fires.
            idle = socket.create_connection(("127.0.0.1", REPL_PORT), timeout=10)
            _read_until_prompt(idle)
            try:
                returncode = process.wait(timeout=FIXTURE_SLEEP_SECONDS + 15.0)
            except subprocess.TimeoutExpired:
                raise SystemExit("Shutdown hung with an idle REPL client connected")
            elapsed = time.monotonic() - start
            output = process.stdout.read()
            idle.close()
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)

    if returncode:
        raise SystemExit(f"ReplFixture exited with status {returncode}:\n{output}")
    if "Bye!" not in output:
        raise SystemExit(f"ReplFixture did not shut down cleanly:\n{output}")
    if elapsed > FIXTURE_SLEEP_SECONDS + 10.0:
        raise SystemExit(f"Shutdown with an idle REPL client took too long ({elapsed:.1f}s)")
    print("REPL_SHUTDOWN_OK", flush=True)
    print("REPL_FIXTURE_OK", flush=True)


if __name__ == "__main__":
    main()
