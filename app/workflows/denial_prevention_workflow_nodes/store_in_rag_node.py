"""
Store in RAG Node

This node stores analyzed denial patterns in the vector knowledge base.
It's the final step in the denial learning workflow.

What this node does:
1. Takes the analyzed denial pattern
2. Generates an embedding for similarity search
3. Stores the pattern in the denial_knowledge table
4. The pattern is now available for future RAG queries

This is how the system "learns" from denials - each stored pattern
helps predict similar denials in the future.
"""

import uuid
from contextlib import contextmanager
from datetime import datetime
import logging

from pydantic import Field

from core.nodes.base import Node
from core.task import TaskContext
from database.denial_knowledge import DenialKnowledge
from database.denial_knowledge_repository import DenialKnowledgeRepository
from database.session import db_session
from schemas.denial_schema import DenialEventSchema
from services.embedding_service import get_embedding_service
from workflows.denial_prevention_workflow_nodes.analyze_denial_node import AnalyzeDenialNode

logger = logging.getLogger(__name__)


class StoreInRAGNode(Node):
    """Node that stores denial patterns in the knowledge base.

    This node persists analyzed denial patterns to the PostgreSQL
    database with vector embeddings for similarity search.
    """

    class OutputType(Node.OutputType):
        """Storage output structure."""

        stored: bool = Field(
            default=False,
            description="Whether the pattern was successfully stored",
        )
        knowledge_id: str = Field(
            default="",
            description="ID of the stored knowledge entry",
        )
        message: str = Field(
            description="Status message",
        )
        embedding_generated: bool = Field(
            default=False,
            description="Whether embedding was successfully generated",
        )

    async def process(self, task_context: TaskContext) -> TaskContext:
        """Store the denial pattern in the knowledge base.

        Args:
            task_context: Context with analyzed denial

        Returns:
            Updated TaskContext with storage status
        """
        event: DenialEventSchema = task_context.event
        analysis_output = self.get_output(AnalyzeDenialNode)

        if not analysis_output:
            logger.error("No analysis output found, cannot store pattern")
            output = self.OutputType(
                stored=False,
                message="Analysis output not found",
            )
            self.save_output(output)
            return task_context

        # Check if we should store this pattern
        if not analysis_output.should_store:
            logger.info("Pattern marked as should_store=False, skipping storage")
            output = self.OutputType(
                stored=False,
                message="Pattern not suitable for storage per analysis",
            )
            self.save_output(output)
            return task_context

        # Generate embedding
        embedding_service = get_embedding_service()
        try:
            embedding = embedding_service.embed_text(analysis_output.embedding_text)
            embedding_generated = True
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            output = self.OutputType(
                stored=False,
                message=f"Embedding generation failed: {e}",
                embedding_generated=False,
            )
            self.save_output(output)
            return task_context

        # Build the knowledge entry
        knowledge = DenialKnowledge(
            id=uuid.uuid4(),
            category=analysis_output.confirmed_category,
            carc_code=event.denial_code,
            denial_reason=analysis_output.denial_pattern_summary,
            trigger_patterns={
                "characteristics": analysis_output.trigger_characteristics,
                "diagnosis_codes": event.diagnosis_codes,
                "procedure_codes": event.procedure_codes,
                "payer_specific": analysis_output.payer_specific,
                "original_payer": event.payer_id,
            },
            remediation=analysis_output.recommended_remediation,
            appeal_template=analysis_output.appeal_strategy,
            success_rate=analysis_output.estimated_success_rate,
            typical_payers=[event.payer_id] if analysis_output.payer_specific else ["all"],
            embedding_text=analysis_output.embedding_text,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        # Store in database
        try:
            with contextmanager(db_session)() as session:
                repository = DenialKnowledgeRepository(session)
                repository.create(knowledge, embedding)

            logger.info(
                f"Stored denial pattern: category={knowledge.category}, "
                f"id={knowledge.id}"
            )

            output = self.OutputType(
                stored=True,
                knowledge_id=str(knowledge.id),
                message=f"Successfully stored denial pattern in knowledge base",
                embedding_generated=embedding_generated,
            )

        except Exception as e:
            logger.error(f"Failed to store denial pattern: {e}")
            output = self.OutputType(
                stored=False,
                message=f"Database storage failed: {e}",
                embedding_generated=embedding_generated,
            )

        self.save_output(output)
        return task_context
