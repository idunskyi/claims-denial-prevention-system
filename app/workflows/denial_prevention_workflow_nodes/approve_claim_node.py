"""
Approve Claim Node

Terminal node for low-risk claims. This node signals that the claim
has passed review and can proceed to submission without changes.

In a production system, this might:
- Log the approval
- Update a dashboard
- Trigger submission to the clearinghouse
- Send a notification
"""

import logging
from datetime import datetime

from pydantic import Field

from core.nodes.base import Node
from core.task import TaskContext
from schemas.claim_schema import ClaimEventSchema
from workflows.denial_prevention_workflow_nodes.risk_assessment_node import RiskAssessmentNode

logger = logging.getLogger(__name__)


class ApproveClaimNode(Node):
    """Terminal node that approves low-risk claims.

    This node is reached when a claim has been assessed as low risk
    and can proceed to submission without intervention.
    """

    class OutputType(Node.OutputType):
        """Approval output structure."""

        status: str = Field(
            default="approved",
            description="Claim status",
        )
        message: str = Field(
            description="Approval message",
        )
        denial_probability: float = Field(
            description="Final denial probability from assessment",
        )
        reviewed_at: str = Field(
            description="Timestamp of review",
        )
        recommendation: str = Field(
            default="Proceed with submission",
            description="Recommendation for next steps",
        )

    async def process(self, task_context: TaskContext) -> TaskContext:
        """Approve the claim for submission.

        Args:
            task_context: The workflow context

        Returns:
            Updated TaskContext with approval status
        """
        event: ClaimEventSchema = task_context.event
        risk_output = self.get_output(RiskAssessmentNode)

        denial_probability = 0.0
        if risk_output:
            denial_probability = risk_output.denial_probability

        message = (
            f"Claim {event.claim_id} approved for submission. "
            f"Denial risk is low ({denial_probability:.0%}). "
            f"No changes required."
        )

        logger.info(f"Claim approved: {event.claim_id}, risk: {denial_probability:.0%}")

        output = self.OutputType(
            status="approved",
            message=message,
            denial_probability=denial_probability,
            reviewed_at=datetime.now().isoformat(),
            recommendation="Proceed with submission",
        )
        self.save_output(output)

        return task_context
