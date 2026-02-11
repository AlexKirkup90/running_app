import datetime as dt

import pytest

from core.auth.security import PasswordPolicyError, can_authenticate, enforce_password_policy, register_failed_attempt


class U:
    def __init__(self):
        self.failed_attempts = 0
        self.locked_until = None


def test_password_policy_rejects_weak():
    with pytest.raises(PasswordPolicyError):
        enforce_password_policy("weak")


def test_lockout_after_retries():
    u = U()
    for _ in range(5):
        register_failed_attempt(u)
    assert u.locked_until is not None
    assert not can_authenticate(u)
    u.locked_until = dt.datetime.utcnow() - dt.timedelta(minutes=1)
    assert can_authenticate(u)
