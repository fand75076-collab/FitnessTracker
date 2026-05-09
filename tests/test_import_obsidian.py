from __future__ import annotations

from pathlib import Path

import pytest

import import_obsidian_workouts as imp


class TestNormalizeText:
    def test_kg_slash_reps_collapses_units(self):
        # "80kg / 10" should become "80/10" so downstream pair regex can parse it
        result = imp.normalize_text("杠铃卧推 80kg / 10")
        assert "80/10" in result

    def test_weight_dash_reps_becomes_slash(self):
        # "80 - 10" should collapse to "80/10" (training notation)
        result = imp.normalize_text("卧推 80-10")
        assert "80/10" in result

    def test_iso_date_in_body_does_not_synthesize_fake_sets(self):
        # Bug-surface check: the <digits>-<digits> → <digits>/<digits> rewrite
        # partially mangles ISO dates (2026-04-20 → 2026/04-20). The important
        # invariant is that this does NOT produce spurious weight/rep pairs
        # that downstream treats as real training sets.
        note_body = "2026-04-20 杠铃卧推 80/10"
        normalized = imp.normalize_text(note_body)
        # Core training pair survives
        assert "80/10" in normalized
        # Date region does not produce a <num>/<num> pair that looks like weight/reps
        # (2026/04-20 is not a valid weight/reps pair because of the trailing dash)
        matches = imp.find_exercise_matches(normalized)
        assert len(matches) == 1
        assert matches[0].canonical_name == "杠铃卧推"

        # End-to-end: only one real set is extracted (weight=80, reps=10),
        # the date fragment doesn't create an extra spurious set.
        records = imp.build_records_for_match(
            matches[0],
            normalized[matches[0].end:],
            completed_at="2026-04-20 18:00:00",
            source_path=Path("note.md"),
            local_index=0,
        )
        assert len(records) == 1
        assert records[0].weight_kg == 80.0
        assert records[0].reps == 10

    def test_fullwidth_punctuation_becomes_whitespace(self):
        result = imp.normalize_text("卧推，80kg，10次")
        assert "，" not in result
        assert "80" in result and "10" in result


class TestExtractCreatedAt:
    def test_reads_frontmatter_timestamp(self):
        text = 'created_at: "2026-04-20 18:00:00"\nchar_count: "42"'
        assert imp.extract_created_at(text) == "2026-04-20 18:00:00"

    def test_returns_none_when_missing(self):
        assert imp.extract_created_at("no frontmatter here") is None


class TestExtractCharCount:
    def test_reads_digits(self):
        assert imp.extract_char_count('char_count: "120"') == 120

    def test_handles_non_digit_suffix(self):
        # char_count may carry a unit label in some notes
        assert imp.extract_char_count('char_count: "120 字"') == 120

    def test_returns_zero_when_missing(self):
        assert imp.extract_char_count("nothing") == 0


class TestExtractBody:
    def test_strips_frontmatter_up_to_blank_line(self):
        text = (
            'created_at: "2026-04-20 18:00:00"\n'
            'char_count: "42"\n'
            '\n'
            '杠铃卧推 80/10'
        )
        body = imp.extract_body(text)
        assert "杠铃卧推" in body
        assert "created_at" not in body
        assert "char_count" not in body

    def test_returns_raw_text_when_no_marker(self):
        assert imp.extract_body("just a plain body") == "just a plain body"


class TestFindExerciseMatches:
    def test_matches_known_alias(self):
        matches = imp.find_exercise_matches("杠铃卧推 80/10")
        assert len(matches) == 1
        assert matches[0].canonical_name == "杠铃卧推"
        assert matches[0].body_part == "胸"

    def test_bodyweight_pushup_gets_fixed_weight_none(self):
        # Standalone "俯卧撑" should register as bodyweight (no fixed_weight injection)
        matches = imp.find_exercise_matches("俯卧撑 20/15/10")
        assert matches
        pushup = next(m for m in matches if m.canonical_name == "俯卧撑")
        assert pushup.fixed_weight is None

    def test_weighted_pattern_sets_fixed_weight(self):
        # "负重 5kg 引体向上" → 引体向上 with fixed_weight=5
        matches = imp.find_exercise_matches("负重5kg 引体 8/7")
        assert matches
        assert any(m.canonical_name == "引体向上" and m.fixed_weight == 5.0 for m in matches)

    def test_non_overlapping_matches_preserve_order(self):
        body = "杠铃卧推 80/10 然后 杠铃划船 70/10"
        matches = imp.find_exercise_matches(body)
        names = [m.canonical_name for m in matches]
        # Both exercises matched, ordered by start position
        assert "杠铃卧推" in names
        assert "杠铃划船" in names
        assert matches == sorted(matches, key=lambda m: m.start)


