from datetime import datetime, UTC
import re
from typing import Optional
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.review_queue import (
    ReviewQueueCreate,
    ReviewQueueCreateResponse,
    ReviewQueueOut,
    ReviewQueueResolveRequest,
    ReviewQueueResolveResponse,
)

router = APIRouter(prefix="/review-queue", tags=["review-queue"])


def _normalise_contact_name(value: str) -> str:
    return re.sub(r"[^\w]+", "", value.casefold()).replace("_", "")


def _split_contact_name(value: str) -> tuple[str, str]:
    parts = value.split()
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


REVIEW_QUEUE_SELECT = """
select
    id,
    source_type,
    review_type,
    review_status,
    source_record_key,
    source_payload,
    scraped_organisation,
    scraped_contact_name,
    scraped_contact_email,
    scraped_contact_phone,
    job_title,
    job_url,
    case
        when best_candidate_checked is null then null
        when lower(best_candidate_checked::text) in ('true', 't', 'yes', 'y', '1') then true
        when lower(best_candidate_checked::text) in ('false', 'f', 'no', 'n', '0') then false
        else null
    end as best_candidate_checked,
    case
        when best_score is null then null
        else best_score::double precision
    end as best_score,
    linked_organisation_id,
    linked_contact_id,
    review_action,
    review_notes,
    resolved_by,
    resolved_at,
    created_at
from public.review_queue
"""


