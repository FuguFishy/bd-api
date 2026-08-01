from __future__ import annotations

import csv
import hashlib
import io
import re
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db import models


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    value = value.strip().lower()
    value = re.sub(r"\s+", " ", value)
    return value


def split_name(full_name: str | None) -> tuple[str | None, str | None]:
    if not full_name:
        return None, None
    parts = full_name.strip().split()
    if not parts:
        return None, None
    if len(parts) == 1:
        return parts[0], None
    return parts[0], " ".join(parts[1:])


def build_full_name(first_name: str | None, last_name: str | None, fallback_name: str | None = None) -> str:
    full_name = " ".join(part for part in [first_name, last_name] if part and part.strip()).strip()
    return full_name or (fallback_name or "").strip() or "Unknown"


def parse_connected_on(raw_value: str | None):
    if not raw_value:
        return None
    raw_value = raw_value.strip()
    for fmt in ("%d %b %Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw_value, fmt).date()
        except ValueError:
            continue
    return None


def hash_row(full_name: str, company_name: str | None, connected_on: str | None, linkedin_profile_url: str | None) -> str:
    raw = "|".join(
        [
            normalize_text(full_name),
            normalize_text(company_name),
            normalize_text(connected_on),
            normalize_text(linkedin_profile_url),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_import_run(db: Session, filename: str, uploaded_by: str | None = None):
    run = models.LinkedInImportRun(
        filename=filename,
        uploaded_by=uploaded_by,
        status="uploaded",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def parse_connections_csv(file_bytes: bytes) -> list[dict[str, Any]]:
    text = file_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    return list(reader)


def stage_connections(db: Session, run_id: int, rows: list[dict[str, Any]]):
    staged = []

    for row in rows:
        first_name = (row.get("First Name") or "").strip() or None
        last_name = (row.get("Last Name") or "").strip() or None
        profile_url = (row.get("Profile URL") or row.get("URL") or "").strip() or None
        email = (row.get("Email Address") or "").strip() or None
        company_name = (row.get("Company") or "").strip() or None
        connected_on_raw = (row.get("Connected On") or "").strip() or None

        full_name_raw = build_full_name(first_name, last_name, row.get("Name"))
        source_row_hash = hash_row(
            full_name=full_name_raw,
            company_name=company_name,
            connected_on=connected_on_raw,
            linkedin_profile_url=profile_url,
        )

        item = models.LinkedInConnectionStaging(
            import_run_id=run_id,
            source_row_hash=source_row_hash,
            full_name_raw=full_name_raw,
            company_name_raw=company_name,
            connected_on=parse_connected_on(connected_on_raw),
            linkedin_profile_url=profile_url,
            email=email,
            first_name=first_name,
            last_name=last_name,
            full_name_normalized=normalize_text(full_name_raw),
            company_name_normalized=normalize_text(company_name),
            match_status="staged",
            review_status="not_required",
        )
        db.add(item)
        staged.append(item)

    db.flush()

    run = db.query(models.LinkedInImportRun).filter(models.LinkedInImportRun.id == run_id).first()
    if run:
        run.rows_received = len(rows)
        run.status = "staged"

    db.commit()

    for item in staged:
        db.refresh(item)

    return staged