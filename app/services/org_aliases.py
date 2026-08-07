from __future__ import annotations

import csv
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_ALIAS_FILE = BASE_DIR / "Name_Mapping.csv"


def normalize_org_text(value: str | None) -> str:
    if not value:
        return ""
    value = value.strip().lower()
    value = re.sub(r"\s+", " ", value)
    return value


def load_org_alias_map(csv_path: Path | None = None) -> dict[str, str]:
    path = csv_path or DEFAULT_ALIAS_FILE
    alias_map: dict[str, str] = {}

    if not path.exists():
        return alias_map

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            linkedin_name = normalize_org_text(row.get("linkedin_name"))
            correct_name = (row.get("correct_name") or "").strip()

            if linkedin_name and correct_name:
                alias_map[linkedin_name] = correct_name

    return alias_map