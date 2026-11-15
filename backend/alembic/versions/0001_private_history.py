"""Private analyses, structured documents, jobs and matches.

Revision ID: 0001_private_history
Revises:
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_private_history"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    document = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
    op.create_table("analyses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("file_type", sa.String(8), nullable=False))
    op.create_index("ix_analyses_owner_created", "analyses", ["owner_id", "created_at"])
    op.create_index("ix_analyses_expires_at", "analyses", ["expires_at"])
    op.create_table("structured_resumes",
        sa.Column("analysis_id", sa.Uuid(), sa.ForeignKey("analyses.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("parsed", document, nullable=False), sa.Column("extraction", document, nullable=False))
    op.create_table("job_descriptions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("analysis_id", sa.Uuid(), sa.ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("text", sa.Text(), nullable=False))
    op.create_index("ix_job_descriptions_analysis_id", "job_descriptions", ["analysis_id"])
    op.create_table("match_results",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("analysis_id", sa.Uuid(), sa.ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_description_id", sa.Uuid(), sa.ForeignKey("job_descriptions.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("result", document, nullable=False))
    op.create_index("ix_match_results_analysis_id", "match_results", ["analysis_id"])


def downgrade():
    op.drop_table("match_results")
    op.drop_table("job_descriptions")
    op.drop_table("structured_resumes")
    op.drop_table("analyses")
