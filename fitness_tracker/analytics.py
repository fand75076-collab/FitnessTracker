from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

SCIENCE_STRENGTH_BODY_PARTS = ["胸", "背", "腿", "肩", "手臂", "核心"]
REP_ZONE_ORDER = ["1-5 力量", "6-7 过渡", "8-12 ACSM", "13-15 高次数", "16+ 耐力"]


@dataclass(frozen=True)
class SummaryMetrics:
    total_sets: int
    total_volume: float
    active_days: int
    max_estimated_1rm: float


def empty_metrics() -> SummaryMetrics:
    return SummaryMetrics(total_sets=0, total_volume=0.0, active_days=0, max_estimated_1rm=0.0)


def build_summary_metrics(dataframe: pd.DataFrame) -> SummaryMetrics:
    if dataframe.empty:
        return empty_metrics()

    return SummaryMetrics(
        total_sets=int(len(dataframe)),
        total_volume=float(dataframe["volume_kg"].sum()),
        active_days=int(dataframe["day"].nunique()),
        max_estimated_1rm=float(dataframe["estimated_1rm"].max()),
    )


def aggregate_volume(dataframe: pd.DataFrame, grain: str) -> pd.DataFrame:
    if dataframe.empty:
        return pd.DataFrame(columns=["period", "volume_kg", "sets"])

    grouped = (
        dataframe.groupby(grain, as_index=False)
        .agg(volume_kg=("volume_kg", "sum"), sets=("id", "count"))
        .rename(columns={grain: "period"})
        .sort_values("period")
    )
    return grouped


def aggregate_body_part(dataframe: pd.DataFrame) -> pd.DataFrame:
    if dataframe.empty:
        return pd.DataFrame(columns=["body_part", "volume_kg"])

    return (
        dataframe.groupby("body_part", as_index=False)
        .agg(volume_kg=("volume_kg", "sum"), sets=("id", "count"))
        .sort_values(["volume_kg", "sets"], ascending=[False, False])
    )


def build_exercise_trend(dataframe: pd.DataFrame, exercise_name: str, grain: str) -> pd.DataFrame:
    if dataframe.empty or not exercise_name:
        return pd.DataFrame(columns=["period", "best_weight_kg", "best_estimated_1rm", "total_volume_kg"])

    filtered = dataframe[dataframe["exercise_name"] == exercise_name]
    if filtered.empty:
        return pd.DataFrame(columns=["period", "best_weight_kg", "best_estimated_1rm", "total_volume_kg"])

    return (
        filtered.groupby(grain, as_index=False)
        .agg(
            best_weight_kg=("weight_kg", "max"),
            best_estimated_1rm=("estimated_1rm", "max"),
            total_volume_kg=("volume_kg", "sum"),
        )
        .rename(columns={grain: "period"})
        .sort_values("period")
    )


def build_max_weight_progress(dataframe: pd.DataFrame, grain: str) -> pd.DataFrame:
    if dataframe.empty:
        return pd.DataFrame(
            columns=[
                "period",
                "exercise_name",
                "best_weight_kg",
                "previous_best_weight_kg",
                "weight_change_kg",
                "weight_change_pct",
                "sets",
            ]
        )

    progress = (
        dataframe.groupby(["exercise_name", grain], as_index=False)
        .agg(best_weight_kg=("weight_kg", "max"), sets=("id", "count"))
        .rename(columns={grain: "period"})
        .sort_values(["exercise_name", "period"])
    )
    progress["previous_best_weight_kg"] = progress.groupby("exercise_name")["best_weight_kg"].shift(1)
    progress["weight_change_kg"] = progress["best_weight_kg"] - progress["previous_best_weight_kg"]
    previous = progress["previous_best_weight_kg"]
    # Keep NaN for periods without a valid prior baseline so downstream filters
    # (e.g. weight_change_pct.notna()) can exclude first-appearance rows.
    valid_previous = previous.where(previous.notna() & (previous > 0))
    progress["weight_change_pct"] = progress["weight_change_kg"] / valid_previous * 100
    return progress


def _science_reference_date(dataframe: pd.DataFrame, reference_date: object | None = None) -> pd.Timestamp:
    if reference_date is not None:
        return pd.Timestamp(reference_date).floor("D")
    if dataframe.empty or "day" not in dataframe.columns:
        return pd.Timestamp.today().floor("D")
    return pd.Timestamp(dataframe["day"].max()).floor("D")


def _strength_rows(dataframe: pd.DataFrame) -> pd.DataFrame:
    if dataframe.empty or "body_part" not in dataframe.columns:
        return dataframe.copy()
    return dataframe[dataframe["body_part"].isin(SCIENCE_STRENGTH_BODY_PARTS)].copy()


