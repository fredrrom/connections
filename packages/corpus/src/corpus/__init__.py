"""Corpus runs: choosing problems, sharding them, recording what happened.

Prover-agnostic. A caller supplies a callable from problem path to `Attempt`;
nothing here knows what a prover is, so pycop, satcop and learned policies all
run through the same machinery.
"""

from corpus.record import (
    Attempt,
    Summary,
    read_attempts,
    summarize,
    write_attempts,
)
from corpus.run import CorpusRun, Prover, corpus_run
from corpus.selection import Shard, glob_anchor, select_problems, shard

__all__ = [
    "Attempt",
    "CorpusRun",
    "Prover",
    "Shard",
    "Summary",
    "corpus_run",
    "glob_anchor",
    "read_attempts",
    "select_problems",
    "shard",
    "summarize",
    "write_attempts",
]
