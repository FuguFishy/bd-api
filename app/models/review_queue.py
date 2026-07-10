from sqlalchemy import Column, Integer, BigInteger, Text, DateTime, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.db.base import Base


class ReviewQueue(Base):
    __tablename__ = "review_queue"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    source_type = Column(Text, nullable=False)
    review_type = Column(Text, nullable=False)
    source_record_key = Column(Text, nullable=False)
    source_payload = Column(JSONB, nullable=False)

    scraped_organisation = Column(Text)
    scraped_contact_name = Column(Text)
    scraped_contact_email = Column(Text)
    scraped_contact_phone = Column(Text)
    job_title = Column(Text)
    job_url = Column(Text)
    best_candidate_checked = Column(Text)
    best_score = Column(Numeric(6, 3))

    review_status = Column(Text, nullable=False, default="new")
    review_action = Column(Text)
    review_notes = Column(Text)

    linked_organisation_id = Column(Integer, ForeignKey("organisations.id"))
    linked_contact_id = Column(Integer, ForeignKey("contacts.id"))

    resolved_by = Column(Text)
    resolved_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint(
            "source_type",
            "review_type",
            "source_record_key",
            name="uq_review_queue_source_key",
        ),
    )