def rep_zone(reps: int | float) -> str:
    if reps <= 5:
        return "1-5 力量"
    if reps <= 7:
        return "6-7 过渡"
    if reps <= 12:
        return "8-12 ACSM"
    if reps <= 15:
        return "13-15 高次数"
    return "16+ 耐力"


def build_science_summary(
    dataframe: pd.DataFrame,
    reference_date: object | None = None,
) -> dict[str, object]:
    if dataframe.empty:
        return {
            "reference_date": None,
            "strength_days_7d": 0,
            "frequency_status": "暂无",
            "active_body_parts_28d": 0,
            "coverage_status": "暂无",
            "rep_8_12_pct": 0.0,
            "acute_volume_ratio": None,
            "load_status": "暂无",
            "recovery_alerts": 0,
        }

    ref = _science_reference_date(dataframe, reference_date)
    strength = _strength_rows(dataframe)
    recent_7 = strength[(strength["day"] >= ref - pd.Timedelta(days=6)) & (strength["day"] <= ref)]
    recent_28 = strength[(strength["day"] >= ref - pd.Timedelta(days=27)) & (strength["day"] <= ref)]
    previous_28 = strength[(strength["day"] >= ref - pd.Timedelta(days=35)) & (strength["day"] < ref - pd.Timedelta(days=6))]

    strength_days_7d = int(recent_7["day"].nunique()) if not recent_7.empty else 0
    active_body_parts_28d = int(recent_28["body_part"].nunique()) if not recent_28.empty else 0
    rep_8_12_pct = float(((recent_28["reps"] >= 8) & (recent_28["reps"] <= 12)).mean() * 100) if not recent_28.empty else 0.0

    acute_volume = float(recent_7["volume_kg"].sum()) if not recent_7.empty else 0.0
    previous_weekly_avg = float(previous_28["volume_kg"].sum() / 4.0) if not previous_28.empty else 0.0
    acute_ratio = acute_volume / previous_weekly_avg if previous_weekly_avg > 0 else None

    if strength_days_7d >= 2:
        frequency_status = "达标"
    elif strength_days_7d == 1:
        frequency_status = "偏低"
    else:
        frequency_status = "缺失"

    if active_body_parts_28d >= len(SCIENCE_STRENGTH_BODY_PARTS):
        coverage_status = "覆盖完整"
    elif active_body_parts_28d >= 4:
        coverage_status = "基本覆盖"
    elif active_body_parts_28d > 0:
        coverage_status = "有明显缺口"
    else:
        coverage_status = "缺失"

    if acute_ratio is None:
        load_status = "基线不足"
    elif acute_ratio < 0.75:
        load_status = "负荷下降"
    elif acute_ratio <= 1.30:
        load_status = "负荷稳定"
    else:
        load_status = "负荷跳升"

    recovery_alerts = len(build_recovery_alerts(strength))

    return {
        "reference_date": ref,
        "strength_days_7d": strength_days_7d,
        "frequency_status": frequency_status,
        "active_body_parts_28d": active_body_parts_28d,
        "coverage_status": coverage_status,
        "rep_8_12_pct": round(rep_8_12_pct, 1),
        "acute_volume_ratio": round(float(acute_ratio), 2) if acute_ratio is not None else None,
        "load_status": load_status,
        "recovery_alerts": int(recovery_alerts),
    }


def build_body_part_science_table(
    dataframe: pd.DataFrame,
    lookback_days: int = 28,
    reference_date: object | None = None,
) -> pd.DataFrame:
    columns = [
        "body_part",
        "sets",
        "avg_sets_per_week",
        "training_days",
        "volume_kg",
        "avg_reps",
        "rep_8_12_pct",
        "days_since_last",
        "status",
        "recommendation",
    ]
    if dataframe.empty:
        return pd.DataFrame(columns=columns)

    ref = _science_reference_date(dataframe, reference_date)
    start = ref - pd.Timedelta(days=max(0, lookback_days - 1))
    recent = _strength_rows(dataframe)
    recent = recent[(recent["day"] >= start) & (recent["day"] <= ref)].copy()
    weeks = max(lookback_days / 7.0, 1.0)

    rows = []
    for body_part in SCIENCE_STRENGTH_BODY_PARTS:
        part = recent[recent["body_part"] == body_part]
        sets = int(len(part))
        avg_sets = sets / weeks
        training_days = int(part["day"].nunique()) if sets else 0
        volume = float(part["volume_kg"].sum()) if sets else 0.0
        avg_reps = float(part["reps"].mean()) if sets else 0.0
        rep_pct = float(((part["reps"] >= 8) & (part["reps"] <= 12)).mean() * 100) if sets else 0.0
        if sets:
            days_since_last = int((ref - pd.Timestamp(part["day"].max())).days)
        else:
            days_since_last = None

        if avg_sets >= 10:
            status = "增肌量充足"
            recommendation = "维持质量，优先小幅渐进。"
        elif avg_sets >= 5:
            status = "中等刺激"
            recommendation = "若目标是增肌，可逐步加到每周约10组。"
        elif avg_sets >= 2:
            status = "健康底线"
            recommendation = "能维持习惯，但专项提升刺激偏低。"
        elif sets > 0:
            status = "刺激不足"
            recommendation = "补足第二次训练或增加少量有效组。"
        else:
            status = "近28天缺失"
            recommendation = "下周安排至少1-2次覆盖。"

        rows.append(
            {
                "body_part": body_part,
                "sets": sets,
                "avg_sets_per_week": round(avg_sets, 1),
                "training_days": training_days,
                "volume_kg": round(volume, 1),
                "avg_reps": round(avg_reps, 1),
                "rep_8_12_pct": round(rep_pct, 1),
                "days_since_last": days_since_last,
                "status": status,
                "recommendation": recommendation,
            }
        )

    return pd.DataFrame(rows, columns=columns)


