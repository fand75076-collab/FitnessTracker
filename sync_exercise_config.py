"""Sync exercise config from JSON to Android Normalizer.java."""
from __future__ import annotations

import json
import re
from pathlib import Path

JSON_PATH = Path(__file__).resolve().parent / "fitness_tracker" / "config" / "exercises.json"
JAVA_PATH = (
    Path(__file__).resolve().parent
    / "android"
    / "FitnessTrackerAndroid"
    / "app"
    / "src"
    / "main"
    / "java"
    / "com"
    / "fitness"
    / "tracker"
    / "Normalizer.java"
)


def generate_static_block(config: dict) -> str:
    lines = ["    static {"]
    for alias, canonical in config.get("aliases", {}).items():
        lines.append(f'        ALIASES.put("{alias}", "{canonical}");')
    lines.append("")
    for exercise, part in config.get("preferred_body_parts", {}).items():
        lines.append(f'        BODY_PARTS.put("{exercise}", "{part}");')
    lines.append("    }")
    return "\n".join(lines)


def main() -> None:
    config = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    new_block = generate_static_block(config)

    java_src = JAVA_PATH.read_text(encoding="utf-8")
    pattern = r"    static \{.*?    \}"
    repl, count = re.subn(pattern, new_block, java_src, count=1, flags=re.DOTALL)
    if count == 0:
        raise RuntimeError("Could not find static block in Normalizer.java")

    JAVA_PATH.write_text(repl, encoding="utf-8")
    print("Synced exercise config to Normalizer.java")


if __name__ == "__main__":
    main()
