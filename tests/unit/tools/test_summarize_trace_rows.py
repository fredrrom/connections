from __future__ import annotations

from tools.parity.summarize_trace_rows import summarize_trace_rows


def test_summarize_trace_rows_counts_timeout_asymmetry_and_disagreements():
    summary = summarize_trace_rows(
        [
            {
                "name": "match.p",
                "native_status": "Theorem",
                "reference_status": "Theorem",
                "status_match": True,
                "trace_match": True,
            },
            {
                "name": "native-timeout.p",
                "native_status": "Timeout",
                "reference_status": "GaveUp",
                "status_match": False,
                "trace_match": False,
            },
            {
                "name": "reference-timeout.p",
                "native_status": "Theorem",
                "reference_status": "Timeout",
                "status_match": False,
                "trace_match": False,
            },
            {
                "name": "trace-diff.p",
                "native_status": "GaveUp",
                "reference_status": "GaveUp",
                "status_match": True,
                "trace_match": False,
            },
            {
                "name": "unsupported.p",
                "error": "unsupported input",
                "status_match": False,
                "trace_match": False,
            },
        ],
        examples=2,
    )

    assert summary["rows"] == 5
    assert summary["supported_rows"] == 4
    assert summary["error_rows"] == 1
    assert summary["trace_matches"] == 1
    assert summary["trace_disagreements"] == 3
    assert summary["non_timeout_trace_disagreements"] == 1
    assert summary["status_matches"] == 2
    assert summary["status_disagreements"] == 2
    assert summary["native_timeout_only"] == 1
    assert summary["reference_timeout_only"] == 1
    assert summary["examples"]["native_timeout_only"][0]["name"] == "native-timeout.p"
