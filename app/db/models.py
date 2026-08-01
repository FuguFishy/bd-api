from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Organisation(Base):
    __tablename__ = "organisations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(Text, nullable=False, unique=True)
    short_name = Column(Text)
    sector = Column(Text)
    tier = Column(Text)
    account_status = Column(Text)
    notes = Column(Text)
    last_contact_date = Column(Date)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    contacts = relationship("Contact", back_populates="organisation")
    projects = relationship("Project", back_populates="organisation")


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    organisation_id = Column(Integer, ForeignKey("organisations.id"))
    first_name = Column(Text)
    last_name = Column(Text)
    email = Column(Text, unique=True)
    full_name = Column(Text)
    position_title = Column(Text)
    department = Column(Text)
    relationship_type = Column(Text)
    source_type = Column(Text)
    linkedin_profile_url = Column(Text, unique=True)
    linkedin_connection_status = Column(Text)
    verification_status = Column(Text)
    notes = Column(Text)
    organisation_name = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    organisation = relationship("Organisation", back_populates="contacts")


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("organisation_id", "name", name="projects_organisation_id_name_key"),
    )

    id = Column(Integer, primary_key=True, index=True)
    organisation_id = Column(Integer, ForeignKey("organisations.id"))
    contact_id = Column(Integer, ForeignKey("contacts.id"))
    name = Column(Text, nullable=False)
    project_type = Column(Text)
    status = Column(Text)
    opportunity_signal = Column(Text)
    strategic_importance = Column(Text)
    start_date = Column(Date)
    end_date = Column(Date)
    notes = Column(Text)
    organisation_name = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    organisation = relationship("Organisation", back_populates="projects")


class Activity(Base):
    __tablename__ = "activities"

    id = Column(BigInteger, primary_key=True, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"))
    organisation_id = Column(Integer, ForeignKey("organisations.id"))
    project_id = Column(Integer, ForeignKey("projects.id"))
    activity_type = Column(Text, nullable=False)
    activity_date = Column(DateTime(timezone=True), nullable=False)
    outcome = Column(Text)
    notes = Column(Text)
    logged_by = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Task(Base):
    __tablename__ = "tasks"

    id = Column(BigInteger, primary_key=True, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"))
    organisation_id = Column(Integer, ForeignKey("organisations.id"))
    project_id = Column(Integer, ForeignKey("projects.id"))
    activity_id = Column(BigInteger, ForeignKey("activities.id"))
    task_type = Column(Text, nullable=False)
    reason = Column(Text)
    priority = Column(Text)
    status = Column(Text, nullable=False)
    due_date = Column(Date)
    owner = Column(Text)
    notes = Column(Text)
    source_type = Column(Text)
    source_key = Column(Text, unique=True)
    recommended_by_rule = Column(Text)
    supersedes_task_id = Column(BigInteger, ForeignKey("tasks.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True))


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id = Column(BigInteger, primary_key=True, index=True)
    workflow_name = Column(Text, nullable=False)
    run_type = Column(Text)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at = Column(DateTime(timezone=True))
    status = Column(Text, nullable=False)
    records_processed = Column(Integer, nullable=False)
    records_flagged = Column(Integer, nullable=False)
    error_summary = Column(Text)


class EntityMatch(Base):
    __tablename__ = "entity_matches"

    id = Column(BigInteger, primary_key=True, index=True)
    source_record_type = Column(Text, nullable=False)
    source_record_id = Column(BigInteger, nullable=False)
    candidate_entity_type = Column(Text, nullable=False)
    candidate_entity_id = Column(BigInteger)
    match_score = Column(Float)
    match_method = Column(Text)
    review_status = Column(Text, nullable=False, server_default="pending")
    review_notes = Column(Text)
    resolved_by = Column(Text)
    resolved_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LinkedInImportRun(Base):
    __tablename__ = "linkedin_import_runs"

    id = Column(BigInteger, primary_key=True, index=True)
    filename = Column(Text, nullable=False)
    uploaded_by = Column(Text)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    status = Column(Text, nullable=False, server_default="pending")
    rows_received = Column(Integer, nullable=False, server_default="0")
    rows_processed = Column(Integer, nullable=False, server_default="0")
    rows_matched = Column(Integer, nullable=False, server_default="0")
    rows_created = Column(Integer, nullable=False, server_default="0")
    rows_flagged = Column(Integer, nullable=False, server_default="0")
    rows_duplicates_prevented = Column(Integer, nullable=False, server_default="0")
    error_summary = Column(Text)

    staging_rows = relationship("LinkedInConnectionStaging", back_populates="import_run")


class LinkedInConnectionStaging(Base):
    __tablename__ = "linkedin_connection_staging"
    __table_args__ = (
        UniqueConstraint(
            "import_run_id",
            "source_row_hash",
            name="uq_linkedin_staging_run_rowhash",
        ),
    )

    id = Column(BigInteger, primary_key=True, index=True)
    import_run_id = Column(BigInteger, ForeignKey("linkedin_import_runs.id"), nullable=False)
    source_row_hash = Column(Text, nullable=False)

    full_name_raw = Column(Text)
    company_name_raw = Column(Text)
    connected_on = Column(Date)
    linkedin_profile_url = Column(Text)
    email = Column(Text)

    first_name = Column(Text)
    last_name = Column(Text)
    full_name_normalized = Column(Text)
    company_name_normalized = Column(Text)

    match_status = Column(Text, nullable=False, server_default="unprocessed")
    matched_contact_id = Column(Integer, ForeignKey("contacts.id"))
    matched_organisation_id = Column(Integer, ForeignKey("organisations.id"))
    match_confidence = Column(Float)

    review_status = Column(Text, nullable=False, server_default="pending")
    review_notes = Column(Text)
    processed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    import_run = relationship("LinkedInImportRun", back_populates="staging_rows")


class WeeklyTarget(Base):
    __tablename__ = "weekly_targets"

    id = Column(BigInteger, primary_key=True, index=True)
    week_start = Column(Date, nullable=False)
    meeting_target = Column(Integer, nullable=False)
    owner = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)