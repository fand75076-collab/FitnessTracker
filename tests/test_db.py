from __future__ import annotations

import sqlite3
from datetime import datetime

import pandas as pd
import pytest

import fitness_tracker.db as db


@pytest.fixture(autouse=True)
def reset_db(tmp_path, monkeypatch):
    """Point DB_PATH to a fresh temp directory for every test."""
    db_path = tmp_path / "data" / "workout.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)
    if db._cached_connection is not None:
        try:
            db._cached_connection.close()
        except Exception:
            pass
        db._cached_connection = None
    db.initialize_db()
    yield
    if db._cached_connection is not None:
        try:
            db._cached_connection.close()
        except Exception:
            pass
        db._cached_connection = None


class TestInitializeDb:
    def test_creates_table_and_indexes(self):
        conn = db.get_connection()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='workout_sets'"
        ).fetchall()
        assert len(tables) == 1

        indexes = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='workout_sets'"
        ).fetchall()
        index_names = {r[0] for r in indexes}
        assert "idx_workout_sets_completed_at" in index_names
        assert "idx_workout_sets_exercise_name" in index_names
        assert "idx_workout_sets_day_exercise" in index_names


class TestValidateWorkoutRecord:
    def test_valid_record_passes(self):
        db.validate_workout_record(
            {"exercise_name": "杠铃卧推", "weight_kg": 100, "reps": 5, "set_number": 1}
        )

    def test_missing_exercise_name_raises(self):
        with pytest.raises(db.ValidationError, match="动作名称不能为空"):
            db.validate_workout_record(
                {"exercise_name": "", "weight_kg": 100, "reps": 5, "set_number": 1}
            )

    def test_negative_weight_raises(self):
        with pytest.raises(db.ValidationError, match="重量不能为负数"):
            db.validate_workout_record(
                {"exercise_name": "杠铃卧推", "weight_kg": -1, "reps": 5, "set_number": 1}
            )

    def test_weight_over_500_raises(self):
        with pytest.raises(db.ValidationError, match="重量超出合理范围"):
            db.validate_workout_record(
                {"exercise_name": "杠铃卧推", "weight_kg": 501, "reps": 5, "set_number": 1}
            )

    def test_zero_reps_raises(self):
        with pytest.raises(db.ValidationError, match="次数不能小于1"):
            db.validate_workout_record(
                {"exercise_name": "杠铃卧推", "weight_kg": 100, "reps": 0, "set_number": 1}
            )

    def test_reps_over_200_raises(self):
        with pytest.raises(db.ValidationError, match="次数超出合理范围"):
            db.validate_workout_record(
                {"exercise_name": "杠铃卧推", "weight_kg": 100, "reps": 201, "set_number": 1}
            )

    def test_zero_set_number_raises(self):
        with pytest.raises(db.ValidationError, match="组序号不能小于1"):
            db.validate_workout_record(
                {"exercise_name": "杠铃卧推", "weight_kg": 100, "reps": 5, "set_number": 0}
            )

    def test_set_number_over_50_raises(self):
        with pytest.raises(db.ValidationError, match="组序号超出合理范围"):
            db.validate_workout_record(
                {"exercise_name": "杠铃卧推", "weight_kg": 100, "reps": 5, "set_number": 51}
            )


class TestAddWorkoutSet:
    def test_inserts_record(self):
        db.add_workout_set(
            {
                "completed_at": "2026-04-20 18:00",
                "body_part": "胸",
                "exercise_name": "杠铃卧推",
                "weight_kg": 80.0,
                "reps": 8,
                "set_number": 1,
                "notes": "",
            }
        )
        df = db.load_workout_sets()
        assert len(df) == 1
        assert df.iloc[0]["exercise_name"] == "杠铃卧推"
        assert df.iloc[0]["weight_kg"] == 80.0

    def test_canonicalizes_exercise_name_on_insert(self):
        db.add_workout_set(
            {
                "completed_at": "2026-04-20 18:00",
                "body_part": "胸",
                "exercise_name": "杠精卧推",
                "weight_kg": 80.0,
                "reps": 8,
                "set_number": 1,
                "notes": "",
            }
        )
        df = db.load_workout_sets()
        assert df.iloc[0]["exercise_name"] == "杠铃卧推"

    def test_invalid_record_raises(self):
        with pytest.raises(db.ValidationError):
            db.add_workout_set(
                {
                    "completed_at": "2026-04-20 18:00",
                    "body_part": "胸",
                    "exercise_name": "",
                    "weight_kg": 80.0,
                    "reps": 8,
                    "set_number": 1,
                    "notes": "",
                }
            )


class TestUpdateWorkoutSet:
    def test_updates_allowed_fields(self):
        db.add_workout_set(
            {
                "completed_at": "2026-04-20 18:00",
                "body_part": "胸",
                "exercise_name": "杠铃卧推",
                "weight_kg": 80.0,
                "reps": 8,
                "set_number": 1,
                "notes": "",
            }
        )
        df = db.load_workout_sets()
        set_id = int(df.iloc[0]["id"])
        db.update_workout_set(set_id, {"weight_kg": 85.0, "reps": 6})
        df2 = db.load_workout_sets()
        assert df2.iloc[0]["weight_kg"] == 85.0
        assert df2.iloc[0]["reps"] == 6

    def test_empty_updates_noop(self):
        db.add_workout_set(
            {
                "completed_at": "2026-04-20 18:00",
                "body_part": "胸",
                "exercise_name": "杠铃卧推",
                "weight_kg": 80.0,
                "reps": 8,
                "set_number": 1,
                "notes": "",
            }
        )
        df = db.load_workout_sets()
        set_id = int(df.iloc[0]["id"])
        db.update_workout_set(set_id, {})
        df2 = db.load_workout_sets()
        assert df2.iloc[0]["weight_kg"] == 80.0


