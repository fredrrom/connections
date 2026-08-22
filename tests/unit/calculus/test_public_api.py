from __future__ import annotations


def test_prover_public_api_exports_documented_boundary():
    from connections.calculus.actions import (
        Action,
        AnyApplyAction,
        ApplyAction,
        ApplyActions,
        ExtensionAction,
        FactorizationAction,
        ReductionAction,
        StartAction,
        UndoAction,
    )
    from connections.calculus.dynamics import Dynamics
    from connections.calculus.state import State
    from connections.run.prover import Problem, run_schedule as run_problem
    from connections.run.strategy import MatrixOptions, StrategySchedule

    assert run_problem is not None
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
