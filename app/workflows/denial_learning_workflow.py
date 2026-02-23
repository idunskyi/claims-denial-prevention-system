"""
Denial Learning Workflow

This workflow processes denial notifications and stores the patterns
in the knowledge base for future prevention.

Workflow Structure:
```
Event (Denial Notification)
    │
    ▼
AnalyzeDenialNode (AgentNode)
    │
    ▼
StoreInRAGNode
    │
    ▼
(Complete - pattern stored)
```

This is the "learning" component of the denial prevention system.
Each denial processed makes the system smarter by adding patterns
that can be retrieved for future claims.

The workflow is typically triggered when:
1. A denial notification is received from the payer
2. A claim in the system is marked as denied
3. Historical denials are imported for training
"""

from core.schema import WorkflowSchema, NodeConfig
from core.workflow import Workflow
from schemas.denial_schema import DenialEventSchema

from workflows.denial_prevention_workflow_nodes.analyze_denial_node import AnalyzeDenialNode
from workflows.denial_prevention_workflow_nodes.store_in_rag_node import StoreInRAGNode


class DenialLearningWorkflow(Workflow):
    """Workflow for learning from denial notifications.

    This workflow analyzes denial notifications and stores the patterns
    in the vector knowledge base for future RAG retrieval.

    Usage:
        workflow = DenialLearningWorkflow(enable_tracing=True)
        result = workflow.run(denial_data)

    After processing, the denial pattern is available for similarity
    search when reviewing future claims.
    """

    workflow_schema = WorkflowSchema(
        description="Learn from denials: Analyzes denial notifications and stores patterns for future prevention.",
        event_schema=DenialEventSchema,
        start=AnalyzeDenialNode,
        nodes=[
            # Step 1: Analyze the denial
            # LLM extracts patterns and generates remediation suggestions
            NodeConfig(
                node=AnalyzeDenialNode,
                connections=[StoreInRAGNode],
                description="Analyze denial notification and extract patterns for learning",
            ),

            # Step 2: Store in knowledge base
            # Generates embedding and persists to PostgreSQL with pgvector
            NodeConfig(
                node=StoreInRAGNode,
                connections=[],  # Terminal node
                description="Store the analyzed pattern in the vector knowledge base",
            ),
        ],
    )
