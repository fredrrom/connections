from __future__ import annotations

from connections.policy import DFSOptions, IterativeDeepeningOptions
from connections.prover.strategy import MatrixOptions
from connections.pycop.settings_codec import LeancopSettingsCodec
from connections.pycop.strategy import PycopStrategy


def test_pycop_strategy_defaults():
    strategy = PycopStrategy()
    assert strategy.matrix.translation == "default"
    assert strategy.matrix.reorder == 0
    assert strategy.matrix.start_clauses == "positive"
    assert strategy.dfs.cut is False
    assert strategy.dfs.scut is False
    assert strategy.dfs.factorization == "equal"
    assert strategy.dfs.backtrack == "step"
    assert strategy.id.comp is None
    assert strategy.id.initial_depth == 1


def test_leancop_settings_codec_to_token_list_from_pycop_strategy():
    strategy = PycopStrategy(
        matrix=MatrixOptions(
            translation="def",
            reorder=2,
            start_clauses="conjecture",
        )
    )
    assert LeancopSettingsCodec.to_token_list(strategy) == "[def,conj,reo(2)]"
    assert LeancopSettingsCodec.to_token_list(PycopStrategy()) == "[]"
    assert (
        LeancopSettingsCodec.to_token_list(
            PycopStrategy(matrix=MatrixOptions(translation="nodef"))
        )
        == "[nodef]"
    )


def test_pycop_strategy_carries_policy_fields():
    strategy = PycopStrategy(
        dfs=DFSOptions(cut=True, factorization="equal"),
        id=IterativeDeepeningOptions(initial_depth=3),
    )
    assert strategy.id.initial_depth == 3
    assert strategy.dfs.cut is True


def test_leancop_settings_codec_from_tokens_defaults_when_none():
    strategy = LeancopSettingsCodec.from_tokens(None)
    assert strategy == PycopStrategy()


def test_leancop_settings_codec_from_tokens_supports_translation_and_search_flags():
    strategy = LeancopSettingsCodec.from_tokens(
        ["def", "conj", "reo(2)", "cut", "scut", "comp(7)"]
    )
    assert strategy.matrix.translation == "def"
    assert strategy.matrix.start_clauses == "conjecture"
    assert strategy.matrix.reorder == 2
    assert strategy.dfs.cut is True
    assert strategy.dfs.scut is True
    assert strategy.id.comp == 7


def test_leancop_settings_codec_from_tokens_prefers_nodef_over_def():
    strategy = LeancopSettingsCodec.from_tokens(["def", "nodef", "def"])
    assert strategy.matrix.translation == "nodef"
