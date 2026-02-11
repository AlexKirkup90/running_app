from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime, timedelta

try:
    from passlib.context import CryptContext

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
except Exception:  # pragma: no cover
    pwd_context = None

PASSWORD_REGEX = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z\d]).{10,128}$")


def validate_password_policy(password: str) -> tuple[bool, str]:
    if not PASSWORD_REGEX.match(password):
        return False, "Password must be 10+ chars with upper, lower, number, and symbol"
    return True, "ok"


def hash_password(password: str) -> str:
    valid, msg = validate_password_policy(password)
    if not valid:
        raise ValueError(msg)
    if pwd_context:
        return pwd_context.hash(password)
    return "sha256$" + hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    if password_hash.startswith("sha256$"):
        return password_hash == "sha256$" + hashlib.sha256(password.encode()).hexdigest()

    if pwd_context:
        try:
            return pwd_context.verify(password, password_hash)
        except Exception:
            return False

    return False


def account_locked(locked_until: datetime | None) -> bool:
    if not locked_until:
        return False
    now = datetime.now(UTC).replace(tzinfo=None)
    return locked_until > now


def apply_failed_login(failed_attempts: int, threshold: int = 5, lock_minutes: int = 15) -> tuple[int, datetime | None]:
    failed = failed_attempts + 1
    if failed >= threshold:
        return failed, datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=lock_minutes)
    return failed, None