@router.get("", response_model=list[ReviewQueueOut])
def list_review_queue(
    status: Optional[str] = Query(default=None),
    source_type: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    sql = f"""
    {REVIEW_QUEUE_SELECT}
    where (:status is null or review_status = :status)
      and (:source_type is null or source_type = :source_type)
    order by created_at desc
    limit :limit
    """
    rows = db.execute(
        text(sql),
        {"status": status, "source_type": source_type, "limit": limit},
    ).mappings().all()
    return [ReviewQueueOut(**dict(row)) for row in rows]


@router.get("/{review_id}", response_model=ReviewQueueOut)
def get_review_queue_item(
    review_id: int,
    source_type: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    sql = f"""
    {REVIEW_QUEUE_SELECT}
    where id = :review_id
      and (:source_type is null or source_type = :source_type)
    """
    row = db.execute(
        text(sql),
        {"review_id": review_id, "source_type": source_type},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Review item not found")
    return ReviewQueueOut(**dict(row))


@router.post("", response_model=ReviewQueueCreateResponse)
def create_review_queue_item(
    payload: ReviewQueueCreate,
    db: Session = Depends(get_db),
):
    existing = db.execute(
        text(
            """
            select id, review_status
            from public.review_queue
            where source_type = :source_type
              and source_record_key = :source_record_key
            limit 1
            """
        ),
        {
            "source_type": payload.source_type,
            "source_record_key": payload.source_record_key,
        },
    ).mappings().first()

    if existing:
        return ReviewQueueCreateResponse(
            created_new_review_item=False,
            ok=True,
            review_queue_id=existing["id"],
            review_status=existing["review_status"],
        )

    source_payload_json = (
        payload.source_payload.model_dump_json()
        if hasattr(payload.source_payload, "model_dump_json")
        else json.dumps(payload.source_payload)
    )

    inserted = db.execute(
        text(
            """
            insert into public.review_queue (
                source_type,
                review_type,
                review_status,
                source_record_key,
                source_payload,
                scraped_organisation,
                scraped_contact_name,
                scraped_contact_email,
                scraped_contact_phone,
                job_title,
                job_url,
                best_candidate_checked,
                best_score
            )
            values (
                :source_type,
                :review_type,
                'new',
                :source_record_key,
                cast(:source_payload as jsonb),
                :scraped_organisation,
                :scraped_contact_name,
                :scraped_contact_email,
                :scraped_contact_phone,
                :job_title,
                :job_url,
                :best_candidate_checked,
                :best_score
            )
            returning id, review_status
            """
        ),
        {
            "source_type": payload.source_type,
            "review_type": payload.review_type,
            "source_record_key": payload.source_record_key,
            "source_payload": source_payload_json,
            "scraped_organisation": payload.scraped_organisation,
            "scraped_contact_name": payload.scraped_contact_name,
            "scraped_contact_email": payload.scraped_contact_email,
            "scraped_contact_phone": payload.scraped_contact_phone,
            "job_title": payload.job_title,
            "job_url": payload.job_url,
            "best_candidate_checked": payload.best_candidate_checked,
            "best_score": payload.best_score,
        },
    ).mappings().first()

    db.commit()

    return ReviewQueueCreateResponse(
        created_new_review_item=True,
        ok=True,
        review_queue_id=inserted["id"],
        review_status=inserted["review_status"],
    )


@router.post("/{review_id}/resolve", response_model=ReviewQueueResolveResponse)
def resolve_review_queue_item(
    review_id: int,
    payload: ReviewQueueResolveRequest,
    source_type: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    review = db.execute(
        text(
            """
            select
                id,
                source_type,
                scraped_contact_name,
                scraped_contact_email,
                scraped_contact_phone,
                job_title,
                linked_organisation_id,
                linked_contact_id
            from public.review_queue
            where id = :review_id
              and (:source_type is null or source_type = :source_type)
            limit 1
            """
        ),
        {"review_id": review_id, "source_type": source_type},
    ).mappings().first()

    if not review:
        raise HTTPException(status_code=404, detail="Review item not found")

    if review["source_type"] == "smartjobs" and payload.action in {
        "match_existing_organisation",
        "create_organisation",
        "create_organisation_and_contact",
    }:
        raise HTTPException(
            status_code=400,
            detail="SmartJobs can create contacts only under an existing organisation",
        )

    linked_organisation_id = review["linked_organisation_id"]
    linked_contact_id = review["linked_contact_id"]

    if payload.action == "ignore":
        db.execute(
            text(
                """
                update public.review_queue
                set
                    review_status = 'ignored',
                    review_action = :review_action,
                    review_notes = :review_notes,
                    resolved_by = :resolved_by,
                    resolved_at = :resolved_at
                where id = :review_id
                """
            ),
            {
                "review_action": payload.action,
                "review_notes": payload.review_notes,
                "resolved_by": payload.resolved_by,
                "resolved_at": datetime.now(UTC),
                "review_id": review_id,
            },
        )

    elif payload.action == "watchlist":
        db.execute(
            text(
                """
                update public.review_queue
                set
                    review_status = 'watchlist',
                    review_action = :review_action,
                    review_notes = :review_notes,
                    resolved_by = :resolved_by,
                    resolved_at = :resolved_at
                where id = :review_id
                """
            ),
            {
                "review_action": payload.action,
                "review_notes": payload.review_notes,
                "resolved_by": payload.resolved_by,
                "resolved_at": datetime.now(UTC),
                "review_id": review_id,
            },
        )

    elif payload.action == "match_existing_organisation":
        if not payload.organisation_id:
            raise HTTPException(status_code=400, detail="organisation_id is required")

        org = db.execute(
            text(
                """
                select id
                from public.organisations
                where id = :organisation_id
                limit 1
                """
            ),
            {"organisation_id": payload.organisation_id},
        ).mappings().first()

        if not org:
            raise HTTPException(status_code=404, detail="Organisation not found")

        linked_organisation_id = org["id"]

        db.execute(
            text(
                """
                update public.review_queue
                set
                    review_status = 'resolved',
                    review_action = :review_action,
                    linked_organisation_id = :linked_organisation_id,
                    review_notes = :review_notes,
                    resolved_by = :resolved_by,
                    resolved_at = :resolved_at
                where id = :review_id
                """
            ),
            {
                "review_action": payload.action,
                "linked_organisation_id": linked_organisation_id,
                "review_notes": payload.review_notes,
                "resolved_by": payload.resolved_by,
                "resolved_at": datetime.now(UTC),
                "review_id": review_id,
            },
        )

    elif payload.action == "create_contact_for_existing_organisation":
        if review["source_type"] != "smartjobs":
            raise HTTPException(status_code=400, detail="This action is restricted to SmartJobs")
        if not payload.organisation_id:
            raise HTTPException(status_code=400, detail="organisation_id is required")

        contact_name = (payload.contact_name or review["scraped_contact_name"] or "").strip()
        contact_email = (payload.contact_email or review["scraped_contact_email"] or "").strip() or None
        if not contact_name:
            raise HTTPException(status_code=400, detail="A scraped contact name is required")

        org = db.execute(
            text(
                """
                select id, name
                from public.organisations
                where id = :organisation_id
                limit 1
                """
            ),
            {"organisation_id": payload.organisation_id},
        ).mappings().first()
        if not org:
            raise HTTPException(status_code=404, detail="Organisation not found")

        linked_organisation_id = org["id"]
        normalised_name = _normalise_contact_name(contact_name)
        normalised_email = contact_email.casefold() if contact_email else None
        lock_keys = [f"smartjobs:name:{linked_organisation_id}:{normalised_name}"]
        if normalised_email:
            lock_keys.append(f"smartjobs:email:{normalised_email}")
        for lock_key in sorted(lock_keys):
            db.execute(text("select pg_advisory_xact_lock(hashtext(:lock_key))"), {"lock_key": lock_key})

        existing_by_email = None
        if normalised_email:
            existing_by_email = db.execute(
                text(
                    """
                    select id, organisation_id, email
                    from public.contacts
                    where lower(email) = :email
                    limit 1
                    """
                ),
                {"email": normalised_email},
            ).mappings().first()

        existing_by_name = db.execute(
            text(
                """
                select id, organisation_id, email
                from public.contacts
                where organisation_id = :organisation_id
                  and regexp_replace(lower(coalesce(full_name, concat_ws(' ', first_name, last_name))), '[^[:alnum:]]+', '', 'g') = :normalised_name
                limit 1
                """
            ),
            {"organisation_id": linked_organisation_id, "normalised_name": normalised_name},
        ).mappings().first()

        if existing_by_email and existing_by_email["organisation_id"] != linked_organisation_id:
            raise HTTPException(
                status_code=409,
                detail="The scraped email belongs to a contact at a different organisation",
            )
        if (
            existing_by_name
            and normalised_email
            and existing_by_name["email"]
            and existing_by_name["email"].casefold() != normalised_email
        ):
            raise HTTPException(
                status_code=409,
                detail="A contact with this name exists at the organisation but has a different email",
            )

        existing_contact = existing_by_email or existing_by_name
        if existing_contact:
            linked_contact_id = existing_contact["id"]
            review_action = "existing_contact_confirmed"
        else:
            first_name, last_name = _split_contact_name(contact_name)
            source_note_parts = [f"SmartJobs review queue item #{review_id}"]
            if review["job_title"]:
                source_note_parts.append(f"Job: {review['job_title']}")
            if review["scraped_contact_phone"]:
                source_note_parts.append(f"Scraped phone retained in review record: {review['scraped_contact_phone']}")
            contact = db.execute(
                text(
                    """
                    insert into public.contacts (
                        organisation_id,
                        organisation_name,
                        first_name,
                        last_name,
                        full_name,
                        email,
                        source_type,
                        notes
                    )
                    values (
                        :organisation_id,
                        :organisation_name,
                        :first_name,
                        :last_name,
                        :full_name,
                        :email,
                        'smartjobs',
                        :notes
                    )
                    returning id
                    """
                ),
                {
                    "organisation_id": linked_organisation_id,
                    "organisation_name": org["name"],
                    "first_name": first_name,
                    "last_name": last_name,
                    "full_name": contact_name,
                    "email": contact_email,
                    "notes": " | ".join(source_note_parts),
                },
            ).mappings().first()
            linked_contact_id = contact["id"]
            review_action = "create_contact_for_existing_organisation"

        db.execute(
            text(
                """
                update public.review_queue
                set
                    review_status = 'resolved',
                    review_action = :review_action,
                    linked_organisation_id = :linked_organisation_id,
                    linked_contact_id = :linked_contact_id,
                    review_notes = :review_notes,
                    resolved_by = :resolved_by,
                    resolved_at = :resolved_at,
                    updated_at = now()
                where id = :review_id
                """
            ),
            {
                "review_action": review_action,
                "linked_organisation_id": linked_organisation_id,
                "linked_contact_id": linked_contact_id,
                "review_notes": payload.review_notes,
                "resolved_by": payload.resolved_by,
                "resolved_at": datetime.now(UTC),
                "review_id": review_id,
            },
        )

    elif payload.action == "create_organisation":
        if not payload.organisation_name:
            raise HTTPException(status_code=400, detail="organisation_name is required")

        org = db.execute(
            text(
                """
                insert into public.organisations (
                    name,
                    short_name,
                    sector,
                    tier,
                    account_status
                )
                values (
                    :name,
                    :short_name,
                    :sector,
                    :tier,
                    :account_status
                )
                returning id
                """
            ),
            {
                "name": payload.organisation_name,
                "short_name": payload.organisation_short_name,
                "sector": payload.sector,
                "tier": payload.tier,
                "account_status": payload.account_status,
            },
        ).mappings().first()

        linked_organisation_id = org["id"]

        db.execute(
            text(
                """
                update public.review_queue
                set
                    review_status = 'resolved',
                    review_action = :review_action,
                    linked_organisation_id = :linked_organisation_id,
                    review_notes = :review_notes,
                    resolved_by = :resolved_by,
                    resolved_at = :resolved_at
                where id = :review_id
                """
            ),
            {
                "review_action": payload.action,
                "linked_organisation_id": linked_organisation_id,
                "review_notes": payload.review_notes,
                "resolved_by": payload.resolved_by,
                "resolved_at": datetime.now(UTC),
                "review_id": review_id,
            },
        )

    elif payload.action == "create_organisation_and_contact":
        if not payload.organisation_name:
            raise HTTPException(status_code=400, detail="organisation_name is required")
        if not payload.contact_name:
            raise HTTPException(status_code=400, detail="contact_name is required")

        org = db.execute(
            text(
                """
                insert into public.organisations (
                    name,
                    short_name,
                    sector,
                    tier,
                    account_status
                )
                values (
                    :name,
                    :short_name,
                    :sector,
                    :tier,
                    :account_status
                )
                returning id
                """
            ),
            {
                "name": payload.organisation_name,
                "short_name": payload.organisation_short_name,
                "sector": payload.sector,
                "tier": payload.tier,
                "account_status": payload.account_status,
            },
        ).mappings().first()

        linked_organisation_id = org["id"]

        contact = db.execute(
            text(
                """
                insert into public.contacts (
                    organisation_id,
                    full_name,
                    position_title,
                    department,
                    email,
                    phone,
                    notes
                )
                values (
                    :organisation_id,
                    :full_name,
                    :position_title,
                    :department,
                    :email,
                    :phone,
                    :notes
                )
                returning id
                """
            ),
            {
                "organisation_id": linked_organisation_id,
                "full_name": payload.contact_name,
                "position_title": payload.contact_position_title,
                "department": payload.contact_department,
                "email": payload.contact_email,
                "phone": payload.contact_phone,
                "notes": payload.review_notes,
            },
        ).mappings().first()

        linked_contact_id = contact["id"]

        db.execute(
            text(
                """
                update public.review_queue
                set
                    review_status = 'resolved',
                    review_action = :review_action,
                    linked_organisation_id = :linked_organisation_id,
                    linked_contact_id = :linked_contact_id,
                    review_notes = :review_notes,
                    resolved_by = :resolved_by,
                    resolved_at = :resolved_at
                where id = :review_id
                """
            ),
            {
                "review_action": payload.action,
                "linked_organisation_id": linked_organisation_id,
                "linked_contact_id": linked_contact_id,
                "review_notes": payload.review_notes,
                "resolved_by": payload.resolved_by,
                "resolved_at": datetime.now(UTC),
                "review_id": review_id,
            },
        )

    else:
        raise HTTPException(status_code=400, detail="Unsupported action")

    db.commit()

    final_row = db.execute(
        text(
            """
            select
                id,
                review_status,
                review_action,
                linked_organisation_id,
                linked_contact_id
            from public.review_queue
            where id = :review_id
            """
        ),
        {"review_id": review_id},
    ).mappings().first()

    return ReviewQueueResolveResponse(
        ok=True,
        review_queue_id=final_row["id"],
        review_status=final_row["review_status"],
        review_action=final_row["review_action"],
        linked_organisation_id=final_row["linked_organisation_id"],
        linked_contact_id=final_row["linked_contact_id"],
    )