def build_rep_zone_distribution(
    dataframe: pd.DataFrame,
    lookback_days: int = 28,
    reference_date: object | None = None,
) -> pd.DataFrame:
    if dataframe.empty:
        return pd.DataFrame(columns=["rep_zone", "sets", "pct"])

    ref = _science_reference_date(dataframe, reference_date)
    start = ref - pd.Timedelta(days=max(0, lookback_days - 1))
    recent = _strength_rows(dataframe)
    recent = recent[(recent["day"] >= start) & (recent["day"] <= ref)].copy()
    if recent.empty:
        return pd.DataFrame({"rep_zone": REP_ZONE_ORDER, "sets": 0, "pct": 0.0})

    recent["rep_zone"] = recent["reps"].map(rep_zone)
    counts = recent["rep_zone"].value_counts().reindex(REP_ZONE_ORDER, fill_value=0)
    total = counts.sum()
    return pd.DataFrame(
        {
            "rep_zone": counts.index,
            "sets": counts.values.astype(int),
            "pct": (counts.values / total * 100).round(1) if total else 0.0,
        }
    )


def build_recovery_alerts(dataframe: pd.DataFrame, min_hours: int = 48) -> pd.DataFrame:
    columns = ["body_part", "previous_session", "current_session", "hours_between", "sets"]
    if dataframe.empty or "session_id" not in dataframe.columns:
        return pd.DataFrame(columns=columns)

    sessions = (
        _strength_rows(dataframe)
        .groupby(["body_part", "session_id"], as_index=False)
        .agg(session_start=("completed_at", "min"), sets=("id", "count"))
        .sort_values(["body_part", "session_start"])
    )
    if sessions.empty:
        return pd.DataFrame(columns=columns)

    sessions["previous_session"] = sessions.groupby("body_part")["session_start"].shift(1)
    sessions["hours_between"] = (
        sessions["session_start"] - sessions["previous_session"]
    ).dt.total_seconds().div(3600)
    alerts = sessions[
        sessions["previous_session"].notna()
        & (sessions["hours_between"] > 0)
        & (sessions["hours_between"] < min_hours)
    ].copy()
    if alerts.empty:
        return pd.DataFrame(columns=columns)

    alerts = alerts.rename(columns={"session_start": "current_session"})
    alerts["hours_between"] = alerts["hours_between"].round(1)
    return alerts[columns].sort_values("current_session", ascending=False)


def build_progression_candidates(
    dataframe: pd.DataFrame,
    target_reps: int = 12,
    min_sessions: int = 2,
) -> pd.DataFrame:
    columns = [
        "exercise_name",
        "latest_session",
        "latest_weight_kg",
        "latest_max_reps",
        "previous_max_reps",
        "suggested_low_kg",
        "suggested_high_kg",
        "reason",
    ]
    if dataframe.empty or "session_id" not in dataframe.columns:
        return pd.DataFrame(columns=columns)

    sessions = (
        dataframe.groupby(["exercise_name", "session_id"], as_index=False)
        .agg(
            latest_session=("completed_at", "max"),
            latest_weight_kg=("weight_kg", "max"),
            latest_max_reps=("reps", "max"),
            sets=("id", "count"),
        )
        .sort_values(["exercise_name", "latest_session"])
    )

    rows = []
    for exercise, group in sessions.groupby("exercise_name"):
        recent = group.tail(min_sessions)
        if len(recent) < min_sessions:
            continue
        latest = recent.iloc[-1]
        previous = recent.iloc[-2]
        if latest["latest_max_reps"] >= target_reps and previous["latest_max_reps"] >= target_reps:
            weight = float(latest["latest_weight_kg"])
            rows.append(
                {
                    "exercise_name": exercise,
                    "latest_session": latest["latest_session"],
                    "latest_weight_kg": round(weight, 1),
                    "latest_max_reps": round(float(latest["latest_max_reps"]), 1),
                    "previous_max_reps": round(float(previous["latest_max_reps"]), 1),
                    "suggested_low_kg": round(weight * 1.02, 1),
                    "suggested_high_kg": round(weight * 1.10, 1),
                    "reason": f"连续{min_sessions}次训练平均次数达到{target_reps}+，可考虑小幅加重。",
                }
            )

    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows, columns=columns).sort_values("latest_session", ascending=False)


