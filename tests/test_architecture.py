"""Stage D dependency guard: parse sources; never import the inspected packages.

Authority: ARCHITECTURE §2 (dependency direction), §9 (placement register),
CORE §§4/8, and coordination/CURRENT_TASK's stage D rules. Dependencies within
BEING or ESSENCE subdivisions are deliberately not ordered. External libraries
and subprocess command strings are outside this SOL-package import guard.
"""

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]

# CORE includes corpus maintenance (register C1–C5). BEING and ESSENCE consume
# CORE and neutral services, never each other or the composition root. CONCEPT
# is reserved (§2): it gets no special permission to couple the other divisions.
# Presentation has no division dependencies (terminal.text/themes row, #98);
# interchange is likewise division-independent (I1, #100: stdlib-only exchange).
ALLOWED = {
    "core": {"core"},
    "being": {"being", "core", "presentation", "interchange"},
    "essence": {"essence", "core", "presentation", "interchange"},
    "concept": {"concept", "core", "presentation", "interchange"},
    "presentation": {"presentation"},
    "interchange": {"interchange"},
}

# Exact source/target exceptions, not prefix exemptions. These are root facade
# attributes, not dependencies on another division. No existing forbidden
# division edge is grandfathered in; remove an exception if its use disappears.
EXCEPTIONS = {
    # ARCHITECTURE §9 reader.render/reader.shell: render shows the SOL version.
    ("sol.being.render", "sol.__version__"),
    # ARCHITECTURE §9 reader.app/options/launch: options displays the version.
    ("sol.app.options", "sol.__version__"),
    # ARCHITECTURE §9 reader.app/options/launch: python -m sol delegates to cli.
    ("sol.__main__", "sol.cli"),
}


def division(module):
    parts = module.split(".")
    if len(parts) < 2 or parts[0] != "sol":
        return None
    return "core" if parts[1] == "corpus" else parts[1]


def import_edges(source, module, *, package=False):
    """Return (line, target, lazy) for absolute, relative and local imports.

    ImportFrom includes root names: `from sol import essence` must not evade
    the guard. No module lookup/import is needed to distinguish names
    from submodules, because both belong to the same division below sol.*.
    Also inspect literal dynamic imports and the two existing lazy facades'
    module literals. Reject other computed dynamic imports for manual review;
    this is a static guard, not arbitrary Python data-flow analysis.
    """
    tree = ast.parse(source)
    current_package = module if package else module.rpartition(".")[0]
    dynamic_names = {"__import__"}
    importlib_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            importlib_names.update(alias.asname or alias.name for alias in node.names
                                   if alias.name == "importlib")
        elif isinstance(node, ast.ImportFrom) and node.module == "importlib":
            dynamic_names.update(alias.asname or alias.name for alias in node.names
                                 if alias.name == "import_module")

    class Imports(ast.NodeVisitor):
        def __init__(self):
            self.lazy = False
            self.edges = []

        def add(self, line, target):
            if target == "sol" or target.startswith("sol."):
                self.edges.append((line, target, self.lazy))

        def visit_FunctionDef(self, node):
            # Only the body is lazy; decorators/defaults/annotations are not.
            for expression in [*node.decorator_list, node.args, *getattr(node, "type_params", [])]:
                self.visit(expression)
            if node.returns is not None:
                self.visit(node.returns)
            previous = self.lazy
            self.lazy = True
            for statement in node.body:
                self.visit(statement)
            self.lazy = previous

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Import(self, node):
            for alias in node.names:
                self.add(node.lineno, alias.name)

        def visit_ImportFrom(self, node):
            base = node.module or ""
            if node.level:
                parts = current_package.split(".")
                if node.level > len(parts):
                    raise SyntaxError("relative import escapes package",
                                      (module, node.lineno, node.col_offset + 1, None))
                base = ".".join(parts[:len(parts) - node.level + 1]
                                + ([base] if base else []))
            # A bare `from sol import ...` refers to a facade attribute or a
            # division, so record the names rather than an ambiguous sol edge.
            if base != "sol":
                self.add(node.lineno, base)
            else:
                for alias in node.names:
                    self.add(node.lineno, f"{base}.{alias.name}")

        def visit_Call(self, node):
            function = node.func
            dynamic = (isinstance(function, ast.Name) and function.id in dynamic_names
                       or isinstance(function, ast.Attribute) and function.attr == "import_module"
                       and isinstance(function.value, ast.Name) and function.value.id in importlib_names)
            if dynamic:
                argument = node.args[0] if node.args else next(
                    (item.value for item in node.keywords if item.arg == "name"), None)
                if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                    target = argument.value
                    if target.startswith("."):
                        raise SyntaxError("review relative dynamic import",
                                          (module, node.lineno, node.col_offset + 1, None))
                    self.add(node.lineno, target)
                elif module not in {"sol.core", "sol.essence"} or not package:
                    raise SyntaxError("review computed dynamic import",
                                      (module, node.lineno, node.col_offset + 1, None))
            self.generic_visit(node)

        def visit_Constant(self, node):
            # CORE's _EXPORTS dictionary and ESSENCE's __getattr__ branches use
            # full module literals; cover every branch without executing either.
            if package and module in {"sol.core", "sol.essence"} and isinstance(node.value, str):
                self.add(node.lineno, node.value)

    visitor = Imports()
    visitor.visit(tree)
    return visitor.edges


