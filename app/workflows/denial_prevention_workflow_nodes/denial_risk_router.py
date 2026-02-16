"""
Denial Risk Router

This router directs claims to different paths based on the risk assessment:
- HIGH risk → EscalateClaimNode (requires human review)
- MEDIUM risk → GenerateFeedbackNode (provide recommendations)
- LOW risk → ApproveClaimNode (auto-approve, no action needed)

The router uses the output from RiskAssessmentNode to make decisions.
"""

from typing import Optional

from core.nodes.base import Node
from core.nodes.router import BaseRouter, RouterNode
from core.task import TaskContext
from workflows.denial_prevention_workflow_nodes.risk_assessment_node import (
    RiskAssessmentNode,
    RiskLevel,
)


class HighRiskRouter(RouterNode):
    """Routes high-risk claims to escalation.

    A claim is high risk if:
    - Risk level is HIGH, or
    - Denial probability > 70%
    """

    def determine_next_node(self, task_context: TaskContext) -> Optional[Node]:
        """Check if claim should be escalated.

        Args:
            task_context: The workflow context

        Returns:
            EscalateClaimNode if high risk, None otherwise
        """
        risk_output = self.get_output(RiskAssessmentNode)

        if not risk_output:
            return None

        is_high_risk = (
            risk_output.risk_level == RiskLevel.HIGH
            or risk_output.denial_probability > 0.7
        )

        if is_high_risk:
            # Import here to avoid circular imports
            from workflows.denial_prevention_workflow_nodes.escalate_claim_node import (
                EscalateClaimNode,
            )
            return EscalateClaimNode(task_context=task_context)

        return None


class MediumRiskRouter(RouterNode):
    """Routes medium-risk claims to feedback generation.

    A claim is medium risk if:
    - Risk level is MEDIUM, or
    - Denial probability between 30-70%
    """

    def determine_next_node(self, task_context: TaskContext) -> Optional[Node]:
        """Check if claim needs feedback.

        Args:
            task_context: The workflow context

        Returns:
            GenerateFeedbackNode if medium risk, None otherwise
        """
        risk_output = self.get_output(RiskAssessmentNode)

        if not risk_output:
            return None

        is_medium_risk = (
            risk_output.risk_level == RiskLevel.MEDIUM
            or (0.3 <= risk_output.denial_probability <= 0.7)
        )

        if is_medium_risk:
            from workflows.denial_prevention_workflow_nodes.generate_feedback_node import (
                GenerateFeedbackNode,
            )
            return GenerateFeedbackNode(task_context=task_context)

        return None


class DenialRiskRouter(BaseRouter):
    """Main router for denial risk-based claim routing.

    Routing logic:
    1. Check if high risk → Escalate
    2. Check if medium risk → Generate feedback
    3. Default (low risk) → Approve

    The fallback is ApproveClaimNode, which means claims that don't
    match high or medium risk criteria are considered safe.
    """

    def __init__(self):
        """Initialize the router with its routes and fallback."""
        super().__init__()
        self.routes = [
            HighRiskRouter(),
            MediumRiskRouter(),
        ]
        self.fallback = None  # We'll handle fallback in route() method

    def route(self, task_context: TaskContext) -> Node:
        """Override route to handle fallback with task_context."""
        for route_node in self.routes:
            route_node.task_context = task_context
            next_node = route_node.determine_next_node(task_context)
            if next_node:
                return next_node

        # Fallback to approval for low risk claims
        from workflows.denial_prevention_workflow_nodes.approve_claim_node import (
            ApproveClaimNode,
        )
        return ApproveClaimNode(task_context=task_context)