def summarize_latest_max_weight_progress(progress: pd.DataFrame) -> dict[str, object]:
    if progress.empty:
        return {
            "period": None,
            "exercise_name": "",
            "weight_change_pct": None,
            "weight_change_kg": None,
            "improved_exercises": 0,
        }

    improved = progress[
        progress["weight_change_pct"].notna()
        & (progress["weight_change_kg"] > 0)
    ].copy()
    if improved.empty:
        return {
            "period": progress["period"].max(),
            "exercise_name": "",
            "weight_change_pct": None,
            "weight_change_kg": None,
            "improved_exercises": 0,
        }

    latest_period = improved["period"].max()
    latest = improved[improved["period"] == latest_period].copy()
    best_row = latest.sort_values(["weight_change_pct", "weight_change_kg"], ascending=[False, False]).iloc[0]
    return {
        "period": latest_period,
        "exercise_name": str(best_row["exercise_name"]),
        "weight_change_pct": float(best_row["weight_change_pct"]),
        "weight_change_kg": float(best_row["weight_change_kg"]),
        "improved_exercises": int(len(latest)),
    }


def build_session_summary(dataframe: pd.DataFrame) -> pd.DataFrame:
    if dataframe.empty or "session_id" not in dataframe.columns:
        return pd.DataFrame(columns=[
            "session_id", "date", "body_parts", "exercise_count",
            "total_sets", "total_volume_kg", "max_weight_kg", "duration_minutes",
        ])

    sessions = []
    for sid, group in dataframe.groupby("session_id"):
        group_sorted = group.sort_values("completed_at")
        date = group_sorted["day"].iloc[0]
        parts = ", ".join(sorted(group_sorted["body_part"].unique()))
        exercises = group_sorted["exercise_name"].nunique()
        total_sets = len(group_sorted)
        total_vol = group_sorted["volume_kg"].sum()
        max_w = group_sorted["weight_kg"].max()
        t_min = group_sorted["completed_at"].min()
        t_max = group_sorted["completed_at"].max()
        dur = (t_max - t_min).total_seconds() / 60.0 if t_max != t_min else 0
        sessions.append({
            "session_id": int(sid),
            "date": date,
            "body_parts": parts,
            "exercise_count": exercises,
            "total_sets": total_sets,
            "total_volume_kg": total_vol,
            "max_weight_kg": max_w,
            "duration_minutes": round(dur, 1),
        })

    return pd.DataFrame(sessions).sort_values("date", ascending=False)


def build_pr_records(dataframe: pd.DataFrame) -> pd.DataFrame:
    if dataframe.empty:
        return pd.DataFrame(columns=[
            "exercise_name", "pr_weight_kg", "pr_reps", "pr_1rm",
            "pr_date", "previous_weight_kg", "previous_date",
        ])

    sorted_df = dataframe.sort_values("completed_at")
    prs = []
    for exercise, group in sorted_df.groupby("exercise_name"):
        group_sorted = group.sort_values("completed_at")
        if (group_sorted["estimated_1rm"] > 0).any():
            best_1rm_idx = group_sorted["estimated_1rm"].idxmax()
        else:
            best_1rm_idx = group_sorted["reps"].idxmax()
        best_row = group_sorted.loc[best_1rm_idx]
        best_position = group_sorted.index.get_loc(best_1rm_idx)
        before = group_sorted.iloc[:best_position]

        previous_weight = before["weight_kg"].max() if not before.empty else None
        if previous_weight == 0:
            previous_weight = None
        previous_date = before.loc[before["weight_kg"].idxmax(), "completed_at"] if not before.empty and before["weight_kg"].max() > 0 else None

        prs.append({
            "exercise_name": exercise,
            "pr_weight_kg": best_row["weight_kg"],
            "pr_reps": int(best_row["reps"]),
            "pr_1rm": best_row["estimated_1rm"],
            "pr_date": best_row["completed_at"],
            "previous_weight_kg": previous_weight,
            "previous_date": previous_date,
        })

    return pd.DataFrame(prs).sort_values("pr_1rm", ascending=False)
