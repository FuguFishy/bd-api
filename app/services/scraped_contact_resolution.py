from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass
class ResolutionResult:
    outcome: str
    reason: str
    confidence: float
    organisation_id: int | None = None
    organisation_name: str | None = None
    contact_id: int | None = None
    contact_name: str | None = None
    would_create_contact: bool = False
    would_create_organisation: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalise_text(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


def normalise_contact_name(value: str | None) -> str:
    return "".join(char for char in normalise_text(value) if char.isalnum())


def split_contact_name(value: str | None) -> tuple[str | None, str | None]:
    parts = " ".join((value or "").strip().split()).split(" ")
    if not parts or not parts[0]:
        return None, None
    return parts[0], " ".join(parts[1:]) or None


def resolve_scraped_contact(
    db: Session,
    *,
    source_type: str,
    source_record_key: str | None,
    scraped_organisation: str | None,
    scraped_contact_name: str | None,
    scraped_contact_email: str | None = None,
    linkedin_profile_url: str | None = None,
) -> ResolutionResult:
    if source_type not in {"aps_jobs", "smartjobs"}:
        return ResolutionResult(
            outcome="review_required",
            reason="unsupported_source_type",
            confidence=0.0,
        )

    organisation_key = normalise_text(scraped_organisation)
    if not organisation_key:
        return ResolutionResult(
            outcome="review_required",
            reason="organisation_missing",
            confidence=0.0,
        )

    organisations = db.execute(
        text(
            """
            select id, name
            from public.organisations
            where is_archived = false
              and lower(regexp_replace(name, '\\s+', ' ', 'g')) =
                  :organisation_key
            order by id
            """
        ),
        {"organisation_key": organisation_key},
    ).mappings().all()

    if not organisations:
        return ResolutionResult(
            outcome="review_required",
            reason="organisation_not_found",
            confidence=0.0,
        )

    if len(organisations) != 1:
        return ResolutionResult(
            outcome="review_required",
            reason="organisation_ambiguous",
            confidence=0.0,
        )

    organisation = organisations[0]
    organisation_id = organisation["id"]
    organisation_name = organisation["name"]

    contact_name = " ".join((scraped_contact_name or "").strip().split())
    normalised_name = normalise_contact_name(contact_name)
    if not normalised_name:
        return ResolutionResult(
            outcome="review_required",
            reason="insufficient_contact_data",
            confidence=0.0,
            organisation_id=organisation_id,
            organisation_name=organisation_name,
        )

    contact_email = (scraped_contact_email or "").strip().casefold() or None
    profile_url = (linkedin_profile_url or "").strip().rstrip("/") or None

    if contact_email:
        email_matches = db.execute(
            text(
                """
                select id, organisation_id, full_name, email
                from public.contacts
                where lower(email) = :email
                order by id
                """
            ),
            {"email": contact_email},
        ).mappings().all()

        if len(email_matches) > 1:
            return ResolutionResult(
                outcome="review_required",
                reason="email_identity_ambiguous",
                confidence=0.0,
                organisation_id=organisation_id,
                organisation_name=organisation_name,
            )

        if email_matches:
            contact = email_matches[0]
            if contact["organisation_id"] != organisation_id:
                return ResolutionResult(
                    outcome="review_required",
                    reason="email_organisation_conflict",
                    confidence=0.0,
                    organisation_id=organisation_id,
                    organisation_name=organisation_name,
                    contact_id=contact["id"],
                    contact_name=contact["full_name"],
                )
            return ResolutionResult(
                outcome="would_auto_link",
                reason="exact_email_same_organisation",
                confidence=1.0,
                organisation_id=organisation_id,
                organisation_name=organisation_name,
                contact_id=contact["id"],
                contact_name=contact["full_name"],
            )

    if profile_url:
        url_matches = db.execute(
            text(
                """
                select id, organisation_id, full_name, linkedin_profile_url
                from public.contacts
                where lower(rtrim(linkedin_profile_url, '/')) =
                      lower(:profile_url)
                order by id
                """
            ),
            {"profile_url": profile_url},
        ).mappings().all()

        if len(url_matches) > 1:
            return ResolutionResult(
                outcome="review_required",
                reason="linkedin_url_identity_ambiguous",
                confidence=0.0,
                organisation_id=organisation_id,
                organisation_name=organisation_name,
            )

        if url_matches:
            contact = url_matches[0]
            if contact["organisation_id"] != organisation_id:
                return ResolutionResult(
                    outcome="review_required",
                    reason="linkedin_url_organisation_conflict",
                    confidence=0.0,
                    organisation_id=organisation_id,
                    organisation_name=organisation_name,
                    contact_id=contact["id"],
                    contact_name=contact["full_name"],
                )
            return ResolutionResult(
                outcome="would_auto_link",
                reason="exact_linkedin_url_same_organisation",
                confidence=1.0,
                organisation_id=organisation_id,
                organisation_name=organisation_name,
                contact_id=contact["id"],
                contact_name=contact["full_name"],
            )

    name_matches = db.execute(
        text(
            """
            select id, organisation_id, full_name, email
            from public.contacts
            where organisation_id = :organisation_id
              and regexp_replace(
                  lower(
                      coalesce(
                      nullif(trim(full_name), ''),
                      nullif(trim(concat_ws(' ', first_name, last_name)), '')
                  )
                  ),
                  '[^[:alnum:]]+',
                  '',
                  'g'
              ) = :normalised_name
            order by id
            """
        ),
        {
            "organisation_id": organisation_id,
            "normalised_name": normalised_name,
        },
    ).mappings().all()

    if len(name_matches) > 1:
        return ResolutionResult(
            outcome="review_required",
            reason="contact_name_ambiguous",
            confidence=0.0,
            organisation_id=organisation_id,
            organisation_name=organisation_name,
        )

    if name_matches:
        contact = name_matches[0]
        existing_email = (contact["email"] or "").strip().casefold() or None
        if contact_email and existing_email and existing_email != contact_email:
            return ResolutionResult(
                outcome="review_required",
                reason="name_email_conflict",
                confidence=0.0,
                organisation_id=organisation_id,
                organisation_name=organisation_name,
                contact_id=contact["id"],
                contact_name=contact["full_name"],
            )
        return ResolutionResult(
            outcome="would_auto_link",
            reason="exact_name_same_organisation",
            confidence=0.96,
            organisation_id=organisation_id,
            organisation_name=organisation_name,
            contact_id=contact["id"],
            contact_name=contact["full_name"],
        )

    return ResolutionResult(
        outcome="would_auto_create",
        reason="existing_organisation_no_contact_match",
        confidence=0.95,
        organisation_id=organisation_id,
        organisation_name=organisation_name,
        would_create_contact=True,
        would_create_organisation=False,
    )
