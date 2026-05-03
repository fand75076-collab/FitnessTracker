from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_SOURCE_DIR = Path(r"C:\Users\Administrator\Documents\Obsidian Vault\Imported\OPPO Notes\ai")


BODYWEIGHT_ALIASES = {
    "俯卧撑",
    "标准俯卧撑",
    "窄距俯卧撑",
    "肩胛骨俯卧撑",
    "引体向上",
    "引体",
    "奥氏引体",
    "澳氏引体",
    "宽距引体",
    "窄距引体",
    "辅助引体",
    "半程引体",
}


EXERCISE_SPECS = [
    ("上斜杠铃卧推", "胸"),
    ("上斜哑铃卧推", "胸"),
    ("上斜哑铃", "胸"),
    ("上斜卧推", "胸"),
    ("哑铃上斜卧推", "胸"),
    ("杠铃卧推", "胸"),
    ("杠精卧推", "胸"),
    ("哑铃卧推", "胸"),
    ("飞鸟夹下胸", "胸"),
    ("飞鸟夹上胸", "胸"),
    ("飞鸟夹胸下胸", "胸"),
    ("飞鸟下夹胸", "胸"),
    ("飞鸟夹胸", "胸"),
    ("平胸飞鸟", "胸"),
    ("单边绳索飞鸟", "胸"),
    ("单臂飞鸟弯举", "胸"),
    ("哑铃飞鸟", "胸"),
    ("反手高位下拉", "背"),
    ("高位下拉", "背"),
    ("坐姿划船", "背"),
    ("单臂下拉", "背"),
    ("杠铃划船", "背"),
    ("杠精划船", "背"),
    ("哑铃划船", "背"),
    ("杠铃深蹲", "腿"),
    ("高脚杯哑铃深蹲", "腿"),
    ("负重深蹲", "腿"),
    ("自重深蹲", "腿"),
    ("反向箭步蹲", "腿"),
    ("罗马尼亚硬拉", "腿"),
    ("杠铃硬拉", "腿"),
    ("实力推", "肩"),
    ("哑铃侧平举", "肩"),
    ("绳索三头下拉", "手臂"),
    ("哑铃弯举", "手臂"),
    ("杠铃弯举", "手臂"),
    ("弯举", "手臂"),
    ("龙门架卷腹", "核心"),
    ("反身龙门架卷腹", "核心"),
    ("负重卷腹", "核心"),
    ("自重卷腹", "核心"),
    ("卷腹", "核心"),
    ("俯卧撑", "胸"),
    ("标准俯卧撑", "胸"),
    ("窄距俯卧撑", "胸"),
    ("肩胛骨俯卧撑", "胸"),
    ("引体向上", "背"),
    ("引体", "背"),
    ("奥氏引体", "背"),
    ("澳氏引体", "背"),
    ("宽距引体", "背"),
    ("窄距引体", "背"),
    ("辅助引体", "背"),
    ("半程引体", "背"),
]


PATTERN_SPECS = [
    (re.compile(r"负重\s*(?P<weight>\d+(?:\.\d+)?)\s*kg\s*(?P<name>俯卧撑|卷腹|引体向上|引体|辅助引体|深蹲)"), True),
    (re.compile(r"(?P<weight>\d+(?:\.\d+)?)\s*kg\s*负重\s*(?P<name>俯卧撑|卷腹|引体向上|引体|辅助引体|深蹲)"), True),
    (re.compile(r"自重\s*(?P<name>俯卧撑|卷腹|引体向上|引体|深蹲)"), False),
]


ALIAS_SORTED = sorted(EXERCISE_SPECS, key=lambda item: len(item[0]), reverse=True)


@dataclass
class ExerciseMatch:
    canonical_name: str
    body_part: str
    start: int
    end: int
    fixed_weight: float | None


@dataclass
class WorkoutRecord:
    completed_at: str
    body_part: str
    exercise_name: str
    weight_kg: float
    reps: int
    set_number: int
    notes: str
    source_key: str
    source_path: str


