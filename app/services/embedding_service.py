"""
Embedding Service Module

This module provides a service for generating text embeddings using OpenAI's
embedding models. Embeddings are vector representations of text that capture
semantic meaning, enabling similarity search.

How it works:
1. Text is sent to OpenAI's embedding API
2. API returns a vector of 1536 floats (for text-embedding-3-small)
3. We store this vector in PostgreSQL with pgvector
4. Later, we can find similar texts by comparing vectors

The service uses text-embedding-3-small by default, which offers:
- Good quality for most use cases
- 1536 dimensions
- Lower cost than text-embedding-3-large
"""

import os
from typing import List, Optional
import logging

from openai import OpenAI

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating text embeddings using OpenAI.

    This service wraps the OpenAI embeddings API and provides methods
    for generating embeddings for single texts or batches.

    Attributes:
        model: The OpenAI embedding model to use
        dimensions: The number of dimensions in the output vectors

    Example:
        service = EmbeddingService()
        embedding = service.embed_text("Patient has chronic back pain")
        # embedding is a list of 1536 floats
    """

    # Model options:
    # - text-embedding-3-small: 1536 dims, good quality, lower cost
    # - text-embedding-3-large: 3072 dims, best quality, higher cost
    # - text-embedding-ada-002: 1536 dims, legacy model
    DEFAULT_MODEL = "text-embedding-3-small"
    DEFAULT_DIMENSIONS = 1536

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        dimensions: int = DEFAULT_DIMENSIONS,
        api_key: Optional[str] = None,
    ):
        """Initialize the embedding service.

        Args:
            model: The OpenAI embedding model to use
            dimensions: Number of dimensions for the embedding
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
        """
        self.model = model
        self.dimensions = dimensions
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    def embed_text(self, text: str) -> List[float]:
        """Generate an embedding for a single text.

        Args:
            text: The text to embed

        Returns:
            A list of floats representing the embedding vector

        Raises:
            OpenAIError: If the API call fails
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding, returning zero vector")
            return [0.0] * self.dimensions

        try:
            response = self.client.embeddings.create(
                input=text,
                model=self.model,
                dimensions=self.dimensions,
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts in a single API call.

        This is more efficient than calling embed_text multiple times
        because it batches the requests.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors (one per input text)

        Raises:
            OpenAIError: If the API call fails
        """
        if not texts:
            return []

        # Filter empty texts and track their positions
        non_empty = [(i, t) for i, t in enumerate(texts) if t and t.strip()]

        if not non_empty:
            return [[0.0] * self.dimensions for _ in texts]

        try:
            response = self.client.embeddings.create(
                input=[t for _, t in non_empty],
                model=self.model,
                dimensions=self.dimensions,
            )

            # Reconstruct results with zero vectors for empty inputs
            results = [[0.0] * self.dimensions for _ in texts]
            for (orig_idx, _), embedding_data in zip(non_empty, response.data):
                results[orig_idx] = embedding_data.embedding

            return results
        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {e}")
            raise

    def build_claim_embedding_text(self, claim: dict) -> str:
        """Build the text representation of a claim for embedding.

        This combines relevant claim fields into a single text that
        captures the semantic characteristics for similarity search.

        Args:
            claim: The claim dictionary with codes, payer info, etc.

        Returns:
            A formatted string suitable for embedding
        """
        parts = []

        # Add diagnosis codes and descriptions
        for diag in claim.get("diagnosis_codes", []):
            code = diag.get("code", "")
            display = diag.get("display", "")
            parts.append(f"Diagnosis: {code} {display}")

        # Add procedure codes and descriptions
        for proc in claim.get("procedure_codes", []):
            code = proc.get("code", "")
            display = proc.get("display", "")
            parts.append(f"Procedure: {code} {display}")

        # Add payer information
        payer = claim.get("payer_name", "")
        plan_type = claim.get("plan_type", "")
        if payer:
            parts.append(f"Payer: {payer} {plan_type}")

        # Add facility type
        facility_type = claim.get("facility_type", "")
        if facility_type:
            parts.append(f"Facility type: {facility_type}")

        # Add prior auth status
        if claim.get("prior_auth_required") and not claim.get("prior_auth_number"):
            parts.append("Prior authorization required but not obtained")

        # Add clinical notes if available
        notes = claim.get("clinical_notes_summary")
        if notes:
            parts.append(f"Clinical notes: {notes}")

        return " | ".join(parts) if parts else "General claim"


# Singleton instance for convenience
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get the singleton embedding service instance.

    Returns:
        The shared EmbeddingService instance
    """
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
