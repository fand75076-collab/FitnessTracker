from __future__ import annotations

import pandas as pd
import pytest

from fitness_tracker import analytics


def make_df(rows: list[dict]) -> pd.DataFrame:
    """Helper to build a minimal workout DataFrame."""
    df = pd.DataFrame(rows)
    if not df.empty:
        df["completed_at"] = pd.to_datetime(df["completed_at"])
        df["day"] = df["completed_at"].dt.floor("D")
        df["week"] = df["completed_at"].dt.to_period("W-MON").dt.start_time
        df["month"] = df["completed_at"].dt.to_period("M").dt.start_time
        df["volume_kg"] = df["weight_kg"] * df["reps"]
        df["estimated_1rm"] = df.apply(
            lambda r: analytics.empty_metrics().max_estimated_1rm
            if r["reps"] <= 0 or r["weight_kg"] <= 0
            else (
                r["weight_kg"]
                if r["reps"] == 1
                else min(
                    r["weight_kg"] * (1 + r["reps"] / 30.0),
                    r["weight_kg"] * (36.0 / (37.0 - r["reps"])),
                )
            ),
            axis=1,
        ).round(1)
        df["id"] = range(1, len(df) + 1)
    return df


class TestBuildSummaryMetrics:
    def test_empty_dataframe(self):
        df = pd.DataFrame()
        m = analytics.build_summary_metrics(df)
        assert m.total_sets == 0
        assert m.total_volume == 0.0
        assert m.active_days == 0
        assert m.max_estimated_1rm == 0.0

    def test_basic_aggregation(self):
        df = make_df(
            [
                {"completed_at": "2026-04-20 18:00", "weight_kg": 100, "reps": 5},
                {"completed_at": "2026-04-21 18:00", "weight_kg": 100, "reps": 5},
            ]
        )
        m = analytics.build_summary_metrics(df)
        assert m.total_sets == 2
        assert m.total_volume == 1000.0
        assert m.active_days == 2


class TestAggregateVolume:
    def test_empty_dataframe(self):
        df = pd.DataFrame()
        result = analytics.aggregate_volume(df, "day")
        assert result.empty

    def test_daily_aggregation(self):
        df = make_df(
            [
                {"completed_at": "2026-04-20 18:00", "weight_kg": 100, "reps": 5},
                {"completed_at": "2026-04-20 19:00", "weight_kg": 100, "reps": 5},
                {"completed_at": "2026-04-21 18:00", "weight_kg": 100, "reps": 5},
            ]
        )
        result = analytics.aggregate_volume(df, "day")
        assert len(result) == 2
        assert result[result["period"] == pd.Timestamp("2026-04-20")]["volume_kg"].iloc[0] == 1000.0
        assert result[result["period"] == pd.Timestamp("2026-04-21")]["volume_kg"].iloc[0] == 500.0

    def test_monthly_aggregation(self):
        df = make_df(
            [
                {"completed_at": "2026-04-20 18:00", "weight_kg": 100, "reps": 5},
                {"completed_at": "2026-05-21 18:00", "weight_kg": 100, "reps": 5},
            ]
        )
        result = analytics.aggregate_volume(df, "month")
        assert len(result) == 2


class TestAggregateBodyPart:
    def test_empty_dataframe(self):
        df = pd.DataFrame()
        result = analytics.aggregate_body_part(df)
        assert result.empty

    def test_groups_by_body_part(self):
        df = make_df(
            [
                {"completed_at": "2026-04-20 18:00", "weight_kg": 100, "reps": 5, "body_part": "胸"},
                {"completed_at": "2026-04-20 19:00", "weight_kg": 100, "reps": 5, "body_part": "胸"},
                {"completed_at": "2026-04-21 18:00", "weight_kg": 100, "reps": 5, "body_part": "背"},
            ]
        )
        result = analytics.aggregate_body_part(df)
        assert len(result) == 2
        chest = result[result["body_part"] == "胸"].iloc[0]
        back = result[result["body_part"] == "背"].iloc[0]
        assert chest["volume_kg"] == 1000.0
        assert chest["sets"] == 2
        assert back["volume_kg"] == 500.0
        assert back["sets"] == 1


class TestBuildExerciseTrend:
    def test_empty_dataframe(self):
        df = pd.DataFrame()
        result = analytics.build_exercise_trend(df, "杠铃卧推", "day")
        assert result.empty

    def test_filters_exercise_and_aggregates(self):
        df = make_df(
            [
                {"completed_at": "2026-04-20 18:00", "weight_kg": 100, "reps": 5, "exercise_name": "杠铃卧推"},
                {"completed_at": "2026-04-20 19:00", "weight_kg": 110, "reps": 3, "exercise_name": "杠铃卧推"},
                {"completed_at": "2026-04-21 18:00", "weight_kg": 80, "reps": 8, "exercise_name": "杠铃划船"},
            ]
        )
        result = analytics.build_exercise_trend(df, "杠铃卧推", "day")
        assert len(result) == 1
        assert result.iloc[0]["best_weight_kg"] == 110.0
        assert result.iloc[0]["total_volume_kg"] == 100 * 5 + 110 * 3


