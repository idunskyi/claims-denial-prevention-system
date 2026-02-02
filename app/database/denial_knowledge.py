"""
Denial Knowledge Database Model Module

This module defines the SQLAlchemy model for storing denial patterns
with vector embeddings for similarity search.

The model stores:
1. Denial pattern metadata (category, CARC code, reason)
2. Remediation strategies and appeal templates
3. Vector embedding for similarity search

The embedding column uses pgvector for efficient similarity search.
When a new claim comes in, we convert it to an embedding and find
similar denial patterns to assess risk.
"""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, DateTime, Float, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSON, UUID

from database.session import Base


class DenialKnowledge(Base):
    """SQLAlchemy model for storing denial knowledge with embeddings.

    This model stores denial patterns that can be retrieved via semantic
    similarity search. Each entry represents a known denial scenario with:
    - The denial reason and category
    - Trigger patterns (what claims characteristics cause this denial)
    - Remediation strategies
    - Success rates for appeals

    The embedding column enables RAG (Retrieval Augmented Generation) by
    allowing us to find similar denial patterns for incoming claims.

    Example usage:
        # Query similar denials using cosine similarity
        SELECT * FROM denial_knowledge
        ORDER BY embedding <=> query_embedding  -- cosine distance
        LIMIT 5;
    """

    __tablename__ = "denial_knowledge"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Unique identifier for the denial knowledge entry",
    )

    # Denial classification
    category = Column(
        String(50),
        nullable=False,
        index=True,
        doc="Denial category (e.g., 'medical_necessity', 'prior_authorization')",
    )
    carc_code = Column(
        String(10),
        nullable=True,
        index=True,
        doc="Claim Adjustment Reason Code (standard industry code)",
    )

    # Denial details
    denial_reason = Column(
        Text,
        nullable=False,
        doc="Human-readable description of why this denial occurs",
    )
    trigger_patterns = Column(
        JSON,
        nullable=True,
        doc="JSON object describing claim characteristics that trigger this denial",
    )

    # Remediation information
    remediation = Column(
        Text,
        nullable=True,
        doc="Recommended actions to prevent or appeal this denial",
    )
    appeal_template = Column(
        Text,
        nullable=True,
        doc="Template text for appeal letters",
    )
    success_rate = Column(
        Float,
        nullable=True,
        doc="Historical success rate when remediation is applied (0.0 to 1.0)",
    )

    # Payer information
    typical_payers = Column(
        ARRAY(String),
        nullable=True,
        doc="List of payers that commonly issue this denial type",
    )

    # Embedding fields
    # Note: The actual 'embedding' column (vector type) is added via migration
    # because SQLAlchemy doesn't natively support pgvector's vector type.
    # We store the text used to generate the embedding for reference/debugging.
    embedding_text = Column(
        Text,
        nullable=True,
        doc="Text that was used to generate the embedding (for debugging)",
    )

    # Timestamps
    created_at = Column(
        DateTime,
        default=datetime.now,
        doc="Timestamp when the entry was created",
    )
    updated_at = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        doc="Timestamp when the entry was last updated",
    )

    def to_dict(self) -> dict:
        """Convert the model to a dictionary for JSON serialization."""
        return {
            "id": str(self.id),
            "category": self.category,
            "carc_code": self.carc_code,
            "denial_reason": self.denial_reason,
            "trigger_patterns": self.trigger_patterns,
            "remediation": self.remediation,
            "appeal_template": self.appeal_template,
            "success_rate": self.success_rate,
            "typical_payers": self.typical_payers,
            "embedding_text": self.embedding_text,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<DenialKnowledge(id={self.id}, category={self.category}, carc={self.carc_code})>"
