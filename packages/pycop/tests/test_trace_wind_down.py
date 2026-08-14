"""Post-proof wind-down: the reference keeps emitting after a rollout stops.

A rollout ends at the accepting state. leanCoP-family references go on
unwinding their Prolog choicepoints, emitting `cut` and `pathlim` on the way
out. Those events are not proof search, so trace parity ignores them -- but
only when that is demonstrably all they are.
"""

from __future__ import annotations

from pycop.parity.run_trace_parity import _strip_post_proof_wind_down as strip


def test_a_pure_wind_down_tail_is_stripped():
    assert strip(["start", "ext"], ["start", "ext", "cut", "cut", "pathlim"]) == [
        "start",
        "ext",
    ]


def test_a_tail_containing_search_is_kept():
    """One real event in the tail means the reference kept proving."""
    reference = ["start", "ext", "cut", "extension"]
    assert strip(["start", "ext"], reference) == reference


def test_a_divergence_before_the_tail_is_kept():
    """Stripping only applies when the native trace is a prefix."""
    reference = ["start", "ext", "cut"]
    assert strip(["start", "red"], reference) == reference


def test_a_longer_native_trace_is_untouched():
    assert strip(["a", "b", "c"], ["a", "b"]) == ["a", "b"]


def test_equal_traces_are_untouched():
    assert strip(["a", "b"], ["a", "b"]) == ["a", "b"]


def test_stripping_never_lengthens_or_reorders():
    native = ["start", "ext", "red"]
    reference = native + ["cut"] * 5 + ["pathlim"] * 3
    result = strip(native, reference)
    assert result == native
    assert len(result) <= len(reference)
