from core.services.imports import validate_csv


def test_csv_validation():
    ok, errors = validate_csv([{"date": "2025-01-01"}])
    assert not ok
    assert errors
