from __future__ import annotations

from connections.policy import FirstActionIDPolicy
from connections.prover.strategy import MatrixOptions, PolicyOptions, Strategy
from provers.pycop.settings_codec import LeancopSettingsCodec


def _leancop_strategy(
    *,
    matrix: MatrixOptions | None = None,
    **policy_args,
) -> Strategy:
    return Strategy(
        matrix=matrix or MatrixOptions(),
        policy=PolicyOptions(policy_class=FirstActionIDPolicy, args=policy_args),
    )


def _args(strategy: Strategy):
    return dict(strategy.policy.args)


def test_strategy_defaults():
    strategy = LeancopSettingsCodec.from_tokens(None)
    matrix = strategy.matrix
    args = _args(strategy)
    assert matrix.translation == "default"
    assert matrix.reorder == 0
    assert matrix.start_clauses == "positive"
    assert strategy.policy.policy_class is FirstActionIDPolicy
    assert args["factorization"] == "equal"


def test_leancop_settings_codec_to_token_list_from_strategy():
    strategy = _leancop_strategy(
        matrix=MatrixOptions(
            translation="def",
            reorder=2,
            start_clauses="conjecture",
        )
    )
    assert LeancopSettingsCodec.to_token_list(strategy) == "[def,conj,reo(2)]"
    assert (
        LeancopSettingsCodec.to_token_list(LeancopSettingsCodec.from_tokens(None))
        == "[]"
    )
    assert (
        LeancopSettingsCodec.to_token_list(
            _leancop_strategy(matrix=MatrixOptions(translation="nodef"))
        )
        == "[nodef]"
    )


def test_strategy_carries_policy_args():
    strategy = _leancop_strategy(
        cut=True,
        factorization="equal",
        initial_depth=3,
    )
    args = _args(strategy)
    assert args["initial_depth"] == 3
    assert args["cut"] is True


def test_leancop_settings_codec_from_tokens_defaults_when_none():
    strategy = LeancopSettingsCodec.from_tokens(None)
    assert strategy == _leancop_strategy(
        cut=False,
        scut=False,
        comp=None,
        factorization="equal",
    )


def test_leancop_settings_codec_from_tokens_supports_translation_and_search_flags():
    strategy = LeancopSettingsCodec.from_tokens(
        ["def", "conj", "reo(2)", "cut", "scut", "comp(7)"]
    )
    matrix = strategy.matrix
    args = _args(strategy)
    assert matrix.translation == "def"
    assert matrix.start_clauses == "conjecture"
    assert matrix.reorder == 2
    assert args["cut"] is True
    assert args["scut"] is True
    assert args["comp"] == 7


def test_leancop_settings_codec_from_tokens_prefers_nodef_over_def():
    strategy = LeancopSettingsCodec.from_tokens(["def", "nodef", "def"])
    assert strategy.matrix.translation == "nodef"
