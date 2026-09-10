"""Pure Python framework contracts; native hook chains live in the bridge fixture."""

from importlib import import_module, invalidate_caches
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import textwrap
import tomllib
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "mods"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "hlmod-hl" / "python"))

from modcore import (
    Event, ModError, Registration, config, current_mod, finish_loading, load_all_stubs,
    load_mod, mods_loaded, reload_mod, shutdown, shutting_down, unload_mod,
)
from modcore._toml_writer import dumps as toml_dumps
import stub_renderer


class EventTests(unittest.TestCase):
    def test_priority_ties_and_nested_mutation_use_entry_snapshot(self):
        event = Event("frame")
        seen = []

        def first(value):
            seen.append(("first", value))
            if value == 0:
                removed.close()
                event.subscribe(lambda value: seen.append(("added", value)))
                event.emit(1)

        event.subscribe(first, priority=10)
        event.subscribe(lambda value: seen.append(("tie", value)), priority=10)
        removed = event.subscribe(lambda value: seen.append(("removed", value)))
        event.emit(0)
        self.assertEqual(seen, [
            ("first", 0), ("first", 1), ("tie", 1), ("added", 1),
            ("tie", 0), ("removed", 0),
        ])
        seen.clear()
        event.emit(2)
        self.assertEqual(seen, [("first", 2), ("tie", 2), ("added", 2)])

    def test_exception_isolation_and_baseexception_propagation(self):
        event = Event("update")
        seen = []

        def broken():
            raise ValueError("bad subscriber")

        event.subscribe(broken)
        event.subscribe(lambda: seen.append("continued"))
        with self.assertLogs("modcore.events", level="ERROR"):
            event.emit()
        self.assertEqual(seen, ["continued"])

        def interrupt():
            raise KeyboardInterrupt()

        interrupt_registration = event.subscribe(interrupt, priority=100)
        with self.assertRaises(KeyboardInterrupt):
            event.emit()
        interrupt_registration.close()
        self.assertEqual(seen, ["continued"])

    def test_registration_context_and_idempotent_close(self):
        event = Event("value")
        seen = []
        with event.subscribe(seen.append) as registration:
            event.emit(1)
        registration.close()
        event.emit(2)
        self.assertEqual(seen, [1])
        self.assertTrue(registration.closed)


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        sys.path.insert(0, self.temporary.name)
        self.write_module("framework_shared", """
            from modcore import Event
            event = Event("shared.frame")
            late = Event("shared.late")
            trace = []
        """)
        self.shared = import_module("framework_shared")

    def tearDown(self):
        try:
            shutdown()
        finally:
            sys.path.remove(self.temporary.name)
            for name in tuple(sys.modules):
                if name.startswith("framework_"):
                    sys.modules.pop(name)
            self.temporary.cleanup()

    def write_module(self, name, source):
        path = self.root.joinpath(*name.split(".")).with_suffix(".py")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(source), encoding="utf-8")
        invalidate_caches()

    def test_shared_event_broadcast_and_callback_owner_cleanup(self):
        self.write_module("framework_a", """
            from modcore import current_mod
            from framework_shared import event, late, trace
            @event.listen(priority=5)
            def update(value):
                trace.append(("a", value, current_mod().id))
                late.subscribe(lambda: trace.append("late-a"))
        """)
        self.write_module("framework_b", """
            from framework_shared import event, trace
            @event.listen()
            def update(value):
                trace.append(("b", value))
        """)
        load_mod("a", "framework_a")
        load_mod("b", "framework_b")
        self.shared.event.emit(1)
        self.shared.late.emit()
        self.assertEqual(self.shared.trace, [("a", 1, "a"), ("b", 1), "late-a"])
        self.assertIsNone(current_mod())
        unload_mod("a")
        self.shared.trace.clear()
        self.shared.event.emit(2)
        self.shared.late.emit()
        self.assertEqual(self.shared.trace, [("b", 2)])

    def test_failed_import_and_initialize_remove_all_owned_resources(self):
        for name, failure in (
            ("framework_import_error", "raise ValueError('import failed')"),
            ("framework_init_error", "def initialize():\n    raise ValueError('initialize failed')"),
        ):
            self.write_module(name, """
                from modcore import Registration
                from framework_shared import event, trace
                event.subscribe(lambda: trace.append("leaked"))
                Registration(lambda: trace.append("first"))
                Registration(lambda: trace.append("second"))
            """)
            path = self.root / (name + ".py")
            with path.open("a", encoding="utf-8") as stream:
                stream.write(failure + "\n")
            with self.assertRaises(ModError) as failure_context:
                load_mod(name, name)
            self.assertIsInstance(failure_context.exception.__cause__, ValueError)
            self.shared.event.emit()
            self.assertEqual(self.shared.trace, ["second", "first"])
            self.shared.trace.clear()
            self.assertNotIn(name, sys.modules)
            self.assertIsNone(current_mod())

    def test_reload_initializes_once_and_does_not_accumulate(self):
        self.write_module("framework_reload", """
            from framework_shared import event, trace
            def initialize():
                trace.append("initialized")
                event.subscribe(lambda: trace.append("event"))
        """)
        original = load_mod("reload", "framework_reload")
        self.shared.event.emit()
        replacement = reload_mod("reload")
        self.shared.event.emit()
        self.assertIsNot(original.module, replacement.module)
        self.assertEqual(original.state, "unloaded")
        self.assertEqual(self.shared.trace, ["initialized", "event", "initialized", "event"])
        self.assertIs(sys.modules["framework_shared"], self.shared)

    def test_dependency_guards_and_cascade_reverse_cleanup_even_on_error(self):
        self.write_module("framework_base", """
            from modcore import Registration
            from framework_shared import trace
            Registration(lambda: trace.append("base resource"))
            def shutdown():
                trace.append("base shutdown")
        """)
        self.write_module("framework_child", """
            from modcore import Registration
            from framework_shared import trace
            Registration(lambda: trace.append("child resource"))
            def shutdown():
                trace.append("child shutdown")
                raise ValueError("child shutdown failed")
        """)
        with self.assertRaises(ModError):
            load_mod("child", "framework_child", ("base",))
        load_mod("base", "framework_base")
        load_mod("child", "framework_child", ("base",))
        with self.assertRaises(ModError):
            unload_mod("base")
        self.assertEqual(self.shared.trace, [])
        with self.assertRaises(ExceptionGroup):
            unload_mod("base", cascade=True)
        self.assertEqual(self.shared.trace, [
            "child shutdown", "child resource", "base shutdown", "base resource",
        ])
        self.assertNotIn("framework_child", sys.modules)
        self.assertNotIn("framework_base", sys.modules)

    def test_dependency_cycle_during_initialize_rolls_back(self):
        self.write_module("framework_cycle_a", """
            from modcore import load_mod
            from framework_shared import event, trace
            event.subscribe(lambda: trace.append("leaked"))
            def initialize():
                load_mod("cycle-b", "framework_cycle_b", ("cycle-a",))
        """)
        self.write_module("framework_cycle_b", "raise AssertionError('must not import')")
        with self.assertRaises(ModError):
            load_mod("cycle-a", "framework_cycle_a")
        self.shared.event.emit()
        self.assertEqual(self.shared.trace, [])
        self.assertNotIn("framework_cycle_a", sys.modules)
        self.assertNotIn("framework_cycle_b", sys.modules)

    def test_reload_cascade_restores_dependency_order_without_duplicates(self):
        self.write_module("framework_parent", """
            from framework_shared import event, trace
            def initialize():
                trace.append("parent")
                event.subscribe(lambda: trace.append("parent event"))
        """)
        self.write_module("framework_dependent", """
            from framework_shared import event, trace
            def initialize():
                trace.append("dependent")
                event.subscribe(lambda: trace.append("dependent event"))
        """)
        load_mod("parent", "framework_parent")
        load_mod("dependent", "framework_dependent", ("parent",))
        reload_mod("parent", cascade=True)
        self.shared.event.emit()
        self.assertEqual(self.shared.trace, [
            "parent", "dependent", "parent", "dependent", "parent event", "dependent event",
        ])

    def test_framework_phases_fire_once_and_before_reverse_teardown(self):
        self.write_module("framework_phase", """
            from modcore import mods_loaded, shutting_down
            from framework_shared import trace
            mods_loaded.subscribe(lambda: trace.append("loaded"))
            shutting_down.subscribe(lambda: trace.append("shutting down"))
            def shutdown():
                trace.append("shutdown callback")
        """)
        load_mod("phase", "framework_phase")
        finish_loading()
        finish_loading()
        shutdown()
        shutdown()
        self.assertEqual(self.shared.trace, ["loaded", "shutting down", "shutdown callback"])
        mods_loaded.emit()
        shutting_down.emit()
        self.assertEqual(self.shared.trace, ["loaded", "shutting down", "shutdown callback"])

    def test_package_reload_removes_only_managed_namespace(self):
        package = self.root / "framework_package"
        package.mkdir()
        (package / "__init__.py").write_text("from . import child\n", encoding="utf-8")
        (package / "child.py").write_text("value = object()\n", encoding="utf-8")
        first = load_mod("package", "framework_package")
        child = first.module.child
        second = reload_mod("package")
        self.assertIsNot(second.module.child, child)
        self.assertIs(sys.modules["framework_shared"], self.shared)


