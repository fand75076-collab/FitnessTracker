from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from fitness_tracker.normalization import (
    aliases_for_exercise,
    canonicalize_exercise_name,
    normalize_recent_exercise_rows,
    normalize_workout_dataframe,
    preferred_body_part,
)


def get_app_root() -> Path:
    override = os.environ.get("FITNESS_TRACKER_HOME")
    if override:
        return Path(override).expanduser().resolve()

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        for candidate in [exe_dir, exe_dir.parent, exe_dir.parent.parent]:
            if (candidate / "data" / "workout.db").exists():
                return candidate
        return exe_dir

    return Path(__file__).resolve().parents[1]


DB_PATH = get_app_root() / "data" / "workout.db"

SESSION_GAP_MINUTES = 90


_cached_connection: sqlite3.Connection | None = None


def get_connection() -> sqlite3.Connection:
    global _cached_connection
    if _cached_connection is not None:
        try:
            _cached_connection.execute("SELECT 1")
            return _cached_connection
        except sqlite3.ProgrammingError:
            try:
                _cached_connection.close()
            except Exception:
                pass
            _cached_connection = None

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    _cached_connection = conn
    return conn


def initialize_db() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workout_sets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                completed_at TEXT NOT NULL,
                body_part TEXT NOT NULL,
                exercise_name TEXT NOT NULL,
                weight_kg REAL NOT NULL,
                reps INTEGER NOT NULL,
                set_number INTEGER NOT NULL,
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_workout_sets_completed_at
            ON workout_sets(completed_at)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_workout_sets_exercise_name
            ON workout_sets(exercise_name)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_workout_sets_day_exercise
            ON workout_sets(completed_at, exercise_name, weight_kg, reps)
            """
        )


class ValidationError(Exception):
    pass


def validate_workout_record(record: dict[str, Any]) -> None:
    if not record.get("exercise_name", "").strip():
        raise ValidationError("动作名称不能为空")
    if record.get("weight_kg", 0) < 0:
        raise ValidationError("重量不能为负数")
    if record.get("weight_kg", 0) > 500:
        raise ValidationError("重量超出合理范围（>500kg），请检查输入")
    if record.get("reps", 0) < 1:
        raise ValidationError("次数不能小于1")
    if record.get("reps", 0) > 200:
        raise ValidationError("次数超出合理范围（>200），请检查输入")
    if record.get("set_number", 0) < 1:
        raise ValidationError("组序号不能小于1")
    if record.get("set_number", 0) > 50:
        raise ValidationError("组序号超出合理范围（>50），请检查输入")


def add_workout_set(record: dict[str, Any]) -> None:
    record = dict(record)
    record["exercise_name"] = canonicalize_exercise_name(record.get("exercise_name", ""))
    record["body_part"] = preferred_body_part(record["exercise_name"], record.get("body_part", "其他"))
    validate_workout_record(record)
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO workout_sets (
                completed_at,
                body_part,
                exercise_name,
                weight_kg,
                reps,
                set_number,
                notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["completed_at"],
                record["body_part"],
                record["exercise_name"],
                record["weight_kg"],
                record["reps"],
                record["set_number"],
                record.get("notes", ""),
            ),
        )


def update_workout_set(set_id: int, updates: dict[str, Any]) -> None:
    allowed = {"weight_kg", "reps", "set_number", "body_part", "exercise_name", "notes", "completed_at"}
    fields = {k: v for k, v in updates.items() if k in allowed and v is not None}
    if not fields:
        return
    if "exercise_name" in fields:
        fields["exercise_name"] = canonicalize_exercise_name(fields["exercise_name"])
        fallback_body_part = fields.get("body_part")
        if fallback_body_part is None:
            with get_connection() as connection:
                row = connection.execute(
                    "SELECT body_part FROM workout_sets WHERE id = ?",
                    (set_id,),
                ).fetchone()
            fallback_body_part = row["body_part"] if row else "其他"
        fields["body_part"] = preferred_body_part(fields["exercise_name"], fallback_body_part)
    elif "body_part" in fields:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT exercise_name FROM workout_sets WHERE id = ?",
                (set_id,),
            ).fetchone()
        if row:
            fields["body_part"] = preferred_body_part(row["exercise_name"], fields["body_part"])
    if "exercise_name" in fields and not str(fields["exercise_name"]).strip():
        raise ValidationError("动作名称不能为空")
    if "weight_kg" in fields and (fields["weight_kg"] < 0 or fields["weight_kg"] > 500):
        raise ValidationError("重量不合理")
    if "reps" in fields and (fields["reps"] < 1 or fields["reps"] > 200):
        raise ValidationError("次数不合理")
    if "set_number" in fields and (fields["set_number"] < 1 or fields["set_number"] > 50):
        raise ValidationError("组序号不合理")
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [set_id]
    with get_connection() as connection:
        connection.execute(
            f"UPDATE workout_sets SET {set_clause} WHERE id = ?",
            values,
        )


def delete_workout_set(set_id: int) -> None:
    with get_connection() as connection:
        connection.execute("DELETE FROM workout_sets WHERE id = ?", (set_id,))


def load_workout_sets() -> pd.DataFrame:
    with get_connection() as connection:
        dataframe = pd.read_sql_query(
            """
            SELECT
                id,
                completed_at,
                body_part,
                exercise_name,
                weight_kg,
                reps,
                set_number,
                notes,
                created_at
            FROM workout_sets
            ORDER BY datetime(completed_at) DESC, id DESC
            """,
            connection,
        )

    if dataframe.empty:
        return dataframe

    dataframe = normalize_workout_dataframe(dataframe)
    dataframe["completed_at"] = pd.to_datetime(dataframe["completed_at"])
    dataframe["created_at"] = pd.to_datetime(dataframe["created_at"])
    dataframe["volume_kg"] = dataframe["weight_kg"] * dataframe["reps"]

    dataframe["estimated_1rm"] = dataframe.apply(
        lambda r: estimate_1rm(r["weight_kg"], r["reps"]),
        axis=1,
    )

    dataframe["day"] = dataframe["completed_at"].dt.floor("D")
    dataframe["week"] = dataframe["completed_at"].dt.to_period("W-MON").dt.start_time
    dataframe["month"] = dataframe["completed_at"].dt.to_period("M").dt.start_time
    dataframe["session_id"] = compute_sessions(dataframe)
    return dataframe


def estimate_1rm(weight_kg: float, reps: int) -> float:
    if reps <= 0 or weight_kg <= 0:
        return 0.0
    if reps == 1:
        return weight_kg
    epley = weight_kg * (1 + reps / 30.0)
    brzycki = weight_kg * (36.0 / (37.0 - reps))
    if reps <= 10:
        return round(min(epley, brzycki), 1)
    return round(epley, 1)


def compute_sessions(dataframe: pd.DataFrame) -> pd.Series:
    if dataframe.empty:
        return pd.Series(dtype=int)

    sorted_df = dataframe.sort_values("completed_at")
    gaps = sorted_df["completed_at"].diff().dt.total_seconds().div(60).fillna(0)
    session_ids = (gaps > SESSION_GAP_MINUTES).cumsum()
    return pd.Series(session_ids.to_numpy(), index=sorted_df.index, dtype=int)


def get_recent_exercises(limit: int = 50) -> list[dict[str, str]]:
    fetch_limit = max(limit * 4, 200)
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT exercise_name, body_part
            FROM (
                SELECT
                    exercise_name,
                    body_part,
                    completed_at,
                    id,
                    ROW_NUMBER() OVER (
                        PARTITION BY exercise_name
                        ORDER BY datetime(completed_at) DESC, id DESC
                    ) AS rn
                FROM workout_sets
            )
            WHERE rn = 1
            ORDER BY datetime(completed_at) DESC
            LIMIT ?
            """,
            (fetch_limit,),
        ).fetchall()
    return normalize_recent_exercise_rows(rows, limit)


