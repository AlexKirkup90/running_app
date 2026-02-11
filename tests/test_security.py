from core.security import apply_failed_login, hash_password, validate_password_policy, verify_password


def test_password_policy():
    ok, _ = validate_password_policy("StrongPass!123")
    assert ok
    ok2, _ = validate_password_policy("weak")
    assert not ok2


def test_lockout_policy():
    attempts, locked = apply_failed_login(4)
    assert attempts == 5
    assert locked is not None


def test_password_verify_supports_sha256_fallback_hashes():
    h = hash_password("StrongPass!123")
    assert verify_password("StrongPass!123", h)

    legacy = "sha256$" + __import__("hashlib").sha256("StrongPass!123".encode()).hexdigest()
    assert verify_password("StrongPass!123", legacy)
    assert not verify_password("WrongPass!123", legacy)
