"""JWT authentication for the REST API."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import select

from core.config import get_settings
from core.db import session_scope
from core.models import User
from core.security import verify_password

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: int
    athlete_id: Optional[int] = None


class TokenData(BaseModel):
    user_id: int
    username: str
    role: str
    athlete_id: Optional[int] = None


def create_access_token(data: dict) -> str:
    """Create a JWT access token with expiry from settings."""
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    to_encode = {**data, "exp": expire}
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def authenticate_user(username: str, password: str) -> Optional[User]:
    """Verify credentials and return User if valid, None otherwise."""
    with session_scope() as s:
        user = s.execute(select(User).where(User.username == username)).scalar_one_or_none()
        if not user:
            return None
        if not verify_password(password, user.password_hash):
            return None
        # Detach from session by capturing values
        return user


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> TokenData:
    """Decode JWT token and return current user data."""
    settings = get_settings()
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id: int = payload.get("user_id")
        username: str = payload.get("sub")
        role: str = payload.get("role")
        athlete_id = payload.get("athlete_id")
        if user_id is None or username is None:
            raise credentials_exception
        return TokenData(user_id=user_id, username=username, role=role, athlete_id=athlete_id)
    except JWTError:
        raise credentials_exception


def require_coach(current_user: Annotated[TokenData, Depends(get_current_user)]) -> TokenData:
    """Dependency that requires the current user to be a coach."""
    if current_user.role != "coach":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Coach role required")
    return current_user


def require_athlete(current_user: Annotated[TokenData, Depends(get_current_user)]) -> TokenData:
    """Dependency that requires the current user to be an athlete."""
    if current_user.role != "client":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Athlete role required")
    if not current_user.athlete_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No athlete profile linked")
    return current_user