class TestBuildMaxWeightProgress:
    def test_empty_dataframe(self):
        df = pd.DataFrame()
        result = analytics.build_max_weight_progress(df, "week")
        assert result.empty

    def test_calculates_weight_change_pct(self):
        df = make_df(
            [
                {"completed_at": "2026-04-14 18:00", "weight_kg": 100, "reps": 5, "exercise_name": "杠铃卧推"},
                {"completed_at": "2026-04-21 18:00", "weight_kg": 110, "reps": 3, "exercise_name": "杠铃卧推"},
            ]
        )
        result = analytics.build_max_weight_progress(df, "week")
        assert not result.empty
        latest = result.loc[result["best_weight_kg"].idxmax()]
        assert latest["best_weight_kg"] == 110.0
        assert latest["previous_best_weight_kg"] == 100.0
        assert latest["weight_change_kg"] == 10.0
        assert latest["weight_change_pct"] == 10.0

    def test_first_appearance_row_has_nan_pct(self):
        """Periods with no prior baseline must surface as NaN, not 0.0,
        so downstream `.notna()` filters exclude them from charts/tables."""
        df = make_df(
            [
                {"completed_at": "2026-04-14 18:00", "weight_kg": 100, "reps": 5, "exercise_name": "杠铃卧推"},
                {"completed_at": "2026-04-21 18:00", "weight_kg": 110, "reps": 3, "exercise_name": "杠铃卧推"},
                {"completed_at": "2026-04-21 18:00", "weight_kg": 80, "reps": 8, "exercise_name": "杠铃划船"},
            ]
        )
        result = analytics.build_max_weight_progress(df, "week")
        first_rows = result[result["previous_best_weight_kg"].isna()]
        assert not first_rows.empty
        assert first_rows["weight_change_pct"].isna().all()


class TestSummarizeLatestMaxWeightProgress:
    def test_empty_progress(self):
        df = pd.DataFrame()
        result = analytics.summarize_latest_max_weight_progress(df)
        assert result["improved_exercises"] == 0

    def test_finds_best_improvement(self):
        df = pd.DataFrame(
            {
                "period": pd.to_datetime(["2026-04-14", "2026-04-21", "2026-04-14", "2026-04-21"]),
                "exercise_name": ["杠铃卧推", "杠铃卧推", "杠铃划船", "杠铃划船"],
                "best_weight_kg": [100.0, 110.0, 80.0, 90.0],
                "previous_best_weight_kg": [pd.NA, 100.0, pd.NA, 80.0],
                "weight_change_kg": [pd.NA, 10.0, pd.NA, 10.0],
                "weight_change_pct": [pd.NA, 10.0, pd.NA, 12.5],
                "sets": [1, 1, 1, 1],
            }
        )
        result = analytics.summarize_latest_max_weight_progress(df)
        assert result["improved_exercises"] == 2
        # Best pct is 12.5 from 划船
        assert result["exercise_name"] == "杠铃划船"
        assert result["weight_change_pct"] == 12.5


