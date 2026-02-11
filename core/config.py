import os
from functools import lru_cache


@lru_cache(maxsize=1)
def database_url() -> str:
    url = os.getenv("DATABASE_URL") or os.getenv("STREAMLIT_DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    return url


def app_env() -> str:
    return os.getenv("APP_ENV", "dev")
