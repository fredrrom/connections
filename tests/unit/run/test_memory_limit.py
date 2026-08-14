from __future__ import annotations

import logging
import sys
import types

import pytest

from connections.run.prover import _memory_limit


class _FakeResource:
    RLIMIT_AS = 9

    def __init__(self, *, fail_restore: bool = False) -> None:
        self.fail_restore = fail_restore
        self.limits = (1 << 40, 1 << 41)
        self.calls: list[tuple[int, tuple[int, int]]] = []

    def getrlimit(self, res: int) -> tuple[int, int]:
        return self.limits

    def setrlimit(self, res: int, limits: tuple[int, int]) -> None:
        self.calls.append((res, limits))
        if self.fail_restore and len(self.calls) > 1:
            raise OSError("restore rejected")
        self.limits = limits


def _install(monkeypatch: pytest.MonkeyPatch, fake: _FakeResource) -> None:
    module = types.SimpleNamespace(
        RLIMIT_AS=fake.RLIMIT_AS,
        getrlimit=fake.getrlimit,
        setrlimit=fake.setrlimit,
    )
    monkeypatch.setitem(sys.modules, "resource", module)


def test_noop_without_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeResource()
    _install(monkeypatch, fake)

    with _memory_limit(None):
        pass

    assert fake.calls == []


def test_sets_and_restores_rlimit(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeResource()
    _install(monkeypatch, fake)
    soft, hard = fake.limits

    with _memory_limit(100):
        assert fake.calls == [(fake.RLIMIT_AS, (100 * 1024**2, hard))]

    assert fake.calls[-1] == (fake.RLIMIT_AS, (soft, hard))


def test_restore_failure_logs_warning(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake = _FakeResource(fail_restore=True)
    _install(monkeypatch, fake)

    with caplog.at_level(logging.WARNING, logger="connections.run.prover"):
        with _memory_limit(100):
            pass

    assert any("RLIMIT_AS" in record.message for record in caplog.records)
