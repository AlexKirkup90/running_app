"""Extended security tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.security import (
    account_locked,
    apply_failed_login,
    hash_password,
    validate_password_policy,
    verify_password,
)


def test_validate_password_policy_strong():
    ok, msg = validate_password_policy("MyStr0ng!Pass")
    assert ok is True
    assert msg == "ok"


def test_validate_password_policy_too_short():
    ok, msg = validate_password_policy("Sh0rt!aa")
    assert ok is False


def test_validate_password_policy_no_uppercase():
    ok, msg = validate_password_policy("nostrongpass!123")
    assert ok is False


def test_validate_password_policy_no_digit():
    ok, msg = validate_password_policy("NoDigitHere!pass")
    assert ok is False


def test_validate_password_policy_no_symbol():
    ok, msg = validate_password_policy("NoSymbol1pass")
    assert ok is False


def test_hash_and_verify_roundtrip():
    password = "TestPassword!123"
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True


def test_verify_wrong_password():
    hashed = hash_password("CorrectPass!123")
    assert verify_password("WrongPass!123", hashed) is False


def test_hash_password_rejects_weak():
    try:
        hash_password("weak")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_account_locked_active():
    future = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=10)
    assert account_locked(future) is True


def test_account_locked_expired():
    past = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=10)
    assert account_locked(past) is False


def test_account_locked_none():
    assert account_locked(None) is False


def test_apply_failed_login_below_threshold():
    failed, locked = apply_failed_login(2)
    assert failed == 3
    assert locked is None


def test_apply_failed_login_at_threshold():
    failed, locked = apply_failed_login(4)
    assert failed == 5
    assert locked is not None
    assert locked > datetime.utcnow()