class TestBuildRecordsForMatch:
    def _match(self, name="杠铃卧推", part="胸", fixed_weight=None):
        return imp.ExerciseMatch(
            canonical_name=name, body_part=part,
            start=0, end=len(name), fixed_weight=fixed_weight,
        )

    def test_parses_pair_notation(self):
        match = self._match()
        records = imp.build_records_for_match(
            match, " 80/10 82.5/8 ",
            completed_at="2026-04-20 18:00:00",
            source_path=Path("note.md"),
            local_index=0,
        )
        assert len(records) == 2
        assert records[0].weight_kg == 80.0 and records[0].reps == 10
        assert records[1].weight_kg == 82.5 and records[1].reps == 8
        # Set numbering starts at 1 and increments
        assert [r.set_number for r in records] == [1, 2]

    def test_bodyweight_segment_without_pairs(self):
        # "俯卧撑 20 15 10" → three bodyweight sets (weight=0)
        match = self._match(name="俯卧撑", part="胸")
        records = imp.build_records_for_match(
            match, " 20 15 10 ",
            completed_at="2026-04-20 18:00:00",
            source_path=Path("note.md"),
            local_index=0,
        )
        assert len(records) == 3
        assert all(r.weight_kg == 0.0 for r in records)
        assert [r.reps for r in records] == [20, 15, 10]

    def test_fixed_weight_applies_to_loose_reps(self):
        match = self._match(name="引体向上", part="背", fixed_weight=5.0)
        records = imp.build_records_for_match(
            match, " 8 7 6 ",
            completed_at="2026-04-20 18:00:00",
            source_path=Path("note.md"),
            local_index=0,
        )
        assert len(records) == 3
        assert all(r.weight_kg == 5.0 for r in records)
        assert [r.reps for r in records] == [8, 7, 6]

    def test_out_of_range_pairs_filtered(self):
        # 400kg / 2 reps → rejected by the 300kg cap
        match = self._match()
        records = imp.build_records_for_match(
            match, " 400 2 80 10 ",
            completed_at="2026-04-20 18:00:00",
            source_path=Path("note.md"),
            local_index=0,
        )
        # Only the 80/10 pair should make it through
        assert len(records) == 1
        assert records[0].weight_kg == 80.0


class TestParseWorkoutNote:
    def test_integration_on_tmp_file(self, tmp_path):
        note = tmp_path / "2026-04-20.md"
        note.write_text(
            'created_at: "2026-04-20 18:00:00"\n'
            'char_count: "60"\n'
            '\n'
            '杠铃卧推 80/10 82.5/8 85/6\n',
            encoding="utf-8",
        )
        records = imp.parse_workout_note(note)
        assert len(records) == 3
        assert all(r.exercise_name == "杠铃卧推" for r in records)
        assert all(r.body_part == "胸" for r in records)
        assert all(r.completed_at == "2026-04-20 18:00:00" for r in records)
        assert records[0].notes.startswith("Imported from Obsidian:")

    def test_skips_long_notes(self, tmp_path):
        # char_count > 250 → workout importer skips (likely prose, not log)
        note = tmp_path / "long.md"
        note.write_text(
            'created_at: "2026-04-20 18:00:00"\n'
            'char_count: "500"\n'
            '\n'
            '杠铃卧推 80/10\n',
            encoding="utf-8",
        )
        assert imp.parse_workout_note(note) == []

    def test_missing_created_at_skips(self, tmp_path):
        note = tmp_path / "no_date.md"
        note.write_text('char_count: "50"\n\n杠铃卧推 80/10', encoding="utf-8")
        assert imp.parse_workout_note(note) == []