class StubLoadingTests(unittest.TestCase):
    def test_only_runtime_modules_load_and_package_exports_survive(self):
        saved = {name: module for name, module in sys.modules.items()
                 if name == "stubs" or name.startswith("stubs.")}
        for name in saved:
            sys.modules.pop(name)
        try:
            with TemporaryDirectory() as temporary:
                root = Path(temporary) / "stubs"
                root.mkdir()
                (root / "__init__.py").write_text("from .Thing import Thing\n", encoding="utf-8")
                (root / "Thing.py").write_text("class Thing: pass\n", encoding="utf-8")
                (root / "Thing.pyi").write_text("not runtime python", encoding="utf-8")
                (root / ".source_hash").write_text("not a module", encoding="utf-8")
                child = root / "child"
                child.mkdir()
                (child / "__init__.py").write_text("", encoding="utf-8")
                (child / "Other.py").write_text("class Other: pass\n", encoding="utf-8")
                cache = root / "__pycache__"
                cache.mkdir()
                (cache / "bad.py").write_text("raise AssertionError('cache imported')", encoding="utf-8")
                sys.path.insert(0, temporary)
                try:
                    load_all_stubs(str(root))
                    package = import_module("stubs")
                    self.assertIsInstance(package.Thing(), package.Thing)
                    self.assertIn("stubs.child.Other", sys.modules)
                finally:
                    sys.path.remove(temporary)
        finally:
            for name in tuple(sys.modules):
                if name == "stubs" or name.startswith("stubs."):
                    sys.modules.pop(name)
            sys.modules.update(saved)


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        config.set_path(Path(self.temporary.name) / "hlmod.toml")
        self.addCleanup(config.set_path, Path("hlmod.toml"))

    def test_section_requires_explicit_name_outside_a_mod(self):
        self.assertIsNone(current_mod())
        with self.assertRaises(RuntimeError):
            config.section(defaults={"x": 1})

    def test_defaults_fill_missing_keys_and_mark_dirty_exactly_once(self):
        section = config.section("mymod", defaults={"volume": 5, "name": "hi"})
        self.assertEqual(section["volume"], 5)
        config.save()
        self.assertTrue(config._path.exists())
        raw = tomllib.loads(config._path.read_text(encoding="utf-8"))
        self.assertEqual(raw, {"mymod": {"volume": 5, "name": "hi"}})

        # Re-opening with the same defaults must not touch an explicitly-set value.
        section["volume"] = 11
        config.save()
        reopened = config.section("mymod", defaults={"volume": 5, "name": "hi"})
        self.assertEqual(reopened["volume"], 11)

    def test_sections_are_independent(self):
        a = config.section("mod_a", defaults={"x": 1})
        b = config.section("mod_b", defaults={"x": 2})
        a["x"] = 100
        self.assertEqual(b["x"], 2)
        config.save()
        raw = tomllib.loads(config._path.read_text(encoding="utf-8"))
        self.assertEqual(raw, {"mod_a": {"x": 100}, "mod_b": {"x": 2}})

    def test_save_is_a_no_op_without_changes(self):
        config.section("mymod", defaults={"x": 1})
        config.save()
        first_write = config._path.read_text(encoding="utf-8")
        config._path.write_text(first_write + "\n# tampered\n", encoding="utf-8")
        config.save()  # nothing marked dirty since the first save; must not rewrite
        self.assertEqual(config._path.read_text(encoding="utf-8"), first_write + "\n# tampered\n")

    def test_shutting_down_event_autosaves(self):
        config.section("mymod", defaults={"x": 1})
        self.assertFalse(config._path.exists())
        shutting_down.emit()
        self.assertTrue(config._path.exists())

    def test_toml_writer_round_trips_representable_value_shapes(self):
        data = {
            "mymod": {
                "flag": True,
                "count": -7,
                "ratio": 0.5,
                "text": 'has "quotes", a\ttab, and a\nnewline',
                "bare-ish.key": 3,
                "items": [1, 2, 3],
                "nested": {"deep": {"value": "ok"}},
            }
        }
        rendered = toml_dumps(data)
        self.assertEqual(tomllib.loads(rendered), data)

