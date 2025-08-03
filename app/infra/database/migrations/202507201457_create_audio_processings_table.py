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
    conn = alembic.op.get_bind()

    conn.execute(
        sqlalchemy.text(
            """
            CREATE TABLE IF NOT EXISTS audio_processings (
              id UUID PRIMARY KEY NOT NULL,
              user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              name VARCHAR(255) NOT NULL,
              size INTEGER NOT NULL,
              duration INTEGER NOT NULL,
              format VARCHAR(50) NOT NULL,
              bitrate INTEGER NOT NULL,
              standard_audio_url VARCHAR(255),
              dynamic_audio_url VARCHAR(255),
              smooth_audio_url VARCHAR(255),
              manual_audio_url VARCHAR(255),
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
            DROP TABLE IF EXISTS audio_processings;
          """
        )
    )
