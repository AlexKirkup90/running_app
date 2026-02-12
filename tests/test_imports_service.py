"""Tests for import service."""

from __future__ import annotations

from core.services.imports import REQUIRED_COLUMNS, parse_generic_csv


def test_parse_generic_csv_valid():
    header = ",".join(REQUIRED_COLUMNS) + "\n"
    row = "2026-01-01,45,8.0,140,165,300,Easy Run\n"
    content = (header + row).encode()
    df, errors = parse_generic_csv(content)
    assert errors == []
    assert len(df) == 1
    assert df.iloc[0]["duration"] == 45


def test_parse_generic_csv_missing_columns():
    content = b"date,duration\n2026-01-01,45\n"
    df, errors = parse_generic_csv(content)
    assert len(errors) > 0
    assert "distance" in errors
    assert "avg_hr" in errors


def test_parse_generic_csv_all_columns_present():
    header = ",".join(REQUIRED_COLUMNS)
    content = (header + "\n").encode()
    df, errors = parse_generic_csv(content)
    assert errors == []
    assert len(df) == 0
