"""
Denial Knowledge Repository Module

This module provides database operations for the denial_knowledge table,
including vector similarity search for RAG (Retrieval Augmented Generation).

Key concepts:
1. Vector similarity search: Find denial patterns similar to a claim
2. Cosine distance: Measures angle between vectors (smaller = more similar)
3. Top-K retrieval: Return the K most similar results

The repository uses raw SQL for vector operations because SQLAlchemy
doesn't natively support pgvector's operators.
"""

import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from database.denial_knowledge import DenialKnowledge

logger = logging.getLogger(__name__)


class DenialKnowledgeRepository:
    """Repository for denial knowledge database operations.

    This repository handles CRUD operations and vector similarity search
    for the denial_knowledge table.

    The vector search uses pgvector's cosine distance operator (<=>)
    to find semantically similar denial patterns.

    Attributes:
        session: The SQLAlchemy session for database operations
    """

    def __init__(self, session: Session):
        """Initialize the repository with a database session.

        Args:
            session: SQLAlchemy session for database operations
        """
        self.session = session

    def create(self, knowledge: DenialKnowledge, embedding: List[float]) -> DenialKnowledge:
        """Create a new denial knowledge entry with embedding.

        Args:
            knowledge: The DenialKnowledge model instance
            embedding: The vector embedding (list of floats)

        Returns:
            The created DenialKnowledge instance
        """
        # First, add the model instance
        self.session.add(knowledge)
        self.session.flush()  # Get the ID without committing

        # Then update the embedding using raw SQL (pgvector type)
        # Note: Use CAST() syntax instead of ::vector to avoid conflict with SQLAlchemy's :param syntax
        embedding_str = f"[{','.join(str(x) for x in embedding)}]"
        self.session.execute(
            text("""
                UPDATE denial_knowledge
                SET embedding = CAST(:embedding AS vector)
                WHERE id = :id
            """),
            {"embedding": embedding_str, "id": str(knowledge.id)}
        )

        return knowledge

    def get(self, id: uuid.UUID) -> Optional[DenialKnowledge]:
        """Get a denial knowledge entry by ID.

        Args:
            id: The UUID of the entry

        Returns:
            The DenialKnowledge instance or None if not found
        """
        return self.session.query(DenialKnowledge).filter(
            DenialKnowledge.id == id
        ).first()

    def get_all(self) -> List[DenialKnowledge]:
        """Get all denial knowledge entries.

        Returns:
            List of all DenialKnowledge instances
        """
        return self.session.query(DenialKnowledge).all()

    def get_by_category(self, category: str) -> List[DenialKnowledge]:
        """Get all denial knowledge entries for a category.

        Args:
            category: The denial category (e.g., 'medical_necessity')

        Returns:
            List of DenialKnowledge instances in that category
        """
        return self.session.query(DenialKnowledge).filter(
            DenialKnowledge.category == category
        ).all()

    def search_similar(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        category_filter: Optional[str] = None,
        similarity_threshold: float = 0.3,
    ) -> List[Dict[str, Any]]:
        """Find denial knowledge entries similar to the query embedding.

        This is the core RAG retrieval function. It uses pgvector's
        cosine distance operator to find similar patterns.

        How cosine distance works:
        - Range: 0 to 2
        - 0 = identical vectors
        - 1 = orthogonal (unrelated)
        - 2 = opposite

        For similarity: similarity = 1 - (distance / 2)
        So threshold of 0.3 means distance < 1.4

        Args:
            query_embedding: The embedding vector to search against
            top_k: Number of results to return
            category_filter: Optional category to filter results
            similarity_threshold: Minimum similarity score (0-1)

        Returns:
            List of dictionaries with denial knowledge and similarity scores
        """
        # Convert threshold to distance (cosine distance = 2 * (1 - similarity))
        max_distance = 2 * (1 - similarity_threshold)

        embedding_str = f"[{','.join(str(x) for x in query_embedding)}]"

        # Build the query
        # Note: Use CAST() syntax instead of ::vector to avoid conflict with SQLAlchemy's :param syntax
        query = """
            SELECT
                id,
                category,
                carc_code,
                denial_reason,
                trigger_patterns,
                remediation,
                appeal_template,
                success_rate,
                typical_payers,
                embedding_text,
                created_at,
                -- Calculate cosine distance (0 = identical, 2 = opposite)
                embedding <=> CAST(:embedding AS vector) AS distance,
                -- Convert to similarity score (1 = identical, 0 = unrelated)
                1 - (embedding <=> CAST(:embedding AS vector)) / 2 AS similarity
            FROM denial_knowledge
            WHERE embedding IS NOT NULL
        """

        params = {"embedding": embedding_str}

        # Add category filter if specified
        if category_filter:
            query += " AND category = :category"
            params["category"] = category_filter

        # Add distance threshold and ordering
        query += """
            AND embedding <=> CAST(:embedding AS vector) < :max_distance
            ORDER BY distance
            LIMIT :top_k
        """
        params["max_distance"] = max_distance
        params["top_k"] = top_k

        result = self.session.execute(text(query), params)
        rows = result.fetchall()

        # Convert to list of dicts
        return [
            {
                "id": str(row.id),
                "category": row.category,
                "carc_code": row.carc_code,
                "denial_reason": row.denial_reason,
                "trigger_patterns": row.trigger_patterns,
                "remediation": row.remediation,
                "appeal_template": row.appeal_template,
                "success_rate": row.success_rate,
                "typical_payers": row.typical_payers,
                "embedding_text": row.embedding_text,
                "distance": float(row.distance),
                "similarity": float(row.similarity),
            }
            for row in rows
        ]

    def search_by_text(
        self,
        text: str,
        embedding_service,
        top_k: int = 5,
        category_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search for similar denial knowledge using text query.

        Convenience method that handles embedding generation.

        Args:
            text: The text to search for
            embedding_service: The EmbeddingService instance
            top_k: Number of results to return
            category_filter: Optional category filter

        Returns:
            List of similar denial knowledge entries
        """
        query_embedding = embedding_service.embed_text(text)
        return self.search_similar(
            query_embedding=query_embedding,
            top_k=top_k,
            category_filter=category_filter,
        )

    def bulk_create(
        self,
        entries: List[Dict[str, Any]],
        embeddings: List[List[float]],
    ) -> int:
        """Bulk create denial knowledge entries with embeddings.

        More efficient than creating one at a time for seeding.

        Args:
            entries: List of denial knowledge dictionaries
            embeddings: Corresponding list of embeddings

        Returns:
            Number of entries created
        """
        if len(entries) != len(embeddings):
            raise ValueError("Number of entries must match number of embeddings")

        created = 0
        for entry, embedding in zip(entries, embeddings):
            knowledge = DenialKnowledge(
                id=uuid.uuid4(),
                category=entry.get("category"),
                carc_code=entry.get("carc_code"),
                denial_reason=entry.get("denial_reason"),
                trigger_patterns=entry.get("trigger_patterns"),
                remediation=entry.get("remediation"),
                appeal_template=entry.get("appeal_template"),
                success_rate=entry.get("success_rate"),
                typical_payers=entry.get("typical_payers"),
                embedding_text=entry.get("embedding_text"),
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            self.create(knowledge, embedding)
            created += 1

        return created

    def delete(self, id: uuid.UUID) -> bool:
        """Delete a denial knowledge entry.

        Args:
            id: The UUID of the entry to delete

        Returns:
            True if deleted, False if not found
        """
        result = self.session.query(DenialKnowledge).filter(
            DenialKnowledge.id == id
        ).delete()
        return result > 0

    def count(self) -> int:
        """Count total denial knowledge entries.

        Returns:
            Number of entries in the table
        """
        return self.session.query(DenialKnowledge).count()

    def clear_all(self) -> int:
        """Delete all denial knowledge entries.

        Use with caution - this removes all data!

        Returns:
            Number of entries deleted
        """
        return self.session.query(DenialKnowledge).delete()
