"""
RAG Retrieval Node

This node performs Retrieval Augmented Generation (RAG) to find similar
denial patterns from the knowledge base.

How it works:
1. Build a text representation of the claim
2. Convert to embedding vector using OpenAI
3. Search the denial_knowledge table using vector similarity
4. Return the top matching denial patterns

The retrieved patterns are then used by the risk assessment node
to make predictions about denial probability.
"""

from contextlib import contextmanager
from typing import List, Dict, Any, Optional
import logging

from pydantic import Field

from core.nodes.base import Node
from core.task import TaskContext
from database.denial_knowledge_repository import DenialKnowledgeRepository
from database.session import db_session
from schemas.claim_schema import ClaimEventSchema
from services.embedding_service import get_embedding_service

logger = logging.getLogger(__name__)


class RAGRetrievalNode(Node):
    """Node that retrieves similar denial patterns from the knowledge base.

    This is the RAG (Retrieval Augmented Generation) component of the
    denial prevention system. It searches for denial patterns that are
    semantically similar to the incoming claim.

    The search uses cosine similarity on vector embeddings to find
    patterns that match the claim's characteristics (diagnosis codes,
    procedure codes, payer, etc.).
    """

    class OutputType(Node.OutputType):
        """Output structure with similar denial patterns."""

        similar_denials: List[Dict[str, Any]] = Field(
            default_factory=list,
            description="List of similar denial patterns from knowledge base",
        )
        retrieval_query: str = Field(
            default="",
            description="The text query used for retrieval",
        )
        num_results: int = Field(
            default=0,
            description="Number of similar patterns found",
        )
        top_categories: List[str] = Field(
            default_factory=list,
            description="Most common denial categories in results",
        )
        average_similarity: float = Field(
            default=0.0,
            description="Average similarity score of results",
        )
        has_high_risk_matches: bool = Field(
            default=False,
            description="Whether any high-similarity matches were found",
        )

    async def process(self, task_context: TaskContext) -> TaskContext:
        """Retrieve similar denial patterns for the claim.

        Args:
            task_context: The workflow context containing the claim

        Returns:
            Updated TaskContext with retrieved denial patterns
        """
        event: ClaimEventSchema = task_context.event

        # Build the search query from claim characteristics
        embedding_service = get_embedding_service()
        retrieval_query = embedding_service.build_claim_embedding_text(
            event.model_dump()
        )

        logger.info(f"RAG retrieval query: {retrieval_query[:200]}...")

        # Get embedding for the query
        try:
            query_embedding = embedding_service.embed_text(retrieval_query)
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            # Return empty results on embedding failure
            output = self.OutputType(
                similar_denials=[],
                retrieval_query=retrieval_query,
                num_results=0,
                top_categories=[],
                average_similarity=0.0,
                has_high_risk_matches=False,
            )
            self.save_output(output)
            return task_context

        # Search the knowledge base
        similar_denials = []
        try:
            with contextmanager(db_session)() as session:
                repository = DenialKnowledgeRepository(session)
                similar_denials = repository.search_similar(
                    query_embedding=query_embedding,
                    top_k=5,
                    similarity_threshold=0.3,
                )
        except Exception as e:
            logger.error(f"Failed to search denial knowledge: {e}")
            # Continue with empty results

        # Analyze results
        top_categories = self._get_top_categories(similar_denials)
        average_similarity = self._calculate_average_similarity(similar_denials)
        has_high_risk_matches = any(
            d.get("similarity", 0) > 0.7 for d in similar_denials
        )

        logger.info(
            f"RAG retrieval found {len(similar_denials)} matches, "
            f"top categories: {top_categories}, "
            f"avg similarity: {average_similarity:.2f}"
        )

        # Save output
        output = self.OutputType(
            similar_denials=similar_denials,
            retrieval_query=retrieval_query,
            num_results=len(similar_denials),
            top_categories=top_categories,
            average_similarity=average_similarity,
            has_high_risk_matches=has_high_risk_matches,
        )
        self.save_output(output)

        return task_context

    def _get_top_categories(
        self, denials: List[Dict[str, Any]], limit: int = 3
    ) -> List[str]:
        """Get the most common denial categories from results."""
        if not denials:
            return []

        category_counts = {}
        for denial in denials:
            category = denial.get("category", "unknown")
            category_counts[category] = category_counts.get(category, 0) + 1

        # Sort by count and return top categories
        sorted_categories = sorted(
            category_counts.items(), key=lambda x: x[1], reverse=True
        )
        return [cat for cat, _ in sorted_categories[:limit]]

    def _calculate_average_similarity(
        self, denials: List[Dict[str, Any]]
    ) -> float:
        """Calculate the average similarity score."""
        if not denials:
            return 0.0

        similarities = [d.get("similarity", 0) for d in denials]
        return sum(similarities) / len(similarities)