def normalize_text(text: str) -> str:
    replacements = {
        "\r": "\n",
        "\u3000": " ",
        "\xa0": " ",
        "，": " ",
        "。": " ",
        "；": " ",
        "：": " ",
        "、": " ",
        "（": " ",
        "）": " ",
        "(": " ",
        ")": " ",
        "➕": " ",
        "+": " ",
        "—": "-",
        "–": "-",
        "“": " ",
        "”": " ",
        "‘": " ",
        "’": " ",
        "|": " ",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)

    text = re.sub(r"(?P<w>\d+(?:\.\d+)?)\s*kg\s*/\s*(?P<r>\d+(?:\.\d+)?)", r"\g<w>/\g<r>", text, flags=re.IGNORECASE)
    text = re.sub(r"(?P<w>\d+(?:\.\d+)?)\s*-\s*(?P<r>\d+(?:\.\d+)?)", r"\g<w>/\g<r>", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_created_at(text: str) -> str | None:
    match = re.search(r'created_at:\s*"([^"]+)"', text)
    return match.group(1) if match else None


def extract_char_count(text: str) -> int:
    match = re.search(r'char_count:\s*"([^"]+)"', text)
    if not match:
        return 0
    digits = "".join(character for character in match.group(1) if character.isdigit())
    return int(digits) if digits else 0


def extract_body(text: str) -> str:
    marker = "char_count:"
    if marker not in text:
        return text
    body = text.split(marker, 1)[1]
    if "\n\n" in body:
        body = body.split("\n\n", 1)[1]
    return normalize_text(body)


def find_exercise_matches(body: str) -> list[ExerciseMatch]:
    matches: list[ExerciseMatch] = []

    for pattern, has_weight in PATTERN_SPECS:
        for match in pattern.finditer(body):
            raw_name = match.group("name")
            name_map = {
                "引体": "引体向上",
                "卷腹": "负重卷腹" if has_weight else "自重卷腹",
                "深蹲": "负重深蹲" if has_weight else "自重深蹲",
            }
            canonical_name = name_map.get(raw_name, raw_name)
            body_part = dict(EXERCISE_SPECS).get(canonical_name, "其他")
            fixed_weight = float(match.group("weight")) if has_weight else 0.0
            matches.append(
                ExerciseMatch(
                    canonical_name=canonical_name,
                    body_part=body_part,
                    start=match.start(),
                    end=match.end(),
                    fixed_weight=fixed_weight,
                )
            )

    for alias, body_part in ALIAS_SORTED:
        for match in re.finditer(re.escape(alias), body):
            if any(existing.start <= match.start() < existing.end for existing in matches):
                continue
            matches.append(
                ExerciseMatch(
                    canonical_name=alias,
                    body_part=body_part,
                    start=match.start(),
                    end=match.end(),
                    fixed_weight=None,
                )
            )

    matches.sort(key=lambda item: item.start)
    return matches


def parse_segment_numbers(segment: str) -> list[str]:
    return re.findall(r"-?\d+(?:\.\d+)?", segment)


def build_records_for_match(
    match: ExerciseMatch,
    segment: str,
    completed_at: str,
    source_path: Path,
    local_index: int,
) -> list[WorkoutRecord]:
    records: list[WorkoutRecord] = []
    raw_segment = segment.strip()
    if not raw_segment:
        return records

    pair_matches = re.findall(r"(-?\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)", raw_segment)
    consumed = raw_segment
    for weight, reps in pair_matches:
        consumed = consumed.replace(f"{weight}/{reps}", " ", 1)

    set_number = 1
    for weight, reps in pair_matches:
        records.append(
            WorkoutRecord(
                completed_at=completed_at,
                body_part=match.body_part,
                exercise_name=match.canonical_name,
                weight_kg=float(weight),
                reps=int(float(reps)),
                set_number=set_number,
                notes=f"Imported from Obsidian: {source_path.name}",
                source_key=f"{source_path.as_posix()}#{local_index}:{set_number}",
                source_path=str(source_path),
            )
        )
        set_number += 1

    remaining_numbers = parse_segment_numbers(consumed)
    if match.fixed_weight is not None:
        for reps in remaining_numbers:
            records.append(
                WorkoutRecord(
                    completed_at=completed_at,
                    body_part=match.body_part,
                    exercise_name=match.canonical_name,
                    weight_kg=float(match.fixed_weight),
                    reps=int(float(reps)),
                    set_number=set_number,
                    notes=f"Imported from Obsidian: {source_path.name}",
                    source_key=f"{source_path.as_posix()}#{local_index}:{set_number}",
                    source_path=str(source_path),
                )
            )
            set_number += 1
        return records

    if match.canonical_name in BODYWEIGHT_ALIASES:
        for reps in remaining_numbers:
            records.append(
                WorkoutRecord(
                    completed_at=completed_at,
                    body_part=match.body_part,
                    exercise_name=match.canonical_name,
                    weight_kg=0.0,
                    reps=int(float(reps)),
                    set_number=set_number,
                    notes=f"Imported from Obsidian: {source_path.name}",
                    source_key=f"{source_path.as_posix()}#{local_index}:{set_number}",
                    source_path=str(source_path),
                )
            )
            set_number += 1
        return records

    pairwise = list(zip(remaining_numbers[0::2], remaining_numbers[1::2]))
    for weight, reps in pairwise:
        try:
            weight_value = float(weight)
            reps_value = int(float(reps))
        except ValueError:
            continue
        if reps_value <= 0 or weight_value <= 0:
            continue
        if reps_value > 200 or weight_value > 300:
            continue
        records.append(
            WorkoutRecord(
                completed_at=completed_at,
                body_part=match.body_part,
                exercise_name=match.canonical_name,
                weight_kg=weight_value,
                reps=reps_value,
                set_number=set_number,
                notes=f"Imported from Obsidian: {source_path.name}",
                source_key=f"{source_path.as_posix()}#{local_index}:{set_number}",
                source_path=str(source_path),
            )
        )
        set_number += 1

    return records


def parse_workout_note(path: Path) -> list[WorkoutRecord]:
    text = path.read_text(encoding="utf-8")
    created_at = extract_created_at(text)
    if not created_at:
        return []

    char_count = extract_char_count(text)
    if char_count > 250:
        return []

    body = extract_body(text)
    matches = find_exercise_matches(body)
    if not matches:
        return []

    records: list[WorkoutRecord] = []
    for index, match in enumerate(matches):
        next_start = matches[index + 1].start if index + 1 < len(matches) else len(body)
        segment = body[match.end:next_start]
        records.extend(build_records_for_match(match, segment, created_at, path, index))

    return [record for record in records if record.reps > 0]


def iter_markdown_files(source_dir: Path) -> Iterable[Path]:
    return sorted(source_dir.glob("*.md"))


def import_records(source_dir: Path, target_home: Path) -> tuple[int, int, int]:
    os.environ["FITNESS_TRACKER_HOME"] = str(target_home)

    from fitness_tracker.db import get_connection, initialize_db
    from fitness_tracker.normalization import canonicalize_exercise_name

    initialize_db()
    imported_notes = 0
    imported_sets = 0
    skipped_sets = 0

    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workout_import_metadata (
                source_key TEXT PRIMARY KEY,
                source_path TEXT NOT NULL,
                imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        for path in iter_markdown_files(source_dir):
            records = parse_workout_note(path)
            if not records:
                continue

            note_imported = False
            for record in records:
                exists = connection.execute(
                    "SELECT 1 FROM workout_import_metadata WHERE source_key = ?",
                    (record.source_key,),
                ).fetchone()
                if exists:
                    skipped_sets += 1
                    continue

                exercise_name = canonicalize_exercise_name(record.exercise_name)
                if record.weight_kg < 0 or record.weight_kg > 300:
                    skipped_sets += 1
                    continue
                if record.reps <= 0 or record.reps > 200:
                    skipped_sets += 1
                    continue

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
                        record.completed_at,
                        record.body_part,
                        exercise_name,
                        record.weight_kg,
                        record.reps,
                        record.set_number,
                        record.notes,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO workout_import_metadata (
                        source_key,
                        source_path
                    ) VALUES (?, ?)
                    """,
                    (record.source_key, record.source_path),
                )
                imported_sets += 1
                note_imported = True

            if note_imported:
                imported_notes += 1

    return imported_notes, imported_sets, skipped_sets


def main() -> None:
    parser = argparse.ArgumentParser(description="Import workout logs from Obsidian OPPO notes.")
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--target-home", type=Path, default=Path(r"D:\vb\dist\FitnessTracker"))
    args = parser.parse_args()

    imported_notes, imported_sets, skipped_sets = import_records(args.source_dir, args.target_home)
    print(f"source_dir={args.source_dir}")
    print(f"target_home={args.target_home}")
    print(f"imported_notes={imported_notes}")
    print(f"imported_sets={imported_sets}")
    print(f"skipped_sets={skipped_sets}")


if __name__ == "__main__":
    main()
