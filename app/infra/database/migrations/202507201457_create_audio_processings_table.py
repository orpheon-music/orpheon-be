"""create_audio_processings_table

Revision ID: 504599605788
Revises: 34458a8b9243
Create Date: 2025-07-20 14:57:04.675932

"""

from collections.abc import Sequence

import sqlalchemy

import alembic

# revision identifiers, used by Alembic.
revision: str = "504599605788"
down_revision: str | Sequence[str] | None = "34458a8b9243"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    alembic.op.create_table(
        "audio_processings",
        sqlalchemy.Column("id", sqlalchemy.UUID, primary_key=True, nullable=False),  # type: ignore
        sqlalchemy.Column("user_id", sqlalchemy.UUID, nullable=False),  # type: ignore
        sqlalchemy.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sqlalchemy.Column("name", sqlalchemy.VARCHAR(255), nullable=False),
        sqlalchemy.Column("size", sqlalchemy.INTEGER, nullable=False),
        sqlalchemy.Column("duration", sqlalchemy.INTEGER, nullable=False),
        sqlalchemy.Column("format", sqlalchemy.VARCHAR(50), nullable=False),
        sqlalchemy.Column("bitrate", sqlalchemy.INTEGER, nullable=False),
        sqlalchemy.Column("standard_audio_url", sqlalchemy.VARCHAR(255), nullable=True),
        sqlalchemy.Column("dynamic_audio_url", sqlalchemy.VARCHAR(255), nullable=True),
        sqlalchemy.Column("smooth_audio_url", sqlalchemy.VARCHAR(255), nullable=True),
        sqlalchemy.Column("manual_audio_url", sqlalchemy.VARCHAR(255), nullable=True),
        sqlalchemy.Column(
            "created_at",
            sqlalchemy.TIMESTAMP,
            server_default=sqlalchemy.func.now(),
            nullable=False,
        ),
        sqlalchemy.Column(
            "updated_at",
            sqlalchemy.TIMESTAMP,
            server_default=sqlalchemy.func.now(),
            onupdate=sqlalchemy.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    alembic.op.drop_table("audio_processings")