def get_exercise_last_values(exercise_name: str, completed_at: str | None = None) -> dict[str, Any] | None:
    names = aliases_for_exercise(exercise_name)
    if not names:
        return None

    placeholders = ", ".join("?" for _ in names)
    with get_connection() as connection:
        row = connection.execute(
            f"""
            SELECT weight_kg, reps, set_number, body_part
            FROM workout_sets
            WHERE exercise_name IN ({placeholders})
            ORDER BY datetime(completed_at) DESC, id DESC
            LIMIT 1
            """,
            names,
        ).fetchone()

        same_session_max_set = None
        if completed_at:
            try:
                anchor = datetime.fromisoformat(completed_at)
                start = anchor - timedelta(minutes=SESSION_GAP_MINUTES)
                same_session_max_set = connection.execute(
                    f"""
                    SELECT MAX(set_number)
                    FROM workout_sets
                    WHERE exercise_name IN ({placeholders})
                      AND datetime(completed_at) >= datetime(?)
                      AND datetime(completed_at) <= datetime(?)
                    """,
                    [
                        *names,
                        start.isoformat(timespec="minutes"),
                        anchor.isoformat(timespec="minutes"),
                    ],
                ).fetchone()[0]
            except ValueError:
                same_session_max_set = None

    if row is None:
        return None

    canonical = canonicalize_exercise_name(exercise_name)
    return {
        "exercise_name": canonical,
        "weight_kg": row[0],
        "reps": row[1],
        "set_number": row[2],
        "next_set_number": int(same_session_max_set) + 1 if same_session_max_set else 1,
        "body_part": preferred_body_part(canonical, row[3]),
    }


