"""create_users_table

Revision ID: 34458a8b9243
Revises: Create Users Table
Create Date: 2025-07-04 14:07:14.001644

"""

from collections.abc import Sequence

import sqlalchemy

import alembic

# revision identifiers, used by Alembic.
revision: str = "34458a8b9243"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    alembic.op.create_table(
        "users",
        sqlalchemy.Column("id", sqlalchemy.UUID, primary_key=True, nullable=False), # type: ignore
        sqlalchemy.Column("name", sqlalchemy.VARCHAR(255), nullable=False),
        sqlalchemy.Column(
            "email", sqlalchemy.VARCHAR(255), unique=True, nullable=False
        ),
        sqlalchemy.Column("password", sqlalchemy.TEXT, nullable=False),
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
    alembic.op.drop_table("users")
