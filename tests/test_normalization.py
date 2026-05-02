from __future__ import annotations

import pandas as pd

from fitness_tracker.normalization import (
    aliases_for_exercise,
    canonicalize_exercise_name,
    clean_exercise_name,
    normalize_recent_exercise_rows,
    normalize_workout_dataframe,
    preferred_body_part,
)


class TestCleanExerciseName:
    def test_trims_and_collapses_whitespace(self):
        assert clean_exercise_name("  杠铃  卧推  ") == "杠铃 卧推"
        assert clean_exercise_name(None) == ""


class TestCanonicalizeExerciseName:
    def test_returns_alias_when_matched(self):
        assert canonicalize_exercise_name("杠精卧推") == "杠铃卧推"
        assert canonicalize_exercise_name("引体") == "引体向上"

    def test_returns_cleaned_name_when_no_alias(self):
        assert canonicalize_exercise_name("深蹲") == "深蹲"

    def test_normalizes_whitespace_first(self):
        assert canonicalize_exercise_name("  杠精卧推  ") == "杠铃卧推"


class TestPreferredBodyPart:
    def test_known_exercise_returns_preferred(self):
        assert preferred_body_part("杠铃卧推", "其他") == "胸"
        assert preferred_body_part("引体向上", "其他") == "背"

    def test_unknown_exercise_returns_fallback(self):
        assert preferred_body_part("深蹲", "腿") == "腿"
        assert preferred_body_part("未知动作", "") == "其他"

    def test_canonicalizes_before_lookup(self):
        assert preferred_body_part("杠精卧推", "其他") == "胸"


class TestAliasesForExercise:
    def test_includes_canonical_and_input(self):
        names = aliases_for_exercise("杠精卧推")
        assert "杠铃卧推" in names
        assert "杠精卧推" in names

    def test_includes_reverse_aliases(self):
        names = aliases_for_exercise("杠铃卧推")
        assert "杠铃卧推" in names
        assert "杠精卧推" in names


class TestNormalizeWorkoutDataframe:
    def test_adds_raw_and_normalized_flag(self):
        df = pd.DataFrame(
            {
                "exercise_name": ["杠精卧推", "深蹲"],
                "body_part": ["胸", "腿"],
            }
        )
        result = normalize_workout_dataframe(df)
        assert result.iloc[0]["exercise_name"] == "杠铃卧推"
        assert result.iloc[0]["raw_exercise_name"] == "杠精卧推"
        assert result.iloc[0]["exercise_name_normalized"] == True
        assert result.iloc[1]["exercise_name_normalized"] == False

    def test_updates_body_part(self):
        df = pd.DataFrame(
            {
                "exercise_name": ["杠精卧推"],
                "body_part": ["其他"],
            }
        )
        result = normalize_workout_dataframe(df)
        assert result.iloc[0]["body_part"] == "胸"

    def test_empty_dataframe_returns_unchanged(self):
        df = pd.DataFrame()
        result = normalize_workout_dataframe(df)
        assert result.empty


class TestNormalizeRecentExerciseRows:
    def test_deduplicates_and_limits(self):
        rows = [
            {"exercise_name": "杠精卧推", "body_part": "胸"},
            {"exercise_name": "杠铃卧推", "body_part": "胸"},
            {"exercise_name": "深蹲", "body_part": "腿"},
        ]
        result = normalize_recent_exercise_rows(rows, limit=2)
        assert len(result) == 2
        assert result[0]["exercise_name"] == "杠铃卧推"
        assert result[1]["exercise_name"] == "深蹲"

    def test_empty_input(self):
        assert normalize_recent_exercise_rows([], limit=10) == []
