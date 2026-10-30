"""Reproducible regression entrypoint using the project venv.

Application dependencies and PyMuPDF are pinned in the project lock and must
resolve from this venv. Pytest remains an optional test-only tool; the helper
may append the base interpreter's site-packages for that isolated entrypoint.
"""
from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import importlib.util
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_SITE = Path(sys.base_prefix) / "Lib" / "site-packages"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if BASE_SITE.is_dir() and str(BASE_SITE) not in sys.path:
    # Append after venv site-packages so project-pinned runtime deps win.
    sys.path.append(str(BASE_SITE))
# The base interpreter contains optional telemetry wheels whose versions do not
# match the project's venv OpenTelemetry API. Keep those optional packages
# isolated so the project's existing conditional skips remain truthful.
for _namespace in ("opentelemetry", "openinference"):
    if importlib.util.find_spec(_namespace) is not None:
        _module = importlib.import_module(_namespace)
        if hasattr(_module, "__path__"):
            _module.__path__ = [entry for entry in _module.__path__
                                if Path(entry).resolve().is_relative_to(Path(sys.prefix).resolve())]


def _versions() -> dict[str, str]:
    names = ("fastapi", "pydantic", "langgraph", "langgraph-checkpoint-sqlite",
             "pytest", "PyMuPDF")
    result = {}
    for name in names:
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result[name] = "missing"
    return result


def run_unittest() -> bool:
    print(f"S2_TEST_ENV python={sys.executable} base={sys.base_prefix} packages={_versions()}", flush=True)
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(f"S2_UNITTEST tests={result.testsRun} failures={len(result.failures)} errors={len(result.errors)} skipped={len(result.skipped)}")
    return result.wasSuccessful()


def run_pytest() -> bool:
    os.environ.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    try:
        import pytest
    except ImportError as exc:
        print(f"S2_PYTEST unavailable: {exc}", file=sys.stderr)
        return False
    code = pytest.main(["-q", "-p", "no:cacheprovider", str(ROOT / "tests" / "test_p16_a_evidence42.py")])
    print(f"S2_PYTEST exit_code={int(code)}")
    return int(code) == 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--unit-only", action="store_true")
    parser.add_argument("--pytest-only", action="store_true")
    args = parser.parse_args()
    if args.unit_only:
        ok = run_unittest()
    elif args.pytest_only:
        ok = run_pytest()
    else:
        unit_ok = run_unittest()
        pytest_ok = run_pytest()
        ok = unit_ok and pytest_ok
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
