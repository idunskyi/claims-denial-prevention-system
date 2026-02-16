"""
Claim Review Workflow

This workflow provides proactive denial prevention by analyzing claims
before submission to identify potential issues.

Workflow Structure:
```
Event (Claim)
    │
    ▼
AnalyzeClaimNode (ConcurrentNode)
    ├── ExtractCodesNode (parallel)
    │
    ▼
RAGRetrievalNode
    │
    ▼
RiskAssessmentNode (AgentNode)
    │
    ▼
DenialRiskRouter
    ├── HIGH risk ──────► EscalateClaimNode
    ├── MEDIUM risk ────► GenerateFeedbackNode
    └── LOW risk ───────► ApproveClaimNode
```

Outputs:
- LOW risk: Claim approved, proceed with submission
- MEDIUM risk: Specific feedback on what to improve
- HIGH risk: Escalated for human review
"""

from core.schema import WorkflowSchema, NodeConfig
from core.workflow import Workflow
from schemas.claim_schema import ClaimEventSchema

from workflows.denial_prevention_workflow_nodes.analyze_claim_node import AnalyzeClaimNode
from workflows.denial_prevention_workflow_nodes.extract_codes_node import ExtractCodesNode
from workflows.denial_prevention_workflow_nodes.rag_retrieval_node import RAGRetrievalNode
from workflows.denial_prevention_workflow_nodes.risk_assessment_node import RiskAssessmentNode
from workflows.denial_prevention_workflow_nodes.denial_risk_router import DenialRiskRouter
from workflows.denial_prevention_workflow_nodes.generate_feedback_node import GenerateFeedbackNode
from workflows.denial_prevention_workflow_nodes.approve_claim_node import ApproveClaimNode
from workflows.denial_prevention_workflow_nodes.escalate_claim_node import EscalateClaimNode


class ClaimReviewWorkflow(Workflow):
    """Workflow for proactive claim denial prevention.

    This workflow analyzes incoming claims and predicts denial risk,
    providing feedback or escalation as appropriate.

    Usage:
        workflow = ClaimReviewWorkflow(enable_tracing=True)
        result = workflow.run(claim_data)

    The workflow uses RAG to find similar denial patterns and an LLM
    to synthesize the risk assessment.
    """

    workflow_schema = WorkflowSchema(
        description="Proactive denial prevention: Analyzes claims before submission to identify and prevent potential denials.",
        event_schema=ClaimEventSchema,
        start=AnalyzeClaimNode,
        nodes=[
            # Step 1: Concurrent analysis
            # Extracts codes and performs rule-based checks in parallel
            NodeConfig(
                node=AnalyzeClaimNode,
                connections=[RAGRetrievalNode],
                description="Concurrent claim analysis with code extraction and rule-based risk checks",
                concurrent_nodes=[
                    ExtractCodesNode,
                ],
            ),

            # Step 2: RAG retrieval
            # Finds similar denial patterns from the knowledge base
            NodeConfig(
                node=RAGRetrievalNode,
                connections=[RiskAssessmentNode],
                description="Retrieve similar denial patterns from knowledge base using vector similarity",
            ),

            # Step 3: Risk assessment
            # LLM analyzes all information and produces risk score
            NodeConfig(
                node=RiskAssessmentNode,
                connections=[DenialRiskRouter],
                description="AI-powered risk assessment synthesizing all analysis results",
            ),

            # Step 4: Routing
            # Routes to appropriate handler based on risk level
            NodeConfig(
                node=DenialRiskRouter,
                connections=[
                    ApproveClaimNode,
                    GenerateFeedbackNode,
                    EscalateClaimNode,
                ],
                description="Routes claims based on risk level",
                is_router=True,
            ),

            # Step 5a: Medium risk path
            # Generates specific recommendations
            NodeConfig(
                node=GenerateFeedbackNode,
                connections=[],  # Terminal node
                description="Generates actionable feedback for medium-risk claims",
            ),

            # Step 5b: Low risk path (terminal)
            NodeConfig(
                node=ApproveClaimNode,
                connections=[],  # Terminal node
                description="Approves low-risk claims for submission",
            ),

            # Step 5c: High risk path (terminal)
            NodeConfig(
                node=EscalateClaimNode,
                connections=[],  # Terminal node
                description="Escalates high-risk claims for human review",
            ),
        ],
    )
