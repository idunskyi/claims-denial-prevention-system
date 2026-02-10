"""
Analyze Claim Node

This is a ConcurrentNode that runs multiple analysis tasks in parallel:
1. ExtractCodesNode - Extract and validate codes
2. RAGRetrievalNode - Find similar denial patterns (this could be moved outside)

By running these concurrently, we reduce latency when processing claims.

After the concurrent nodes complete, this node aggregates the results
and identifies any rule-based risk factors.
"""

from typing import List
import logging

from pydantic import Field

from core.nodes.concurrent import ConcurrentNode
from core.task import TaskContext
from schemas.claim_schema import ClaimEventSchema

logger = logging.getLogger(__name__)


class AnalyzeClaimNode(ConcurrentNode):
    """Concurrent node that runs parallel claim analysis.

    This node orchestrates multiple analysis tasks to run simultaneously,
    then aggregates their results and performs additional rule-based checks.

    Concurrent nodes (defined in workflow NodeConfig):
    - ExtractCodesNode: Code extraction and validation
    - Additional analysis nodes can be added here
    """

    class OutputType(ConcurrentNode.OutputType):
        """Aggregated output from concurrent analysis."""

        rule_based_risks: List[str] = Field(
            default_factory=list,
            description="Risk factors identified by rule-based checks",
        )
        analysis_complete: bool = Field(
            default=True,
            description="Whether analysis completed successfully",
        )

    async def process(self, task_context: TaskContext) -> TaskContext:
        """Run concurrent analysis and aggregate results.

        Args:
            task_context: The workflow context containing the claim

        Returns:
            Updated TaskContext with analysis results
        """
        # Run concurrent nodes (ExtractCodesNode, etc.)
        await self.execute_nodes_concurrently(task_context)

        # Now perform additional rule-based analysis
        event: ClaimEventSchema = task_context.event
        rule_based_risks = self._check_rule_based_risks(event)

        if rule_based_risks:
            logger.info(f"Rule-based risks identified: {rule_based_risks}")

        # Save aggregated output
        output = self.OutputType(
            rule_based_risks=rule_based_risks,
            analysis_complete=True,
        )
        self.save_output(output)

        return task_context

    def _check_rule_based_risks(self, event: ClaimEventSchema) -> List[str]:
        """Perform rule-based risk checks on the claim.

        These are deterministic checks that don't require ML/LLM.
        They catch obvious issues before the AI assessment.

        Args:
            event: The claim event to check

        Returns:
            List of identified risk factors
        """
        risks = []

        # Rule 1: Prior auth required but not obtained
        if event.prior_auth_required and not event.prior_auth_number:
            risks.append("missing_prior_auth")

        # Rule 2: High-cost procedure without documentation
        if event.billed_amount and float(event.billed_amount) > 10000:
            if not event.clinical_notes_summary:
                risks.append("high_cost_no_documentation")

        # Rule 3: HMO without referral indicators
        if event.plan_type and event.plan_type.upper() == "HMO":
            # In real implementation, would check for referral
            pass

        # Rule 4: Timely filing risk
        if event.service_date and event.submission_date:
            from datetime import date
            if isinstance(event.service_date, date) and isinstance(event.submission_date, date):
                days_since_service = (event.submission_date - event.service_date).days
                # Most payers require submission within 90-365 days
                if days_since_service > 80:
                    risks.append("timely_filing_risk")

        # Rule 5: No diagnosis codes
        if not event.diagnosis_codes:
            risks.append("no_diagnosis_codes")

        # Rule 6: No procedure codes
        if not event.procedure_codes:
            risks.append("no_procedure_codes")

        # Rule 7: Unspecified diagnosis with high-level E/M
        high_level_em = ["99214", "99215", "99204", "99205"]
        has_high_em = any(
            p.code in high_level_em for p in event.procedure_codes
        )
        has_unspecified = any(
            d.code.endswith(".9") or d.code.endswith(".99")
            for d in event.diagnosis_codes
        )
        if has_high_em and has_unspecified:
            risks.append("high_level_em_unspecified_diagnosis")

        return risks