def load_import_summary() -> pd.DataFrame:
    with get_connection() as connection:
        exists = connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = 'workout_import_metadata'
            """
        ).fetchone()
        if not exists:
            return pd.DataFrame(columns=["source_path", "sets", "first_imported_at", "last_imported_at"])

        return pd.read_sql_query(
            """
            SELECT
                source_path,
                COUNT(*) AS sets,
                MIN(imported_at) AS first_imported_at,
                MAX(imported_at) AS last_imported_at
            FROM workout_import_metadata
            GROUP BY source_path
            ORDER BY source_path DESC
            """,
            connection,
        )


def load_imported_sets() -> pd.DataFrame:
    with get_connection() as connection:
        exists = connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = 'workout_import_metadata'
            """
        ).fetchone()
        if not exists:
            return pd.DataFrame(
                columns=[
                    "id",
                    "completed_at",
                    "body_part",
                    "exercise_name",
                    "weight_kg",
                    "reps",
                    "set_number",
                    "notes",
                ]
            )

        dataframe = pd.read_sql_query(
            """
            SELECT
                id,
                completed_at,
                body_part,
                exercise_name,
                weight_kg,
                reps,
                set_number,
                notes
            FROM workout_sets
            WHERE notes LIKE 'Imported from %'
            ORDER BY datetime(completed_at) DESC, id DESC
            """,
            connection,
        )

    if dataframe.empty:
        return dataframe

    dataframe = normalize_workout_dataframe(dataframe)
    dataframe["completed_at"] = pd.to_datetime(dataframe["completed_at"])
    dataframe["volume_kg"] = dataframe["weight_kg"] * dataframe["reps"]
    return dataframe


def export_to_csv(dataframe: pd.DataFrame) -> str:
    export_cols = [
        "id", "completed_at", "body_part", "exercise_name",
        "weight_kg", "reps", "set_number", "volume_kg",
        "estimated_1rm", "raw_exercise_name", "notes",
    ]
    available = [c for c in export_cols if c in dataframe.columns]
    return dataframe[available].to_csv(index=False)