class TestDeleteWorkoutSet:
    def test_deletes_record(self):
        db.add_workout_set(
            {
                "completed_at": "2026-04-20 18:00",
                "body_part": "胸",
                "exercise_name": "杠铃卧推",
                "weight_kg": 80.0,
                "reps": 8,
                "set_number": 1,
                "notes": "",
            }
        )
        df = db.load_workout_sets()
        set_id = int(df.iloc[0]["id"])
        db.delete_workout_set(set_id)
        df2 = db.load_workout_sets()
        assert len(df2) == 0


class TestEstimate1rm:
    def test_zero_reps_returns_zero(self):
        assert db.estimate_1rm(100, 0) == 0.0

    def test_zero_weight_returns_zero(self):
        assert db.estimate_1rm(0, 5) == 0.0

    def test_single_rep_returns_weight(self):
        assert db.estimate_1rm(100, 1) == 100.0

    def test_low_reps_uses_min_of_two_formulas(self):
        # Epley: 100 * (1 + 5/30) = 116.7
        # Brzycki: 100 * (36 / (37 - 5)) = 112.5
        assert db.estimate_1rm(100, 5) == 112.5

    def test_high_reps_uses_epley_only(self):
        # Epley: 100 * (1 + 12/30) = 140.0
        # Brzycki would be invalid or very high for reps=12
        assert db.estimate_1rm(100, 12) == 140.0


class TestComputeSessions:
    def test_empty_dataframe(self):
        df = pd.DataFrame(columns=["completed_at"])
        result = db.compute_sessions(df)
        assert len(result) == 0

    def test_single_record_session_zero(self):
        df = pd.DataFrame(
            {"completed_at": pd.to_datetime(["2026-04-20 18:00"])}
        )
        result = db.compute_sessions(df)
        assert result.iloc[0] == 0

    def test_same_session_when_gap_small(self):
        df = pd.DataFrame(
            {
                "completed_at": pd.to_datetime(
                    ["2026-04-20 18:00", "2026-04-20 18:30", "2026-04-20 19:00"]
                )
            }
        )
        result = db.compute_sessions(df)
        assert set(result.unique()) == {0}

    def test_new_session_when_gap_exceeds_threshold(self):
        df = pd.DataFrame(
            {
                "completed_at": pd.to_datetime(
                    ["2026-04-20 18:00", "2026-04-20 19:40", "2026-04-20 20:00"]
                )
            }
        )
        result = db.compute_sessions(df)
        # Sorted: 18:00, 19:40(>90min gap -> session 1), 20:00(same session)
        assert result.tolist() == [0, 1, 1]


class TestGetExerciseLastValues:
    def test_returns_none_for_unknown_exercise(self):
        assert db.get_exercise_last_values("不存在的动作") is None

    def test_returns_last_values(self):
        db.add_workout_set(
            {
                "completed_at": "2026-04-20 18:00",
                "body_part": "胸",
                "exercise_name": "杠铃卧推",
                "weight_kg": 80.0,
                "reps": 8,
                "set_number": 2,
                "notes": "",
            }
        )
        vals = db.get_exercise_last_values("杠铃卧推")
        assert vals is not None
        assert vals["weight_kg"] == 80.0
        assert vals["reps"] == 8
        assert vals["set_number"] == 2
        # Without completed_at, next_set_number defaults to 1
        assert vals["next_set_number"] == 1

    def test_next_set_number_resets_for_different_session(self):
        db.add_workout_set(
            {
                "completed_at": "2026-04-20 18:00",
                "body_part": "胸",
                "exercise_name": "杠铃卧推",
                "weight_kg": 80.0,
                "reps": 8,
                "set_number": 3,
                "notes": "",
            }
        )
        # Query a time well after the 90-minute gap -> should reset to 1
        vals = db.get_exercise_last_values("杠铃卧推", "2026-04-20 22:00")
        assert vals is not None
        assert vals["next_set_number"] == 1


class TestLoadWorkoutSets:
    def test_computed_columns_present(self):
        db.add_workout_set(
            {
                "completed_at": "2026-04-20 18:00",
                "body_part": "胸",
                "exercise_name": "杠铃卧推",
                "weight_kg": 80.0,
                "reps": 8,
                "set_number": 1,
                "notes": "",
            }
        )
        df = db.load_workout_sets()
        assert "volume_kg" in df.columns
        assert "estimated_1rm" in df.columns
        assert "day" in df.columns
        assert "week" in df.columns
        assert "month" in df.columns
        assert "session_id" in df.columns
        assert df.iloc[0]["volume_kg"] == 80.0 * 8

    def test_empty_database_returns_empty_frame(self):
        df = db.load_workout_sets()
        assert df.empty


class TestExportToCsv:
    def test_includes_expected_columns(self):
        db.add_workout_set(
            {
                "completed_at": "2026-04-20 18:00",
                "body_part": "胸",
                "exercise_name": "杠铃卧推",
                "weight_kg": 80.0,
                "reps": 8,
                "set_number": 1,
                "notes": "",
            }
        )
        df = db.load_workout_sets()
        csv = db.export_to_csv(df)
        assert "completed_at" in csv
        assert "exercise_name" in csv
        assert "volume_kg" in csv
