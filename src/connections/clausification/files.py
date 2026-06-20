from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from connections.clausification.translate import (
    ClausificationTranslationMode,
    StartClausesMode,
    clausify,
)
from connections.syntax.logic import Domain, Logic
from connections.syntax.matrix import Matrix
from connections.trace_logging import TRACE_LEVEL, clausification_trace_logger, trace


def matrix_from_file(
    path: str | Path,
    *,
    translation: ClausificationTranslationMode = "default",
    reorder: int = 0,
    start_clauses: StartClausesMode = "positive",
    logic: Logic = "classical",
    domain: Domain = "constant",
    source_file_dirs: Iterable[str | Path] = (),
) -> Matrix:
    """Load a matrix from a source file using the native parser and translator."""

    _ = domain
    resolved_source_file_dirs = tuple(
        Path(directory).resolve() for directory in source_file_dirs
    )

    from connections.parsing.tptp.parser import parse_tptp_file

    if clausification_trace_logger.isEnabledFor(TRACE_LEVEL):
        trace(clausification_trace_logger, "%s", "matrix.from_file.start")
    parsed = parse_tptp_file(path, source_roots=resolved_source_file_dirs)
    matrix = clausify(
        parsed,
        translation=translation,
        reorder=reorder,
        start_clauses=start_clauses,
        logic=logic,
    )
    if clausification_trace_logger.isEnabledFor(TRACE_LEVEL):
        trace(clausification_trace_logger, "%s", "matrix.from_file.done")
    return matrix


__all__ = ["matrix_from_file"]
