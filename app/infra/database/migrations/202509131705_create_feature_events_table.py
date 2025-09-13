"""create_feature_events_table

Revision ID: 10944306e03c
Revises: 504599605788
Create Date: 2025-09-13 17:05:49.387686

"""
from collections.abc import Sequence

import sqlalchemy

import alembic

# revision identifiers, used by Alembic.
revision: str = '10944306e03c'
down_revision: str | Sequence[str] | None = '504599605788'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = alembic.op.get_bind()

    conn.execute(
        sqlalchemy.text(
            """
            CREATE TABLE IF NOT EXISTS feature_events (
              id SERIAL PRIMARY KEY NOT NULL,
              feature_name VARCHAR(255) NOT NULL,
              event_type VARCHAR(50) NOT NULL,
              event_data JSONB,
              created_at TIMESTAMP DEFAULT NOW() NOT NULL
            );
          """
        )
    )


def downgrade() -> None:
    conn = alembic.op.get_bind()

    conn.execute(
        sqlalchemy.text(
            """
            DROP TABLE IF EXISTS feature_events;
          """
        )
    )
