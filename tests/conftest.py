from __future__ import annotations

from pathlib import Path

import pytest


def pytest_addoption(parser):
    group = parser.getgroup("connections external corpora")
    group.addoption(
        "--tptp-root",
        action="store",
        default=None,
        metavar="PATH",
        help="Path to a local TPTP root for tests marked external_tptp_corpus.",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "unit: fast tests for isolated code units",
    )
    config.addinivalue_line(
        "markers",
        "integration: tests that exercise process, filesystem, CLI, or corpus boundaries",
    )
    config.addinivalue_line(
        "markers",
        "external_tptp_corpus: optional tests against a local TPTP root",
    )


def pytest_collection_modifyitems(config, items):
    tptp_root = _configured_tptp_root(config)
    for item in items:
        parts = Path(str(item.fspath)).parts
        if "tests" not in parts:
            continue
        relative = parts[parts.index("tests") + 1 :]
        if not relative:
            continue
        if relative[0] == "unit":
            item.add_marker(pytest.mark.unit)
        if relative[0] == "integration":
            item.add_marker(pytest.mark.integration)
        if "external_tptp_corpus" in item.keywords and tptp_root is None:
            item.add_marker(pytest.mark.skip(reason="requires --tptp-root=PATH"))


def _configured_tptp_root(config) -> Path | None:
    value = config.getoption("--tptp-root")
    if not value:
        return None
    path = Path(value)
    if not path.exists() or not path.is_dir():
        raise pytest.UsageError(f"--tptp-root points to a non-directory path: {value}")
    return path


@pytest.fixture
def tptp_root(pytestconfig) -> Path:
    root = _configured_tptp_root(pytestconfig)
    if root is None:
        raise RuntimeError("tptp_root fixture requires --tptp-root=PATH")
    return root
