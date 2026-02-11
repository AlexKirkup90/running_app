from __future__ import annotations

import pandas as pd


def weekly_summary(logs_df: pd.DataFrame) -> pd.DataFrame:
    if logs_df.empty:
        return pd.DataFrame(columns=["week", "duration_min", "load_score", "sessions"])
    d = logs_df.copy()
    d["date"] = pd.to_datetime(d["date"])
    d["week"] = d["date"].dt.to_period("W").astype(str)
    out = d.groupby("week", as_index=False).agg(duration_min=("duration_min", "sum"), load_score=("load_score", "sum"), sessions=("id", "count"))
    return out