def allowed(source, target, lazy):
    if (source, target) in EXCEPTIONS:
        return True
    if source == "sol":
        return lazy and division(target) in {*ALLOWED, "app"}
    source_division, target_division = division(source), division(target)
    if source_division == "app":
        return target_division in {*ALLOWED, "app"}
    return target_division in ALLOWED.get(source_division, set())


class ArchitectureTests(unittest.TestCase):
    def test_sol_imports_follow_stage_d_dependencies(self):
        failures = []
        used_exceptions = set()
        for path in sorted((ROOT / "sol").rglob("*.py")):
            relative = path.relative_to(ROOT)
            parts = relative.with_suffix("").parts
            package = parts[-1] == "__init__"
            module = ".".join(parts[:-1] if package else parts)
            if module not in {"sol", "sol.__main__"} and division(module) not in {*ALLOWED, "app"}:
                failures.append(f"{relative}:1: unregistered SOL package {module}")
            try:
                edges = import_edges(path.read_text(encoding="utf-8"), module, package=package)
            except SyntaxError as error:
                failures.append(f"{relative}:{error.lineno}: {error.msg}")
                continue
            for line, target, lazy in edges:
                if (module, target) in EXCEPTIONS:
                    used_exceptions.add((module, target))
                if not allowed(module, target, lazy):
                    failures.append(f"{relative}:{line}: {module} -> {target} is forbidden "
                                    "(ARCHITECTURE §2/§9; CORE §§4/8)")
        if failures:
            self.fail("Stage D dependency violations:\n" + "\n".join(failures))
        self.assertEqual(used_exceptions, EXCEPTIONS, "Remove unused architecture exceptions")

    def test_old_reader_and_terminal_packages_are_absent(self):
        for name in ("reader", "terminal"):
            for path in (ROOT / "sol" / name, ROOT / "sol" / f"{name}.py"):
                with self.subTest(path=path):
                    self.assertFalse(path.exists(), f"{path.relative_to(ROOT)} must not return (stage D, #99)")

    def test_scanner_finds_local_relative_aliased_and_conditional_edges_without_execution(self):
        source = ("raise RuntimeError('never execute inspected sources')\n"
                  "from sol import essence as study\n"
                  "def launch():\n"
                  "    from ...essence.tui import app as ui\n"
                  "    if False:\n"
                  "        import sol.app.main as root\n"
                  "    from . import host\n")
        edges = import_edges(source, "sol.being.neovim.reader")
        self.assertIn((2, "sol.essence", False), edges)
        self.assertIn((4, "sol.essence.tui", True), edges)
        self.assertIn((6, "sol.app.main", True), edges)
        self.assertIn((7, "sol.being.neovim", True), edges)
        for _, target, lazy in edges[:3]:
            self.assertFalse(allowed("sol.being.neovim.reader", target, lazy))
        package_edges = import_edges("from .. import being\n", "sol.essence", package=True)
        self.assertEqual(package_edges, [(1, "sol.being", False)])

    def test_dynamic_imports_and_lazy_facade_tables_are_inspected(self):
        edges = import_edges("from importlib import import_module as load\n"
                             "def f():\n    load('sol.being.actions')\n", "sol.core.example")
        self.assertIn((3, "sol.being.actions", True), edges)
        self.assertFalse(allowed("sol.core.example", edges[0][1], True))
        edges = import_edges("_EXPORTS = {'bad': 'sol.app.main'}\n", "sol.core", package=True)
        self.assertIn((1, "sol.app.main", False), edges)
        self.assertFalse(allowed("sol.core", edges[0][1], False))
        with self.assertRaisesRegex(SyntaxError, "computed dynamic import"):
            import_edges("__import__(module_name)", "sol.being.example")

    def test_forbidden_edges_and_root_laziness(self):
        cases = [
            ("sol.core.example", "from sol.presentation import theme"),
            ("sol.corpus.example", "from sol.being import actions"),
            ("sol.essence.example", "from ..being import actions"),
            ("sol.being.example", "from sol import essence as analysis"),
            ("sol.being.example", "from sol.app import main"),
            ("sol.presentation.example", "import sol.core"),
            ("sol.interchange.example", "from sol.essence import tui"),
            ("sol.concept.example", "from sol.being import actions"),
        ]
        for module, statement in cases:
            with self.subTest(module=module, statement=statement):
                edges = import_edges(statement, module)
                self.assertTrue(edges)
                self.assertTrue(all(not allowed(module, target, lazy) for _, target, lazy in edges))
        for source, target in [("sol.core.example", "sol.corpus.contract"),
                               ("sol.being.example", "sol.interchange.essence"),
                               ("sol.essence.example", "sol.core")]:
            self.assertTrue(allowed(source, target, False))
        self.assertTrue(allowed("sol", "sol.app.main", True))
        self.assertFalse(allowed("sol", "sol.app.main", False))
        edges = import_edges("def launch(value=__import__('sol.app.main')):\n    pass\n",
                             "sol", package=True)
        self.assertEqual(edges, [(1, "sol.app.main", False)])
        self.assertFalse(allowed("sol.core.example", "sol.cli", True))
        self.assertFalse(allowed("sol.being.example", "sol", True))
        self.assertFalse(allowed("sol.being.other", "sol.__version__", False))


if __name__ == "__main__":
    unittest.main()
