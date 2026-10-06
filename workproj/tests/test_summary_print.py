"""Unit tests for console summary table printing."""

from typing import Any

from main import print_summary


def test_print_summary_normal(capsys: Any) -> None:
    """Validate print_summary output contains source names, totals, and Reconciles OK."""
    summary = {
        "duration_seconds": 12.34,
        "per_source": {
            "Books to Scrape": {
                "collected": 1000,
                "cleaned": 1000,
                "rejected": 0,
                "duplicates_removed": 1,
                "final_count": 999,
            },
            "Quotes to Scrape": {
                "collected": 100,
                "cleaned": 100,
                "rejected": 0,
                "duplicates_removed": 0,
                "final_count": 100,
            },
        },
        "totals": {
            "collected": 1100,
            "cleaned": 1100,
            "rejected": 0,
            "duplicates_detected": 1,
            "final_record_count": 1099,
            "reconciles": True,
        },
    }

    print_summary(summary)
    captured = capsys.readouterr().out
    lines = [line for line in captured.splitlines() if line.strip()]

    # Contains both source names
    assert "Books to Scrape" in captured
    assert "Quotes to Scrape" in captured

    # Contains Totals and Reconciles OK
    assert "Totals" in captured
    assert "1100" in captured
    assert "1099" in captured
    assert "Reconciles: OK" in captured
    assert "12.34s" in captured
    assert "output/final_dataset.csv" in captured
    assert "output/summary_report.json" in captured

    # Must be at most 20 lines
    assert len(lines) <= 20


def test_print_summary_missing_keys(capsys: Any) -> None:
    """Empty or incomplete summary dict does not raise and handles missing keys safely."""
    print_summary({})
    captured = capsys.readouterr().out
    assert "Totals" in captured
    assert "Reconciles: MISMATCH" in captured


def test_print_summary_reconciles_flag(capsys: Any) -> None:
    """Verifies that reconciles flag toggles correctly between OK and MISMATCH."""
    print_summary({"totals": {"reconciles": True}})
    out_ok = capsys.readouterr().out
    assert "Reconciles: OK" in out_ok

    print_summary({"totals": {"reconciles": False}})
    out_mismatch = capsys.readouterr().out
    assert "Reconciles: MISMATCH" in out_mismatch
