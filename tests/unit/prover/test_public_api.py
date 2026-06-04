from __future__ import annotations


def test_prover_public_api_exports_documented_boundary():
    from connections.prover import (
        Action,
        AnyApplyAction,
        ApplyAction,
        ApplyActions,
        Dynamics,
        ExtensionAction,
        FactorizationAction,
        MatrixOptions,
        Problem,
        Prover,
        ProverHook,
        ReductionAction,
        StartAction,
        State,
        StrategySchedule,
        UndoAction,
    )

    assert Prover is not None
    assert ProverHook is not None
    assert Problem is not None
    assert State is not None
    assert Dynamics is not None
    assert MatrixOptions is not None
    assert StrategySchedule is not None
    assert Action is not None
    assert AnyApplyAction is not None
    assert ApplyAction is not None
    assert ApplyActions is not None
    assert ExtensionAction is not None
    assert FactorizationAction is not None
    assert ReductionAction is not None
    assert StartAction is not None
    assert UndoAction is not None