class TestScienceRules:
    def test_build_science_summary_scores_recent_frequency(self):
        df = make_df(
            [
                {"completed_at": "2026-04-20 18:00", "weight_kg": 80, "reps": 10, "body_part": "胸", "exercise_name": "杠铃卧推"},
                {"completed_at": "2026-04-22 18:00", "weight_kg": 90, "reps": 8, "body_part": "背", "exercise_name": "杠铃划船"},
                {"completed_at": "2026-04-01 18:00", "weight_kg": 70, "reps": 6, "body_part": "腿", "exercise_name": "杠铃深蹲"},
            ]
        )
        summary = analytics.build_science_summary(df, reference_date="2026-04-22")
        assert summary["strength_days_7d"] == 2
        assert summary["frequency_status"] == "达标"
        assert summary["active_body_parts_28d"] == 3
        assert summary["rep_8_12_pct"] == pytest.approx(66.7)

    def test_body_part_science_table_includes_missing_major_parts(self):
        df = make_df(
            [
                {"completed_at": "2026-04-20 18:00", "weight_kg": 80, "reps": 10, "body_part": "胸", "exercise_name": "杠铃卧推"},
                {"completed_at": "2026-04-21 18:00", "weight_kg": 80, "reps": 10, "body_part": "胸", "exercise_name": "杠铃卧推"},
            ]
        )
        table = analytics.build_body_part_science_table(df, reference_date="2026-04-22")
        assert set(table["body_part"]) == set(analytics.SCIENCE_STRENGTH_BODY_PARTS)
        chest = table[table["body_part"] == "胸"].iloc[0]
        legs = table[table["body_part"] == "腿"].iloc[0]
        assert chest["sets"] == 2
        assert chest["avg_sets_per_week"] == 0.5
        assert legs["status"] == "近28天缺失"

    def test_recovery_alerts_find_same_body_part_under_48_hours(self):
        df = make_df(
            [
                {"completed_at": "2026-04-20 18:00", "weight_kg": 80, "reps": 10, "body_part": "胸", "exercise_name": "杠铃卧推"},
                {"completed_at": "2026-04-21 17:00", "weight_kg": 80, "reps": 10, "body_part": "胸", "exercise_name": "哑铃卧推"},
                {"completed_at": "2026-04-24 18:00", "weight_kg": 90, "reps": 8, "body_part": "背", "exercise_name": "杠铃划船"},
            ]
        )
        df["session_id"] = [0, 1, 2]
        alerts = analytics.build_recovery_alerts(df)
        assert len(alerts) == 1
        assert alerts.iloc[0]["body_part"] == "胸"
        assert alerts.iloc[0]["hours_between"] == 23.0

    def test_progression_candidates_require_two_high_rep_sessions(self):
        df = make_df(
            [
                {"completed_at": "2026-04-20 18:00", "weight_kg": 70, "reps": 12, "body_part": "胸", "exercise_name": "杠铃卧推"},
                {"completed_at": "2026-04-20 18:10", "weight_kg": 70, "reps": 13, "body_part": "胸", "exercise_name": "杠铃卧推"},
                {"completed_at": "2026-04-22 18:00", "weight_kg": 70, "reps": 12, "body_part": "胸", "exercise_name": "杠铃卧推"},
                {"completed_at": "2026-04-22 18:10", "weight_kg": 70, "reps": 12, "body_part": "胸", "exercise_name": "杠铃卧推"},
            ]
        )
        df["session_id"] = [0, 0, 1, 1]
        result = analytics.build_progression_candidates(df)
        assert len(result) == 1
        assert result.iloc[0]["exercise_name"] == "杠铃卧推"
        assert result.iloc[0]["suggested_low_kg"] == 71.4
        assert result.iloc[0]["suggested_high_kg"] == 77.0


class TestBuildSessionSummary:
    def test_empty_dataframe(self):
        df = pd.DataFrame()
        result = analytics.build_session_summary(df)
        assert result.empty

    def test_groups_sets_into_sessions(self):
        df = make_df(
            [
                {"completed_at": "2026-04-20 18:00", "weight_kg": 100, "reps": 5, "body_part": "胸", "exercise_name": "杠铃卧推"},
                {"completed_at": "2026-04-20 18:30", "weight_kg": 100, "reps": 5, "body_part": "胸", "exercise_name": "杠铃卧推"},
                # 91-minute gap triggers a new session (> 90)
                {"completed_at": "2026-04-20 20:01", "weight_kg": 80, "reps": 8, "body_part": "背", "exercise_name": "杠铃划船"},
            ]
        )
        import fitness_tracker.db as db
        df["session_id"] = db.compute_sessions(df)
        result = analytics.build_session_summary(df)
        assert len(result) == 2


class TestBuildPrRecords:
    def test_empty_dataframe(self):
        df = pd.DataFrame()
        result = analytics.build_pr_records(df)
        assert result.empty

    def test_finds_best_1rm_per_exercise(self):
        df = make_df(
            [
                {"completed_at": "2026-04-14 18:00", "weight_kg": 100, "reps": 5, "exercise_name": "杠铃卧推"},
                {"completed_at": "2026-04-21 18:00", "weight_kg": 110, "reps": 3, "exercise_name": "杠铃卧推"},
            ]
        )
        result = analytics.build_pr_records(df)
        assert len(result) == 1
        assert result.iloc[0]["exercise_name"] == "杠铃卧推"
        # 110kg x 3 -> Epley 121.0, Brzycki ~116.47 -> min = 116.5
        assert result.iloc[0]["pr_1rm"] == 116.5
        assert result.iloc[0]["pr_weight_kg"] == 110.0

    def test_tracks_previous_weight(self):
        df = make_df(
            [
                {"completed_at": "2026-04-14 18:00", "weight_kg": 100, "reps": 5, "exercise_name": "杠铃卧推"},
                {"completed_at": "2026-04-21 18:00", "weight_kg": 110, "reps": 3, "exercise_name": "杠铃卧推"},
            ]
        )
        result = analytics.build_pr_records(df)
        assert result.iloc[0]["previous_weight_kg"] == 100.0
