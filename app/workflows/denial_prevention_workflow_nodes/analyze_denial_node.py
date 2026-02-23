"""
Analyze Denial Node

This AgentNode analyzes incoming denial notifications to extract
patterns that can be stored in the knowledge base.

When a claim is denied, this node:
1. Parses the denial information
2. Categorizes the denial
3. Extracts the pattern characteristics
4. Generates remediation suggestions
5. Prepares the data for storage

The extracted patterns help improve future denial predictions.
"""

from typing import List, Optional

from pydantic import Field

from core.nodes.agent import AgentNode, AgentConfig, ModelProvider
from core.task import TaskContext
from schemas.denial_schema import DenialEventSchema, DenialCategory


class AnalyzeDenialNode(AgentNode):
    """Agent node that analyzes denial patterns for learning.

    This node uses an LLM to analyze denial notifications and extract
    structured patterns that can be stored in the knowledge base.

    The analysis produces:
    - Denial category confirmation/refinement
    - Trigger patterns (what caused the denial)
    - Remediation suggestions
    - Appeal strategy recommendations
    """

    class OutputType(AgentNode.OutputType):
        """Analysis output structure."""

        confirmed_category: str = Field(
            description="Confirmed or refined denial category",
        )
        denial_pattern_summary: str = Field(
            description="Concise summary of the denial pattern",
        )
        trigger_characteristics: List[str] = Field(
            default_factory=list,
            description="Claim characteristics that triggered this denial",
        )
        payer_specific: bool = Field(
            default=False,
            description="Whether this pattern is specific to this payer",
        )
        recommended_remediation: str = Field(
            description="Recommended remediation for future claims",
        )
        appeal_strategy: Optional[str] = Field(
            default=None,
            description="Suggested appeal strategy if applicable",
        )
        estimated_success_rate: float = Field(
            ge=0,
            le=1,
            description="Estimated success rate if remediation is applied",
        )
        embedding_text: str = Field(
            description="Text to use for generating the knowledge base embedding",
        )
        should_store: bool = Field(
            default=True,
            description="Whether this pattern should be stored in the knowledge base",
        )

    def get_agent_config(self) -> AgentConfig:
        """Configure the denial analysis agent."""
        instructions = """You are a healthcare claims denial analyst.
Your job is to analyze denial notifications and extract patterns that can
help prevent similar denials in the future.

For each denial, analyze:
1. The root cause - what specifically caused the denial
2. The claim characteristics that triggered it
3. Whether this is payer-specific or universal
4. What could have been done differently

Generate:
- A clear remediation strategy for future claims
- An appeal strategy if the denial seems contestable
- An estimated success rate (be realistic)
- Text that captures the essence of this denial pattern for similarity search

Categories:
- medical_necessity: Procedure deemed not medically necessary
- prior_authorization: Missing or invalid prior auth
- coding_error: Code mismatches, invalid codes, bundling issues
- duplicate: Duplicate claim submission
- timely_filing: Submission deadline missed
- coverage_terminated: Patient coverage issues
- non_covered_service: Service not covered by plan
- out_of_network: Provider/facility not in network
- documentation: Missing or insufficient documentation
- bundling: Services should be billed together
- benefit_maximum: Benefit limits exceeded

Be specific in your analysis. The goal is to build a knowledge base
that helps predict and prevent future denials.
"""
        return AgentConfig(
            instructions=instructions,
            output_type=self.OutputType,
            model_provider=ModelProvider.OPENAI,
            model_name="gpt-4o",
        )

    async def process(self, task_context: TaskContext) -> TaskContext:
        """Analyze the denial for pattern extraction.

        Args:
            task_context: Context with denial event

        Returns:
            Updated TaskContext with analysis results
        """
        event: DenialEventSchema = task_context.event

        # Build context for the LLM
        context_parts = []

        context_parts.append("## DENIAL INFORMATION")
        context_parts.append(f"Denial Code (CARC): {event.denial_code}")
        context_parts.append(f"Denial Reason: {event.denial_reason}")
        context_parts.append(f"Initial Category: {event.denial_category.value}")

        context_parts.append("\n## ORIGINAL CLAIM")
        context_parts.append(f"Diagnosis Codes: {', '.join(event.diagnosis_codes)}")
        context_parts.append(f"Procedure Codes: {', '.join(event.procedure_codes)}")
        context_parts.append(f"Modifiers: {', '.join(event.modifiers) if event.modifiers else 'None'}")
        context_parts.append(f"Billed Amount: ${event.billed_amount}")
        context_parts.append(f"Allowed Amount: ${event.allowed_amount or 0}")

        context_parts.append("\n## PAYER INFORMATION")
        context_parts.append(f"Payer: {event.payer_name} ({event.payer_id})")
        context_parts.append(f"Plan Type: {event.plan_type}")

        if event.appeal_filed:
            context_parts.append("\n## APPEAL INFORMATION")
            context_parts.append(f"Appeal Filed: Yes")
            context_parts.append(f"Appeal Outcome: {event.appeal_outcome}")
            if event.appeal_notes:
                context_parts.append(f"Appeal Notes: {event.appeal_notes}")
            if event.remediation_applied:
                context_parts.append(f"Remediation Applied: {event.remediation_applied}")

        if event.clinical_notes:
            context_parts.append("\n## CLINICAL NOTES")
            context_parts.append(event.clinical_notes)

        # Build user prompt
        user_prompt = "\n".join(context_parts)
        user_prompt += "\n\n## TASK"
        user_prompt += "\nAnalyze this denial and extract patterns for the knowledge base."
        user_prompt += "\nGenerate embedding text that captures the key characteristics for similarity search."

        # Run the agent
        result = await self.agent.run(user_prompt=user_prompt)
        self.save_output(result.output)

        return task_context
