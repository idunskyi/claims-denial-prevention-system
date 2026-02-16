"""
Risk Assessment Node

This is an AgentNode that uses an LLM to assess the denial risk of a claim.
It combines:
1. Rule-based risks from AnalyzeClaimNode
2. Similar denial patterns from RAGRetrievalNode
3. Claim characteristics

The agent synthesizes all this information to produce a risk assessment
with probability, risk level, and detailed reasoning.
"""

from enum import Enum
from typing import List, Optional

from pydantic import Field

from core.nodes.agent import AgentNode, AgentConfig, ModelProvider
from core.task import TaskContext
from schemas.claim_schema import ClaimEventSchema
from workflows.denial_prevention_workflow_nodes.analyze_claim_node import AnalyzeClaimNode
from workflows.denial_prevention_workflow_nodes.extract_codes_node import ExtractCodesNode
from workflows.denial_prevention_workflow_nodes.rag_retrieval_node import RAGRetrievalNode


class RiskLevel(str, Enum):
    """Denial risk levels."""

    LOW = "low"          # < 30% denial probability
    MEDIUM = "medium"    # 30-70% denial probability
    HIGH = "high"        # > 70% denial probability


class RiskAssessmentNode(AgentNode):
    """Agent node that assesses denial risk using LLM.

    This node takes all the analysis results and uses an LLM to:
    1. Synthesize the information
    2. Identify the most likely denial reasons
    3. Assign a risk probability
    4. Provide detailed reasoning

    The LLM has access to:
    - The claim data
    - Extracted codes and any issues
    - Similar denial patterns from the knowledge base
    - Rule-based risk factors
    """

    class OutputType(AgentNode.OutputType):
        """Risk assessment output structure."""

        risk_level: RiskLevel = Field(
            description="Overall risk level (low, medium, high)"
        )
        denial_probability: float = Field(
            ge=0,
            le=1,
            description="Probability of denial (0-1)",
        )
        primary_risk_factors: List[str] = Field(
            default_factory=list,
            description="Main factors contributing to denial risk",
        )
        likely_denial_categories: List[str] = Field(
            default_factory=list,
            description="Most likely denial categories if denied",
        )
        reasoning: str = Field(
            description="Detailed explanation of the risk assessment",
        )
        confidence: float = Field(
            ge=0,
            le=1,
            description="Confidence in this assessment (0-1)",
        )

    def get_agent_config(self) -> AgentConfig:
        """Configure the risk assessment agent."""
        instructions = """You are a healthcare claims denial risk assessment specialist.
Your job is to analyze claims and predict the likelihood of denial based on:
1. The claim's diagnosis and procedure codes
2. Similar denial patterns from our knowledge base
3. Rule-based risk factors already identified
4. Payer-specific patterns

When assessing risk, consider:
- Code appropriateness: Does the diagnosis support the procedure?
- Prior authorization: Is it required and obtained?
- Documentation: Is there sufficient supporting documentation?
- Coding accuracy: Are codes specific enough?
- Timely filing: Is the claim within filing limits?
- Coverage: Is the service covered under the plan?
- Medical necessity: Is the service medically necessary?

Risk Levels:
- LOW (< 30%): Claim looks clean, minimal risk factors
- MEDIUM (30-70%): Some concerns, may need attention
- HIGH (> 70%): Significant issues, likely to be denied

Be specific in your reasoning and cite the similar denial patterns when relevant.
"""
        return AgentConfig(
            instructions=instructions,
            output_type=self.OutputType,
            model_provider=ModelProvider.OPENAI,
            model_name="gpt-4o",
        )

    async def process(self, task_context: TaskContext) -> TaskContext:
        """Perform risk assessment on the claim.

        Args:
            task_context: Context with claim and analysis results

        Returns:
            Updated TaskContext with risk assessment
        """
        event: ClaimEventSchema = task_context.event

        # Get outputs from prior nodes
        analyze_output = self.get_output(AnalyzeClaimNode)
        extract_output = self.get_output(ExtractCodesNode)
        rag_output = self.get_output(RAGRetrievalNode)

        # Build the context for the LLM
        context_parts = []

        # Add claim summary
        context_parts.append("## CLAIM INFORMATION")
        context_parts.append(f"Claim ID: {event.claim_id}")
        context_parts.append(f"Patient Age: {event.patient_age}")
        context_parts.append(f"Service Date: {event.service_date}")
        context_parts.append(f"Billed Amount: ${event.billed_amount}")
        context_parts.append(f"Payer: {event.payer_name} ({event.plan_type})")
        context_parts.append(f"Prior Auth Required: {event.prior_auth_required}")
        context_parts.append(f"Prior Auth Number: {event.prior_auth_number or 'NOT PROVIDED'}")

        # Add codes
        if extract_output:
            context_parts.append("\n## CLINICAL CODES")
            context_parts.append(f"Diagnosis Codes: {', '.join(extract_output.diagnosis_codes or [])}")
            context_parts.append(f"Diagnosis Descriptions: {', '.join(extract_output.diagnosis_descriptions or [])}")
            context_parts.append(f"Procedure Codes: {', '.join(extract_output.procedure_codes or [])}")
            context_parts.append(f"Procedure Descriptions: {', '.join(extract_output.procedure_descriptions or [])}")
            if extract_output.code_issues or []:
                context_parts.append(f"Code Issues: {', '.join(extract_output.code_issues or [])}")

        # Add rule-based risks
        if analyze_output and (analyze_output.rule_based_risks or []):
            context_parts.append("\n## RULE-BASED RISK FACTORS")
            for risk in analyze_output.rule_based_risks or []:
                context_parts.append(f"- {risk}")

        # Add similar denial patterns from RAG
        if rag_output and (rag_output.similar_denials or []):
            context_parts.append("\n## SIMILAR DENIAL PATTERNS FROM KNOWLEDGE BASE")
            for i, denial in enumerate(rag_output.similar_denials or [][:3], 1):
                context_parts.append(f"\n### Pattern {i} (Similarity: {denial.get('similarity', 0):.2f})")
                context_parts.append(f"Category: {denial.get('category')}")
                context_parts.append(f"Reason: {denial.get('denial_reason')}")
                context_parts.append(f"CARC Code: {denial.get('carc_code')}")
                context_parts.append(f"Historical Success Rate if Fixed: {denial.get('success_rate', 'N/A')}")
                if denial.get('remediation'):
                    context_parts.append(f"Remediation: {denial.get('remediation')}")

        # Add clinical notes if available
        if event.clinical_notes_summary:
            context_parts.append("\n## CLINICAL NOTES SUMMARY")
            context_parts.append(event.clinical_notes_summary)

        # Build user prompt
        user_prompt = "\n".join(context_parts)
        user_prompt += "\n\n## TASK"
        user_prompt += "\nAnalyze this claim and provide a denial risk assessment."

        # Run the agent
        result = await self.agent.run(user_prompt=user_prompt)
        self.save_output(result.output)

        return task_context
