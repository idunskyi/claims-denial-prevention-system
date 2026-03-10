"""
Seed Denial Knowledge Base

This script populates the PostgreSQL denial_knowledge table with
the synthetic denial patterns we generated.

It:
1. Loads the denial knowledge JSON files
2. Generates embeddings for each entry using OpenAI
3. Stores the entries with embeddings in the database

Run this AFTER:
1. Docker containers are running
2. Database migrations have been applied

Usage:
    cd /path/to/genai-launchpad
    python playground/data_prep/seed_denial_knowledge.py
"""

import json
import sys
from pathlib import Path
from contextlib import contextmanager
import logging

# Set up paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "app"))

from dotenv import load_dotenv

# Load environment variables
env_path = PROJECT_ROOT / "app" / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    # Try docker env
    env_path = PROJECT_ROOT / "docker" / ".env"
    load_dotenv(env_path)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Now import app modules
from database.session import db_session
from database.denial_knowledge import DenialKnowledge
from database.denial_knowledge_repository import DenialKnowledgeRepository
from services.embedding_service import EmbeddingService


DENIALS_DIR = PROJECT_ROOT / "requests" / "denial_prevention" / "denials"


def load_denial_knowledge() -> list:
    """Load all denial knowledge entries from JSON files."""
    all_denials_file = DENIALS_DIR / "_all_denials.json"

    if not all_denials_file.exists():
        logger.error(f"Denial knowledge file not found: {all_denials_file}")
        logger.error("Run generate_denial_knowledge.py first!")
        return []

    with open(all_denials_file, 'r') as f:
        return json.load(f)


def seed_knowledge_base(entries: list, batch_size: int = 10) -> int:
    """Seed the denial knowledge base with entries.

    Args:
        entries: List of denial knowledge dictionaries
        batch_size: Number of entries to process before committing

    Returns:
        Number of entries successfully seeded
    """
    embedding_service = EmbeddingService()

    # First, check current count
    with contextmanager(db_session)() as session:
        repository = DenialKnowledgeRepository(session)
        current_count = repository.count()
        logger.info(f"Current denial knowledge entries: {current_count}")

        if current_count > 0:
            logger.warning("Knowledge base already has entries.")
            response = input("Clear existing entries and re-seed? (y/N): ")
            if response.lower() == 'y':
                repository.clear_all()
                logger.info("Cleared existing entries")
            else:
                logger.info("Keeping existing entries, adding new ones")

    # Generate embeddings in batches
    logger.info(f"Generating embeddings for {len(entries)} entries...")

    embedding_texts = [e.get("embedding_text", "") for e in entries]
    embeddings = []

    for i in range(0, len(embedding_texts), batch_size):
        batch = embedding_texts[i:i + batch_size]
        logger.info(f"  Processing batch {i // batch_size + 1}/{(len(embedding_texts) + batch_size - 1) // batch_size}")
        try:
            batch_embeddings = embedding_service.embed_texts(batch)
            embeddings.extend(batch_embeddings)
        except Exception as e:
            logger.error(f"  Error generating embeddings for batch: {e}")
            # Add zero vectors for failed batch
            embeddings.extend([[0.0] * 1536 for _ in batch])

    logger.info(f"Generated {len(embeddings)} embeddings")

    # Store in database
    logger.info("Storing entries in database...")
    stored = 0

    with contextmanager(db_session)() as session:
        repository = DenialKnowledgeRepository(session)

        for entry, embedding in zip(entries, embeddings):
            try:
                repository.create(
                    DenialKnowledge(
                        category=entry.get("category"),
                        carc_code=entry.get("carc_code"),
                        denial_reason=entry.get("denial_reason"),
                        trigger_patterns=entry.get("trigger_patterns"),
                        remediation=entry.get("remediation"),
                        appeal_template=entry.get("appeal_template"),
                        success_rate=entry.get("success_rate"),
                        typical_payers=entry.get("typical_payers"),
                        embedding_text=entry.get("embedding_text"),
                    ),
                    embedding=embedding
                )
                stored += 1
            except Exception as e:
                logger.error(f"  Error storing entry: {e}")

    return stored


def verify_seeding():
    """Verify the seeding was successful by running a test query."""
    logger.info("\nVerifying seeding with test query...")

    embedding_service = EmbeddingService()

    # Test query - should find prior authorization related entries
    test_query = "Missing prior authorization for surgical procedure"
    query_embedding = embedding_service.embed_text(test_query)

    with contextmanager(db_session)() as session:
        repository = DenialKnowledgeRepository(session)

        # Get count
        count = repository.count()
        logger.info(f"Total entries in knowledge base: {count}")

        # Search for similar
        results = repository.search_similar(
            query_embedding=query_embedding,
            top_k=3,
        )

        if results:
            logger.info(f"\nTest query: '{test_query}'")
            logger.info(f"Found {len(results)} similar entries:")
            for i, result in enumerate(results, 1):
                logger.info(f"  {i}. [{result['category']}] {result['denial_reason'][:80]}...")
                logger.info(f"     Similarity: {result['similarity']:.2f}")
        else:
            logger.warning("No results found for test query!")


def main():
    logger.info("=" * 60)
    logger.info("DENIAL KNOWLEDGE BASE SEEDING")
    logger.info("=" * 60)

    # Load entries
    entries = load_denial_knowledge()
    if not entries:
        return

    logger.info(f"Loaded {len(entries)} denial knowledge entries")

    # Seed the database
    stored = seed_knowledge_base(entries)
    logger.info(f"\nSuccessfully stored {stored}/{len(entries)} entries")

    # Verify
    verify_seeding()

    logger.info("\n" + "=" * 60)
    logger.info("SEEDING COMPLETE")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
