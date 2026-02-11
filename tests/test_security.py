from core.security import apply_failed_login, validate_password_policy


def test_password_policy():
    ok, _ = validate_password_policy("StrongPass!123")
    assert ok
    ok2, _ = validate_password_policy("weak")
    assert not ok2


def test_lockout_policy():
    attempts, locked = apply_failed_login(4)
    assert attempts == 5
    assert locked is not None
