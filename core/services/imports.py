from __future__ import annotations

import pandas as pd

REQUIRED_COLUMNS = ["date", "duration", "distance", "avg_hr", "max_hr", "avg_pace", "session_type"]


def parse_generic_csv(content: bytes) -> tuple[pd.DataFrame, list[str]]:
    df = pd.read_csv(pd.io.common.BytesIO(content))
    errors = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    return df, errors
