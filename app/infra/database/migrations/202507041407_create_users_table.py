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
    conn = alembic.op.get_bind()

    conn.execute(
        sqlalchemy.text(
            """
            CREATE TABLE IF NOT EXISTS users (
              id UUID PRIMARY KEY NOT NULL,
              name VARCHAR(255) NOT NULL,
              email VARCHAR(255) UNIQUE NOT NULL,
              password TEXT NOT NULL,
              created_at TIMESTAMP DEFAULT NOW() NOT NULL,
              updated_at TIMESTAMP DEFAULT NOW() NOT NULL
            );
          """
        )
    )


def downgrade() -> None:
    conn = alembic.op.get_bind()

    conn.execute(
        sqlalchemy.text(
            """
            DROP TABLE IF EXISTS users;
          """
        )
    )
