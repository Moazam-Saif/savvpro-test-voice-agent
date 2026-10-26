"""
tests/test_import_guard.py – AST-based import guard (8.5).

Ensures no brain/ module imports from api/, does I/O, or uses forbidden calls.
Also verifies no AI SDK appears in the brain dependencies.
"""
from __future__ import annotations

import ast
import pathlib

BRAIN_ROOT = pathlib.Path(__file__).parent.parent / "src" / "assistant" / "brain"

ALLOWED_STDLIB = {
    "re", "datetime", "dataclasses", "enum", "difflib", "copy", "unicodedata",
    "typing", "collections", "functools", "itertools", "math", "operator",
    "string", "time", "__future__", "logging",
}

FORBIDDEN_CALLS = {
    ("datetime", "now"), ("datetime", "utcnow"),
    ("time", "time"), ("os", "environ"),
}

FORBIDDEN_MODULES = {
    "random", "subprocess", "socket", "urllib", "http", "requests",
    "openai", "anthropic", "google.generativeai", "langchain",
    "transformers", "torch", "tensorflow",
}


def _check_module(path: pathlib.Path) -> list[str]:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(path))
    errors: list[str] = []

    for node in ast.walk(tree):
        # Check imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in FORBIDDEN_MODULES:
                    errors.append(f"{path.name}: forbidden import '{alias.name}'")
                if alias.name.startswith("assistant.api"):
                    errors.append(f"{path.name}: brain/ must not import from api/")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            top = mod.split(".")[0]
            if top in FORBIDDEN_MODULES:
                errors.append(f"{path.name}: forbidden import from '{mod}'")
            if mod.startswith("assistant.api"):
                errors.append(f"{path.name}: brain/ must not import from api/")

        # Check forbidden calls (e.g. datetime.now())
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name):
                pair = (node.value.id, node.attr)
                if pair in FORBIDDEN_CALLS:
                    errors.append(f"{path.name}: forbidden call {node.value.id}.{node.attr}()")

    return errors


def test_brain_import_guard():
    all_errors: list[str] = []
    for path in BRAIN_ROOT.rglob("*.py"):
        all_errors.extend(_check_module(path))
    assert all_errors == [], "\n".join(all_errors)
