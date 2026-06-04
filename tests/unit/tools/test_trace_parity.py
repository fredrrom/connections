from __future__ import annotations

from tools.parity.run_trace_parity import _compact_trace_row


def test_compact_trace_row_keeps_summary_fields_without_event_arrays():
    row = {
        "name": "problem.p",
        "trace_match": False,
        "first_difference": {"index": 2},
        "native_trace_length": 3,
        "reference_trace_length": 4,
        "native_trace": ["start", "extension", "backtrack"],
        "reference_trace": ["start", "extension", "pathlim_hit", "backtrack"],
    }

    compact = _compact_trace_row(row)

    assert compact["name"] == "problem.p"
    assert compact["trace_match"] is False
    assert compact["first_difference"] == {"index": 2}
    assert compact["native_trace_length"] == 3
    assert compact["reference_trace_length"] == 4
    assert "native_trace" not in compact
    assert "reference_trace" not in compact
    assert "native_trace" in row
