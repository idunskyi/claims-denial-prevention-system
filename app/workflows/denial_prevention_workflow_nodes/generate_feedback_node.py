"""
Generate Feedback Node

This AgentNode generates specific recommendations for medium-risk claims.
It provides actionable feedback on what should be changed or added to
reduce the likelihood of denial.

The feedback includes:
- Specific issues identified
- Recommended actions
- Required documentation
- Suggested code changes (if applicable)
"""

from typing import List, Optional

from pydantic import Field

from core.nodes.agent import AgentNode, AgentConfig, ModelProvider
from core.task import TaskContext
from schemas.claim_schema import ClaimEventSchema
from workflows.denial_prevention_workflow_nodes.risk_assessment_node import RiskAssessmentNode
from workflows.denial_prevention_workflow_nodes.rag_retrieval_node import RAGRetrievalNode


class Recommendation(AgentNode.OutputType):
    """A single recommendation for fixing an issue."""

    issue: str = Field(description="The specific issue identified")
    action: str = Field(description="Recommended action to take")
    priority: str = Field(description="Priority level: high, medium, low")
    category: str = Field(description="Category: documentation, coding, authorization, other")


class GenerateFeedbackNode(AgentNode):
    """Agent node that generates specific recommendations.

    This node analyzes the risk assessment and similar denial patterns
    to provide actionable feedback for preventing denial.

    The feedback is structured to be immediately actionable by
    billing staff or providers.
    """

    class OutputType(AgentNode.OutputType):
        """Feedback output structure."""

        summary: str = Field(
            description="Brief summary of the claim status and main concerns",
        )
        recommendations: List[Recommendation] = Field(
            default_factory=list,
            description="List of specific recommendations",
        )
        required_documentation: List[str] = Field(
            default_factory=list,
            description="Documents that should be added to support the claim",
        )
        suggested_code_changes: List[str] = Field(
            default_factory=list,
            description="Suggested changes to diagnosis or procedure codes",
        )
        appeal_likelihood_if_denied: float = Field(
            ge=0,
            le=1,
            description="Likelihood of successful appeal if denied (0-1)",
        )
        next_steps: str = Field(
            description="Clear next steps for the billing team",
        )

    def get_agent_config(self) -> AgentConfig:
        """Configure the feedback generation agent."""
        instructions = """You are a healthcare claims optimization specialist.
Your job is to provide specific, actionable recommendations to prevent claim denials.

For each issue identified, provide:
1. A clear description of the problem
2. A specific action to fix it
3. Priority (high = must fix, medium = should fix, low = nice to have)
4. Category (documentation, coding, authorization, other)

Guidelines for recommendations:
- Be specific: "Add modifier 25 to E/M code" not "Fix the coding"
- Be actionable: Give steps that can be taken immediately
- Be realistic: Consider what's possible in a billing workflow
- Prioritize: Focus on the highest-impact changes first

Documentation recommendations should specify:
- What type of document is needed
- What it should contain
- Where to obtain it

Code change recommendations should:
- Reference specific codes
- Explain why the change is needed
- Note any modifiers that should be added

Always provide clear next steps that a billing specialist can follow.
"""
        return AgentConfig(
            instructions=instructions,
            output_type=self.OutputType,
            model_provider=ModelProvider.OPENAI,
            model_name="gpt-4o",
        )

    async def process(self, task_context: TaskContext) -> TaskContext:
        """Generate feedback recommendations.

        Args:
            task_context: Context with claim and risk assessment

        Returns:
            Updated TaskContext with feedback
        """
        event: ClaimEventSchema = task_context.event
        risk_output = self.get_output(RiskAssessmentNode)
        rag_output = self.get_output(RAGRetrievalNode)

        # Build the context for the LLM
        context_parts = []

        context_parts.append("## CLAIM SUMMARY")
        context_parts.append(f"Claim ID: {event.claim_id}")
        context_parts.append(f"Billed Amount: ${event.billed_amount}")
        context_parts.append(f"Payer: {event.payer_name}")

        # Add risk assessment
        if risk_output:
            context_parts.append("\n## RISK ASSESSMENT")
            context_parts.append(f"Risk Level: {risk_output.risk_level.value.upper()}")
            context_parts.append(f"Denial Probability: {risk_output.denial_probability:.0%}")
            context_parts.append(f"Primary Risk Factors: {', '.join(risk_output.primary_risk_factors)}")
            context_parts.append(f"Assessment Reasoning: {risk_output.reasoning}")

        # Add similar denial patterns with remediation info
        if rag_output and rag_output.similar_denials:
            context_parts.append("\n## SIMILAR DENIAL PATTERNS & SUCCESSFUL REMEDIATIONS")
            for denial in rag_output.similar_denials[:3]:
                context_parts.append(f"\n### {denial.get('category', 'Unknown')} Denial")
                context_parts.append(f"Reason: {denial.get('denial_reason')}")
                if denial.get('remediation'):
                    context_parts.append(f"Successful Remediation: {denial.get('remediation')}")
                if denial.get('success_rate'):
                    context_parts.append(f"Success Rate When Fixed: {denial.get('success_rate'):.0%}")

        # Build user prompt
        user_prompt = "\n".join(context_parts)
        user_prompt += "\n\n## TASK"
        user_prompt += "\nProvide specific, actionable recommendations to prevent this claim from being denied."
        user_prompt += "\nFocus on the highest-impact changes that can be made before submission."

        # Run the agent
        result = await self.agent.run(user_prompt=user_prompt)
        self.save_output(result.output)

        return task_context
