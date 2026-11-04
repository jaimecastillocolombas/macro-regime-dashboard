"""Smoke test: the package imports, so CI has something real to run from day one."""

import importlib


def test_package_imports() -> None:
    for module in ("src", "src.ingest", "src.transform", "src.strategy"):
        assert importlib.import_module(module) is not None
