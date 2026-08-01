"""linkedin_import_safe_manual

Revision ID: ef87ecc8fd2f
Revises: 101ba1882857
Create Date: 2026-08-01 18:51:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "ef87ecc8fd2f"
down_revision: Union[str, Sequence[str], None] = "101ba1882857"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _has_index(inspector, table_name: str, index_name: str) -> bool:
    return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))


def _has_unique_constraint(inspector, table_name: str, constraint_name: str) -> bool:
    return any(uc["name"] == constraint_name for uc in inspector.get_unique_constraints(table_name))


def _has_foreign_key(inspector, table_name: str, fk_name: str) -> bool:
    return any(fk.get("name") == fk_name for fk in inspector.get_foreign_keys(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # ------------------------------------------------------------------
    # contacts additions
    # ------------------------------------------------------------------
    if _has_table(inspector, "contacts"):
        if not _has_column(inspector, "contacts", "position_title"):
            op.add_column("contacts", sa.Column("position_title", sa.Text(), nullable=True))
        if not _has_column(inspector, "contacts", "department"):
            op.add_column("contacts", sa.Column("department", sa.Text(), nullable=True))
        if not _has_column(inspector, "contacts", "relationship_type"):
            op.add_column("contacts", sa.Column("relationship_type", sa.Text(), nullable=True))
        if not _has_column(inspector, "contacts", "source_type"):
            op.add_column("contacts", sa.Column("source_type", sa.Text(), nullable=True))
        if not _has_column(inspector, "contacts", "linkedin_profile_url"):
            op.add_column("contacts", sa.Column("linkedin_profile_url", sa.Text(), nullable=True))
        if not _has_column(inspector, "contacts", "linkedin_connection_status"):
            op.add_column("contacts", sa.Column("linkedin_connection_status", sa.Text(), nullable=True))
        if not _has_column(inspector, "contacts", "verification_status"):
            op.add_column("contacts", sa.Column("verification_status", sa.Text(), nullable=True))
        if not _has_column(inspector, "contacts", "notes"):
            op.add_column("contacts", sa.Column("notes", sa.Text(), nullable=True))
        if not _has_column(inspector, "contacts", "organisation_name"):
            op.add_column("contacts", sa.Column("organisation_name", sa.Text(), nullable=True))
        if not _has_column(inspector, "contacts", "created_at"):
            op.add_column(
                "contacts",
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
            )
        if not _has_column(inspector, "contacts", "updated_at"):
            op.add_column(
                "contacts",
                sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
            )

        inspector = sa.inspect(bind)
        if (
            _has_column(inspector, "contacts", "linkedin_profile_url")
            and not _has_unique_constraint(inspector, "contacts", "contacts_linkedin_profile_url_key")
        ):
            op.create_unique_constraint(
                "contacts_linkedin_profile_url_key",
                "contacts",
                ["linkedin_profile_url"],
            )

    # ------------------------------------------------------------------
    # organisations additions
    # ------------------------------------------------------------------
    if _has_table(inspector, "organisations"):
        if not _has_column(inspector, "organisations", "short_name"):
            op.add_column("organisations", sa.Column("short_name", sa.Text(), nullable=True))
        if not _has_column(inspector, "organisations", "sector"):
            op.add_column("organisations", sa.Column("sector", sa.Text(), nullable=True))
        if not _has_column(inspector, "organisations", "tier"):
            op.add_column("organisations", sa.Column("tier", sa.Text(), nullable=True))
        if not _has_column(inspector, "organisations", "account_status"):
            op.add_column("organisations", sa.Column("account_status", sa.Text(), nullable=True))
        if not _has_column(inspector, "organisations", "notes"):
            op.add_column("organisations", sa.Column("notes", sa.Text(), nullable=True))
        if not _has_column(inspector, "organisations", "last_contact_date"):
            op.add_column("organisations", sa.Column("last_contact_date", sa.Date(), nullable=True))
        if not _has_column(inspector, "organisations", "created_at"):
            op.add_column(
                "organisations",
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
            )
        if not _has_column(inspector, "organisations", "updated_at"):
            op.add_column(
                "organisations",
                sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
            )

    # ------------------------------------------------------------------
    # projects additions
    # ------------------------------------------------------------------
    if _has_table(inspector, "projects"):
        if not _has_column(inspector, "projects", "project_type"):
            op.add_column("projects", sa.Column("project_type", sa.Text(), nullable=True))
        if not _has_column(inspector, "projects", "status"):
            op.add_column("projects", sa.Column("status", sa.Text(), nullable=True))
        if not _has_column(inspector, "projects", "opportunity_signal"):
            op.add_column("projects", sa.Column("opportunity_signal", sa.Text(), nullable=True))
        if not _has_column(inspector, "projects", "strategic_importance"):
            op.add_column("projects", sa.Column("strategic_importance", sa.Text(), nullable=True))
        if not _has_column(inspector, "projects", "start_date"):
            op.add_column("projects", sa.Column("start_date", sa.Date(), nullable=True))
        if not _has_column(inspector, "projects", "end_date"):
            op.add_column("projects", sa.Column("end_date", sa.Date(), nullable=True))
        if not _has_column(inspector, "projects", "notes"):
            op.add_column("projects", sa.Column("notes", sa.Text(), nullable=True))
        if not _has_column(inspector, "projects", "organisation_name"):
            op.add_column("projects", sa.Column("organisation_name", sa.Text(), nullable=True))
        if not _has_column(inspector, "projects", "created_at"):
            op.add_column(
                "projects",
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
            )
        if not _has_column(inspector, "projects", "updated_at"):
            op.add_column(
                "projects",
                sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
            )

        inspector = sa.inspect(bind)
        if not _has_unique_constraint(inspector, "projects", "projects_organisation_id_name_key"):
            op.create_unique_constraint(
                "projects_organisation_id_name_key",
                "projects",
                ["organisation_id", "name"],
            )

    # ------------------------------------------------------------------
    # activities table
    # ------------------------------------------------------------------
    inspector = sa.inspect(bind)
    if not _has_table(inspector, "activities"):
        op.create_table(
            "activities",
            sa.Column("id", sa.BigInteger(), primary_key=True, nullable=False),
            sa.Column("contact_id", sa.Integer(), sa.ForeignKey("contacts.id"), nullable=True),
            sa.Column("organisation_id", sa.Integer(), sa.ForeignKey("organisations.id"), nullable=True),
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
            sa.Column("activity_type", sa.Text(), nullable=False),
            sa.Column("activity_date", sa.DateTime(timezone=True), nullable=False),
            sa.Column("outcome", sa.Text(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("logged_by", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    inspector = sa.inspect(bind)
    if _has_table(inspector, "activities"):
        if not _has_index(inspector, "activities", "idx_activities_contact"):
            op.create_index("idx_activities_contact", "activities", ["contact_id"])
        if not _has_index(inspector, "activities", "idx_activities_org"):
            op.create_index("idx_activities_org", "activities", ["organisation_id"])
        if not _has_index(inspector, "activities", "idx_activities_project"):
            op.create_index("idx_activities_project", "activities", ["project_id"])
        if not _has_index(inspector, "activities", "idx_activities_type"):
            op.create_index("idx_activities_type", "activities", ["activity_type"])
        if not _has_index(inspector, "activities", "idx_activities_date"):
            op.create_index("idx_activities_date", "activities", ["activity_date"])

    # ------------------------------------------------------------------
    # tasks table / additions
    # ------------------------------------------------------------------
    inspector = sa.inspect(bind)
    if not _has_table(inspector, "tasks"):
        op.create_table(
            "tasks",
            sa.Column("id", sa.BigInteger(), primary_key=True, nullable=False),
            sa.Column("contact_id", sa.Integer(), sa.ForeignKey("contacts.id"), nullable=True),
            sa.Column("organisation_id", sa.Integer(), sa.ForeignKey("organisations.id"), nullable=True),
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
            sa.Column("activity_id", sa.BigInteger(), sa.ForeignKey("activities.id"), nullable=True),
            sa.Column("task_type", sa.Text(), nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("priority", sa.Text(), nullable=True),
            sa.Column("status", sa.Text(), nullable=False),
            sa.Column("due_date", sa.Date(), nullable=True),
            sa.Column("owner", sa.Text(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("source_type", sa.Text(), nullable=True),
            sa.Column("source_key", sa.Text(), nullable=True),
            sa.Column("recommended_by_rule", sa.Text(), nullable=True),
            sa.Column("supersedes_task_id", sa.BigInteger(), sa.ForeignKey("tasks.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        )
    else:
        if not _has_column(inspector, "tasks", "source_type"):
            op.add_column("tasks", sa.Column("source_type", sa.Text(), nullable=True))
        if not _has_column(inspector, "tasks", "source_key"):
            op.add_column("tasks", sa.Column("source_key", sa.Text(), nullable=True))
        if not _has_column(inspector, "tasks", "recommended_by_rule"):
            op.add_column("tasks", sa.Column("recommended_by_rule", sa.Text(), nullable=True))
        if not _has_column(inspector, "tasks", "supersedes_task_id"):
            op.add_column("tasks", sa.Column("supersedes_task_id", sa.BigInteger(), nullable=True))
            inspector = sa.inspect(bind)
            if not _has_foreign_key(inspector, "tasks", "tasks_supersedes_task_id_fkey"):
                op.create_foreign_key(
                    "tasks_supersedes_task_id_fkey",
                    "tasks",
                    "tasks",
                    ["supersedes_task_id"],
                    ["id"],
                )
        if not _has_column(inspector, "tasks", "completed_at"):
            op.add_column("tasks", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))

    inspector = sa.inspect(bind)
    if _has_table(inspector, "tasks"):
        if not _has_index(inspector, "tasks", "idx_tasks_contact"):
            op.create_index("idx_tasks_contact", "tasks", ["contact_id"])
        if not _has_index(inspector, "tasks", "idx_tasks_org"):
            op.create_index("idx_tasks_org", "tasks", ["organisation_id"])
        if not _has_index(inspector, "tasks", "idx_tasks_project"):
            op.create_index("idx_tasks_project", "tasks", ["project_id"])
        if not _has_index(inspector, "tasks", "idx_tasks_status"):
            op.create_index("idx_tasks_status", "tasks", ["status"])
        if not _has_index(inspector, "tasks", "idx_tasks_due_date"):
            op.create_index("idx_tasks_due_date", "tasks", ["due_date"])

        if (
            _has_column(inspector, "tasks", "source_key")
            and not _has_unique_constraint(inspector, "tasks", "tasks_source_key_key")
        ):
            op.create_unique_constraint("tasks_source_key_key", "tasks", ["source_key"])

    # ------------------------------------------------------------------
    # entity_matches table / additions
    # ------------------------------------------------------------------
    inspector = sa.inspect(bind)
    if not _has_table(inspector, "entity_matches"):
        op.create_table(
            "entity_matches",
            sa.Column("id", sa.BigInteger(), primary_key=True, nullable=False),
            sa.Column("source_record_type", sa.Text(), nullable=False),
            sa.Column("source_record_id", sa.BigInteger(), nullable=False),
            sa.Column("candidate_entity_type", sa.Text(), nullable=False),
            sa.Column("candidate_entity_id", sa.BigInteger(), nullable=True),
            sa.Column("match_score", sa.Float(), nullable=True),
            sa.Column("match_method", sa.Text(), nullable=True),
            sa.Column("review_status", sa.Text(), nullable=False, server_default="pending"),
            sa.Column("review_notes", sa.Text(), nullable=True),
            sa.Column("resolved_by", sa.Text(), nullable=True),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
    else:
        if not _has_column(inspector, "entity_matches", "created_at"):
            op.add_column(
                "entity_matches",
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
            )

    # ------------------------------------------------------------------
    # linkedin_import_runs table
    # ------------------------------------------------------------------
    inspector = sa.inspect(bind)
    if not _has_table(inspector, "linkedin_import_runs"):
        op.create_table(
            "linkedin_import_runs",
            sa.Column("id", sa.BigInteger(), primary_key=True, nullable=False),
            sa.Column("filename", sa.Text(), nullable=False),
            sa.Column("uploaded_by", sa.Text(), nullable=True),
            sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
            sa.Column("rows_received", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("rows_processed", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("rows_matched", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("rows_created", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("rows_flagged", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("rows_duplicates_prevented", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_summary", sa.Text(), nullable=True),
        )

    # ------------------------------------------------------------------
    # linkedin_connection_staging table
    # ------------------------------------------------------------------
    inspector = sa.inspect(bind)
    if not _has_table(inspector, "linkedin_connection_staging"):
        op.create_table(
            "linkedin_connection_staging",
            sa.Column("id", sa.BigInteger(), primary_key=True, nullable=False),
            sa.Column("import_run_id", sa.BigInteger(), sa.ForeignKey("linkedin_import_runs.id"), nullable=False),
            sa.Column("source_row_hash", sa.Text(), nullable=False),
            sa.Column("full_name_raw", sa.Text(), nullable=True),
            sa.Column("company_name_raw", sa.Text(), nullable=True),
            sa.Column("connected_on", sa.Date(), nullable=True),
            sa.Column("linkedin_profile_url", sa.Text(), nullable=True),
            sa.Column("email", sa.Text(), nullable=True),
            sa.Column("first_name", sa.Text(), nullable=True),
            sa.Column("last_name", sa.Text(), nullable=True),
            sa.Column("full_name_normalized", sa.Text(), nullable=True),
            sa.Column("company_name_normalized", sa.Text(), nullable=True),
            sa.Column("match_status", sa.Text(), nullable=False, server_default="unprocessed"),
            sa.Column("matched_contact_id", sa.Integer(), sa.ForeignKey("contacts.id"), nullable=True),
            sa.Column("matched_organisation_id", sa.Integer(), sa.ForeignKey("organisations.id"), nullable=True),
            sa.Column("match_confidence", sa.Float(), nullable=True),
            sa.Column("review_status", sa.Text(), nullable=False, server_default="pending"),
            sa.Column("review_notes", sa.Text(), nullable=True),
            sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("import_run_id", "source_row_hash", name="uq_linkedin_staging_run_rowhash"),
        )

    # ------------------------------------------------------------------
    # weekly_targets table
    # ------------------------------------------------------------------
    inspector = sa.inspect(bind)
    if not _has_table(inspector, "weekly_targets"):
        op.create_table(
            "weekly_targets",
            sa.Column("id", sa.BigInteger(), primary_key=True, nullable=False),
            sa.Column("week_start", sa.Date(), nullable=False),
            sa.Column("meeting_target", sa.Integer(), nullable=False),
            sa.Column("owner", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )


def downgrade() -> None:
    # Intentionally conservative downgrade.
    # We avoid dropping columns from existing business tables because this migration
    # is meant to be expand-only and safe against partially pre-existing schemas.

    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "weekly_targets"):
        op.drop_table("weekly_targets")

    inspector = sa.inspect(bind)
    if _has_table(inspector, "linkedin_connection_staging"):
        op.drop_table("linkedin_connection_staging")

    inspector = sa.inspect(bind)
    if _has_table(inspector, "linkedin_import_runs"):
        op.drop_table("linkedin_import_runs")

    inspector = sa.inspect(bind)
    if _has_table(inspector, "tasks"):
        if _has_unique_constraint(inspector, "tasks", "tasks_source_key_key"):
            op.drop_constraint("tasks_source_key_key", "tasks", type_="unique")
        if _has_foreign_key(inspector, "tasks", "tasks_supersedes_task_id_fkey"):
            op.drop_constraint("tasks_supersedes_task_id_fkey", "tasks", type_="foreignkey")

    inspector = sa.inspect(bind)
    if _has_table(inspector, "projects"):
        if _has_unique_constraint(inspector, "projects", "projects_organisation_id_name_key"):
            op.drop_constraint("projects_organisation_id_name_key", "projects", type_="unique")

    inspector = sa.inspect(bind)
    if _has_table(inspector, "contacts"):
        if _has_unique_constraint(inspector, "contacts", "contacts_linkedin_profile_url_key"):
            op.drop_constraint("contacts_linkedin_profile_url_key", "contacts", type_="unique")