class StubRendererTests(unittest.TestCase):
    """`editor_source` rebuilds .pyi bodies via ast.unparse; it must keep the
    method docstring statement instead of discarding it with the rest of the
    (runtime-only) body."""

    def render_weapon(self, *, doc=None, file=None, line=None):
        function = {"findex": 0, "type": 1, "owner": "pr.Weapon", "name": "fire", "arg_names": []}
        if file is not None:
            function["file"] = file
            function["line"] = line
        metadata = {
            "code_hash": "abc", "native_type_count": 1,
            "types": [
                {"index": 0, "kind": stub_renderer.OBJ, "name": "pr.Weapon", "super": -1, "fields": [],
                 "methods": [{"name": "fire", "findex": 0, "pindex": 0}], "bindings": []},
                {"index": 1, "kind": stub_renderer.FUN, "args": [0], "return": 0},
            ],
            "functions": [function],
            "constructors": [],
            "docs": {"pr.Weapon": {"functions": {"fire": doc}}} if doc else {},
        }
        files = stub_renderer.Renderer(metadata, {}).render()
        return files["pr/Weapon.pyi"]

    def test_method_docstring_survives_into_pyi(self):
        pyi = self.render_weapon(doc="Fires the weapon.")
        self.assertIn('"""Fires the weapon."""', pyi)

    def test_debug_location_is_appended_to_the_docstring(self):
        pyi = self.render_weapon(doc="Fires the weapon.", file="Weapon.hx", line=42)
        self.assertIn("Fires the weapon.", pyi)
        self.assertIn("Weapon.hx:42", pyi)

    def test_debug_location_alone_still_produces_a_docstring(self):
        pyi = self.render_weapon(file="Weapon.hx", line=42)
        self.assertIn('"""Weapon.hx:42"""', pyi)

    def test_no_doc_and_no_debug_info_leaves_a_bare_body(self):
        pyi = self.render_weapon()
        method = pyi.split("def fire(self, /) -> _T0 | None:", 1)[1]
        self.assertNotIn('"""', method.splitlines()[1])
        self.assertIn("...", method)


if __name__ == "__main__":
    unittest.main()
