from __future__ import annotations

import json
import sys
from collections.abc import Iterable
from pathlib import Path

import pandas as pd


def _load_config() -> dict:
    module_dir = Path(__file__).resolve().parent
    candidates = [module_dir / "config" / "exercises.json"]
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        bundle_root = Path(sys._MEIPASS)
        candidates.extend(
            [
                bundle_root / "fitness_tracker" / "config" / "exercises.json",
                bundle_root / "config" / "exercises.json",
            ]
        )

    for config_path in candidates:
        if config_path.exists():
            with config_path.open(encoding="utf-8") as fh:
                return json.load(fh)
    return {"aliases": {}, "preferred_body_parts": {}}


_CONFIG = _load_config()
EXERCISE_ALIASES: dict[str, str] = dict(_CONFIG.get("aliases", {}))
PREFERRED_BODY_PARTS: dict[str, str] = dict(_CONFIG.get("preferred_body_parts", {}))


def clean_exercise_name(name: object) -> str:
    return " ".join(str(name or "").strip().split())


def canonicalize_exercise_name(name: object) -> str:
    cleaned = clean_exercise_name(name)
    return EXERCISE_ALIASES.get(cleaned, cleaned)


def preferred_body_part(exercise_name: object, fallback: object = "其他") -> str:
    canonical = canonicalize_exercise_name(exercise_name)
    fallback_text = str(fallback or "其他").strip() or "其他"
    return PREFERRED_BODY_PARTS.get(canonical, fallback_text)


def aliases_for_exercise(exercise_name: object) -> list[str]:
    canonical = canonicalize_exercise_name(exercise_name)
    names = {canonical, clean_exercise_name(exercise_name)}
    names.update(alias for alias, target in EXERCISE_ALIASES.items() if target == canonical)
    return sorted(name for name in names if name)


def normalize_workout_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    if dataframe.empty or "exercise_name" not in dataframe.columns:
        return dataframe

    normalized = dataframe.copy()
    normalized["raw_exercise_name"] = normalized["exercise_name"].map(clean_exercise_name)
    normalized["exercise_name"] = normalized["raw_exercise_name"].map(canonicalize_exercise_name)
    normalized["exercise_name_normalized"] = (
        normalized["raw_exercise_name"] != normalized["exercise_name"]
    )

    if "body_part" in normalized.columns:
        normalized["body_part"] = normalized.apply(
            lambda row: preferred_body_part(row["exercise_name"], row["body_part"]),
            axis=1,
        )

    return normalized


def normalize_recent_exercise_rows(rows: Iterable[object], limit: int) -> list[dict[str, str]]:
    recent: list[dict[str, str]] = []
    seen: set[str] = set()

    for row in rows:
        raw_name = row["exercise_name"] if hasattr(row, "keys") else row[0]
        raw_part = row["body_part"] if hasattr(row, "keys") else row[1]
        canonical = canonicalize_exercise_name(raw_name)
        if not canonical or canonical in seen:
            continue
        seen.add(canonical)
        recent.append(
            {
                "exercise_name": canonical,
                "body_part": preferred_body_part(canonical, raw_part),
            }
        )
        if len(recent) >= limit:
            break

    return recent
