from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from connections.syntax.logic import Domain, Logic
from connections.prover.status import SZSStatus

_SIMPLE_STATUS_RE = re.compile(r"^%\s*Status\s+:\s*(?P<label>.+?)\s*$")
_INTUITIONISTIC_STATUS_RE = re.compile(
    r"^%\s*Status\s+\(intuit\.\)\s+:\s*(?P<label>.+?)\s*$"
)
_QMLTP_LOGIC_ROW_RE = re.compile(
    r"^%\s*(?P<logic>K|D|T|S4|S5)\s+(?P<statuses>.+?)\s*$"
)

_QMLTP_SOURCE = "qmltp_status_table"
_ILTP_SOURCE = "iltp_intuitionistic_status"
_TPTP_SOURCE = "tptp_status"

_DOMAIN_ALIASES = {
    "constant": "constant",
    "const": "constant",
    "cumulative": "cumulative",
    "cumul": "cumulative",
    "varying": "varying",
    "vary": "varying",
}

_GENERIC_STATUS_TO_SZS = {
    "Theorem": SZSStatus.THEOREM.value,
    "Non-Theorem": SZSStatus.COUNTER_SATISFIABLE.value,
    "CounterSatisfiable": SZSStatus.COUNTER_SATISFIABLE.value,
    "Unsatisfiable": SZSStatus.UNSATISFIABLE.value,
    "Satisfiable": SZSStatus.SATISFIABLE.value,
    "ContradictoryAxioms": SZSStatus.CONTRADICTORY_AXIOMS.value,
}
_INTUITIONISTIC_STATUS_TO_SZS = {
    **_GENERIC_STATUS_TO_SZS,
    "Open": SZSStatus.COUNTER_SATISFIABLE.value,
}
_UNKNOWN_STATUS_LABELS = {"Unknown", "Unsolved"}


@dataclass(frozen=True, slots=True)
class BenchmarkStatus:
    label: str
    szs_status: str | None
    source: str


def benchmark_status(
    path: str | Path,
    *,
    logic: Logic,
    domain: Domain = "constant",
) -> BenchmarkStatus | None:
    text = _read_text(Path(path))
    if logic in {"D", "T", "S4", "S5"}:
        return _qmltp_status(text, logic=logic, domain=domain)
    if logic == "intuitionistic":
        return _intuitionistic_status(text)
    if logic == "classical":
        return _tptp_status(text)
    return None


def _qmltp_status(text: str, *, logic: Logic, domain: Domain) -> BenchmarkStatus | None:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = _SIMPLE_STATUS_RE.match(line)
        if match is None:
            continue
        domains = _domain_columns(match.group("label"))
        if not domains:
            continue
        for table_line in lines[index + 1 :]:
            if not table_line.startswith("%"):
                break
            row = _QMLTP_LOGIC_ROW_RE.match(table_line)
            if row is None:
                continue
            if row.group("logic") != logic:
                continue
            values = row.group("statuses").split()
            domain_index = _domain_index(domains, domain)
            if domain_index is None or domain_index >= len(values):
                return None
            label = values[domain_index]
            return BenchmarkStatus(
                label=label,
                szs_status=_status_label_to_szs(label, _GENERIC_STATUS_TO_SZS),
                source=_QMLTP_SOURCE,
            )
    return None


def _intuitionistic_status(text: str) -> BenchmarkStatus | None:
    for line in text.splitlines():
        match = _INTUITIONISTIC_STATUS_RE.match(line)
        if match is None:
            continue
        label = match.group("label").strip()
        return BenchmarkStatus(
            label=label,
            szs_status=_status_label_to_szs(label, _INTUITIONISTIC_STATUS_TO_SZS),
            source=_ILTP_SOURCE,
        )
    return None


def _tptp_status(text: str) -> BenchmarkStatus | None:
    for line in text.splitlines():
        match = _SIMPLE_STATUS_RE.match(line)
        if match is None:
            continue
        label = match.group("label").strip()
        if _domain_columns(label):
            continue
        return BenchmarkStatus(
            label=label,
            szs_status=_status_label_to_szs(label, _GENERIC_STATUS_TO_SZS),
            source=_TPTP_SOURCE,
        )
    return None


def _domain_columns(label: str) -> tuple[str, ...]:
    columns: list[str] = []
    for part in label.split():
        column = _DOMAIN_ALIASES.get(part.lower())
        if column is not None:
            columns.append(column)
    if set(columns) >= {"varying", "cumulative", "constant"}:
        return tuple(columns)
    return ()


def _domain_index(domains: tuple[str, ...], domain: Domain) -> int | None:
    normalized = _DOMAIN_ALIASES[domain]
    try:
        return domains.index(normalized)
    except ValueError:
        return None


def _status_label_to_szs(label: str, mapping: dict[str, str]) -> str | None:
    base_label = label.split("(", 1)[0].strip()
    if base_label in _UNKNOWN_STATUS_LABELS:
        return None
    return mapping.get(base_label)


def _read_text(path: Path) -> str:
    data = path.read_bytes()
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1")


__all__ = [
    "BenchmarkStatus",
    "benchmark_status",
]
