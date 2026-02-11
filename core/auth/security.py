from __future__ import annotations

import datetime as dt
import hashlib
import re

try:
    from passlib.context import CryptContext
except Exception:  # pragma: no cover
    CryptContext = None

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto") if CryptContext else None


class PasswordPolicyError(ValueError):
    pass


def enforce_password_policy(password: str) -> None:
    if len(password) < 12:
        raise PasswordPolicyError("Password must be at least 12 characters")
    if not re.search(r"[A-Z]", password):
        raise PasswordPolicyError("Password must include uppercase")
    if not re.search(r"[a-z]", password):
        raise PasswordPolicyError("Password must include lowercase")
    if not re.search(r"\d", password):
        raise PasswordPolicyError("Password must include number")
    if not re.search(r"[^A-Za-z0-9]", password):
        raise PasswordPolicyError("Password must include symbol")


def hash_password(password: str) -> str:
    enforce_password_policy(password)
    if pwd_context:
        return pwd_context.hash(password)
    return "sha256$" + hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    if pwd_context and not password_hash.startswith("sha256$"):
        return pwd_context.verify(password, password_hash)
    return password_hash == ("sha256$" + hashlib.sha256(password.encode()).hexdigest())


def register_failed_attempt(user, lock_minutes: int = 15):
    user.failed_attempts += 1
    if user.failed_attempts >= 5:
        user.locked_until = dt.datetime.utcnow() + dt.timedelta(minutes=lock_minutes)


def can_authenticate(user) -> bool:
    return not user.locked_until or user.locked_until <= dt.datetime.utcnow()
