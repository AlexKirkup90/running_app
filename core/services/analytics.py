from __future__ import annotations

import pandas as pd


def weekly_summary(logs: pd.DataFrame) -> pd.DataFrame:
    if logs.empty:
        return pd.DataFrame(columns=["week", "duration_min", "load_score", "sessions"])
    frame = logs.copy()
    frame["week"] = pd.to_datetime(frame["log_date"]).dt.to_period("W").astype(str)
    return frame.groupby("week", as_index=False).agg(
        duration_min=("duration_min", "sum"),
        load_score=("load_score", "sum"),
        sessions=("log_date", "count"),
    )
