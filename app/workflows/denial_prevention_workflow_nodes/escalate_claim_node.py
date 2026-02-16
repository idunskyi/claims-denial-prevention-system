"""
Escalate Claim Node

Terminal node for high-risk claims. This node signals that the claim
requires human review before submission due to high denial risk.

In a production system, this might:
- Create a work queue item
- Send email to supervisor
- Flag in the billing dashboard
- Pause automated submission
"""

import logging
from datetime import datetime
from typing import List

from pydantic import Field

from core.nodes.base import Node
from core.task import TaskContext
from schemas.claim_schema import ClaimEventSchema
from workflows.denial_prevention_workflow_nodes.risk_assessment_node import RiskAssessmentNode
from workflows.denial_prevention_workflow_nodes.rag_retrieval_node import RAGRetrievalNode

logger = logging.getLogger(__name__)


class EscalateClaimNode(Node):
    """Terminal node that escalates high-risk claims for human review.

    This node is reached when a claim has been assessed as high risk
    and should not be submitted without human intervention.
    """

    class OutputType(Node.OutputType):
        """Escalation output structure."""

        status: str = Field(
            default="escalated",
            description="Claim status",
        )
        message: str = Field(
            description="Escalation message with details",
        )
        denial_probability: float = Field(
            description="Denial probability from assessment",
        )
        primary_concerns: List[str] = Field(
            default_factory=list,
            description="Main reasons for escalation",
        )
        likely_denial_categories: List[str] = Field(
            default_factory=list,
            description="Most likely denial categories",
        )
        reviewed_at: str = Field(
            description="Timestamp of review",
        )
        recommendation: str = Field(
            description="Recommendation for the reviewer",
        )
        urgency: str = Field(
            default="high",
            description="Urgency level for review",
        )

    async def process(self, task_context: TaskContext) -> TaskContext:
        """Escalate the claim for human review.

        Args:
            task_context: The workflow context

        Returns:
            Updated TaskContext with escalation status
        """
        event: ClaimEventSchema = task_context.event
        risk_output = self.get_output(RiskAssessmentNode)
        rag_output = self.get_output(RAGRetrievalNode)

        denial_probability = 0.8
        primary_concerns = []
        likely_categories = []
        reasoning = "High risk claim requires review."

        if risk_output:
            denial_probability = risk_output.denial_probability
            primary_concerns = risk_output.primary_risk_factors
            likely_categories = risk_output.likely_denial_categories
            reasoning = risk_output.reasoning

        # Build escalation message
        message = (
            f"ESCALATION REQUIRED: Claim {event.claim_id}\n"
            f"Denial probability: {denial_probability:.0%}\n"
            f"Amount at risk: ${event.billed_amount}\n"
            f"Primary concerns: {', '.join(primary_concerns)}\n"
            f"Assessment: {reasoning}"
        )

        # Build recommendation based on the issues
        if "missing_prior_auth" in primary_concerns:
            recommendation = (
                "URGENT: Obtain prior authorization before submission. "
                "Contact payer for expedited auth if needed."
            )
        elif any("coding" in c.lower() for c in likely_categories):
            recommendation = (
                "Review coding with provider. Ensure diagnosis supports "
                "the procedures billed and codes are specific enough."
            )
        elif any("documentation" in c.lower() for c in likely_categories):
            recommendation = (
                "Gather additional clinical documentation before submission. "
                "Consider attaching operative notes or detailed progress notes."
            )
        else:
            recommendation = (
                "Review claim with billing supervisor before submission. "
                "Consider the risk factors identified and address if possible."
            )

        logger.warning(
            f"Claim escalated: {event.claim_id}, "
            f"risk: {denial_probability:.0%}, "
            f"concerns: {primary_concerns}"
        )

        output = self.OutputType(
            status="escalated",
            message=message,
            denial_probability=denial_probability,
            primary_concerns=primary_concerns,
            likely_denial_categories=likely_categories,
            reviewed_at=datetime.now().isoformat(),
            recommendation=recommendation,
            urgency="high" if denial_probability > 0.85 else "medium",
        )
        self.save_output(output)

        return task_context
