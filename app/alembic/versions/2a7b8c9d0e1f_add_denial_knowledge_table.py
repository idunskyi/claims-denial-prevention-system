"""add_denial_knowledge_table

Revision ID: 2a7b8c9d0e1f
Revises: 1f60bbe4f690
Create Date: 2026-01-27

This migration creates the denial_knowledge table for storing
denial patterns with vector embeddings for similarity search.

The table uses pgvector for efficient similarity search on embeddings.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '2a7b8c9d0e1f'
down_revision: Union[str, None] = '1f60bbe4f690'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ensure pgvector extension is enabled (should already be from init script)
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # Create the denial_knowledge table
    op.create_table(
        'denial_knowledge',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('carc_code', sa.String(length=10), nullable=True),
        sa.Column('denial_reason', sa.Text(), nullable=False),
        sa.Column('trigger_patterns', postgresql.JSON(), nullable=True),
        sa.Column('remediation', sa.Text(), nullable=True),
        sa.Column('appeal_template', sa.Text(), nullable=True),
        sa.Column('success_rate', sa.Float(), nullable=True),
        sa.Column('typical_payers', postgresql.ARRAY(sa.String()), nullable=True),
        # Vector column for embeddings - 1536 dimensions for OpenAI text-embedding-3-small
        # Using raw SQL because SQLAlchemy doesn't natively support vector type
        sa.Column('embedding_text', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Add the vector column using raw SQL (pgvector type)
    op.execute('ALTER TABLE denial_knowledge ADD COLUMN embedding vector(1536)')

    # Create an index for faster similarity search
    # Using ivfflat index which is good for approximate nearest neighbor search
    # Lists parameter: sqrt(n) where n is expected number of rows, start with 100
    op.execute('''
        CREATE INDEX denial_knowledge_embedding_idx
        ON denial_knowledge
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    ''')

    # Create index on category for filtering
    op.create_index('ix_denial_knowledge_category', 'denial_knowledge', ['category'])

    # Create index on carc_code for filtering
    op.create_index('ix_denial_knowledge_carc_code', 'denial_knowledge', ['carc_code'])


def downgrade() -> None:
    op.drop_index('ix_denial_knowledge_carc_code', table_name='denial_knowledge')
    op.drop_index('ix_denial_knowledge_category', table_name='denial_knowledge')
    op.execute('DROP INDEX IF EXISTS denial_knowledge_embedding_idx')
    op.drop_table('denial_knowledge')
