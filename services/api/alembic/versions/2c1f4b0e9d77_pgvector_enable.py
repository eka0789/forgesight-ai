"""enable pgvector + convert embedding column (PostgreSQL only)

Revision ID: 2c1f4b0e9d77
Revises: 62bc1bfed3eb
Create Date: 2026-11-11

On PostgreSQL this activates the pgvector extension and converts
document_chunks.embedding (JSON) to vector(384). On SQLite the migration is a
no-op (column stays JSON).
"""
from __future__ import annotations

import os

from alembic import op

revision = "2c1f4b0e9d77"
down_revision = "62bc1bfed3eb"
branch_labels = None
depends_on = None

EMBEDDING_DIM = int(os.environ.get("EMBEDDING_DIM", "384"))


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        f"ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector({EMBEDDING_DIM}) "
        "USING CASE WHEN embedding IS NULL THEN NULL ELSE embedding::text::vector END"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding "
        f"ON document_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding")
    op.execute("ALTER TABLE document_chunks ALTER COLUMN embedding TYPE json USING embedding::text::jsonb")
