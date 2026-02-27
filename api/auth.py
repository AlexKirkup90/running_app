from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.config import get_settings


bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthPrincipal:
    user_id: int
    username: str
    role: str
    athlete_id: Optional[int]
    exp: int


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * ((4 - (len(data) % 4)) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def _sign(signing_input: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    return _b64url_encode(digest)


def issue_access_token(*, user_id: int, username: str, role: str, athlete_id: Optional[int], expires_in_seconds: int) -> str:
    settings = get_settings()
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": int(user_id),
        "username": str(username),
        "role": str(role),
        "athlete_id": athlete_id,
        "exp": int(time.time()) + int(expires_in_seconds),
    }
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}"
    signature = _sign(signing_input, settings.jwt_secret_key)
    return f"{signing_input}.{signature}"


def decode_access_token(token: str) -> AuthPrincipal:
    settings = get_settings()
    try:
        header_b64, payload_b64, signature = token.split(".", 2)
    except ValueError as exc:  # pragma: no cover - trivial parse failure
        raise HTTPException(status_code=401, detail={"code": "INVALID_TOKEN"}) from exc

    signing_input = f"{header_b64}.{payload_b64}"
    expected_sig = _sign(signing_input, settings.jwt_secret_key)
    if not hmac.compare_digest(signature, expected_sig):
        raise HTTPException(status_code=401, detail={"code": "INVALID_TOKEN"})

    try:
        payload = json.loads(_b64url_decode(payload_b64))
    except Exception as exc:
        raise HTTPException(status_code=401, detail={"code": "INVALID_TOKEN"}) from exc

    exp = int(payload.get("exp") or 0)
    if exp <= int(time.time()):
        raise HTTPException(status_code=401, detail={"code": "TOKEN_EXPIRED"})

    try:
        return AuthPrincipal(
            user_id=int(payload["sub"]),
            username=str(payload["username"]),
            role=str(payload["role"]),
            athlete_id=(int(payload["athlete_id"]) if payload.get("athlete_id") is not None else None),
            exp=exp,
        )
    except Exception as exc:
        raise HTTPException(status_code=401, detail={"code": "INVALID_TOKEN"}) from exc


def get_current_principal(credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)) -> AuthPrincipal:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail={"code": "AUTH_REQUIRED"})
    return decode_access_token(credentials.credentials)


def require_roles(*allowed_roles: str) -> Callable[[AuthPrincipal], AuthPrincipal]:
    allowed = {r.lower() for r in allowed_roles}

    def _dependency(principal: AuthPrincipal = Depends(get_current_principal)) -> AuthPrincipal:
        role = principal.role.lower()
        # Admin can access all role-scoped endpoints by design in Stage 1 for progress viewing / operations.
        if role != "admin" and role not in allowed:
            raise HTTPException(
                status_code=403,
                detail={"code": "FORBIDDEN_ROLE", "required_roles": sorted(allowed), "role": principal.role},
            )
        return principal

    return _dependency


def require_athlete_access(athlete_id: int, principal: AuthPrincipal = Depends(get_current_principal)) -> AuthPrincipal:
    role = principal.role.lower()
    if role in {"coach", "admin"}:
        return principal
    if principal.athlete_id is None or int(principal.athlete_id) != int(athlete_id):
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN_ATHLETE_SCOPE", "athlete_id": athlete_id, "principal_athlete_id": principal.athlete_id},
        )
    return principal
