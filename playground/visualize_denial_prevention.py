"""
Visualize Denial Prevention Workflows

This script generates visual diagrams of the denial prevention workflows,
similar to visualize_workflow.py but customized for the denial prevention system.

Usage:
    cd /path/to/genai-launchpad
    python playground/visualize_denial_prevention.py

Outputs:
    - playground/claim_review_workflow.png
    - playground/denial_learning_workflow.png
"""

import sys
from pathlib import Path

# Set up paths
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "app"))

from dotenv import load_dotenv
env_path = PROJECT_ROOT / "app" / ".env"
if env_path.exists():
    load_dotenv(env_path)

from graphviz import Digraph


def visualize_claim_review_workflow():
    """Generate visualization for ClaimReviewWorkflow."""
    dot = Digraph(comment="Claim Review Workflow")

    # Graph settings
    dot.attr(
        rankdir="LR",
        bgcolor="#ffffff",
        fontname="Helvetica,Arial,sans-serif",
        pad="0.5",
        nodesep="0.5",
        ranksep="0.75",
    )

    # Node defaults
    dot.attr(
        "node",
        shape="rectangle",
        style="filled",
        fillcolor="#ececfd",
        color="#8e71d5",
        fontcolor="#333333",
        fontname="Helvetica",
        fontsize="12",
        height="0.6",
        width="2.0",
        penwidth="2",
    )

    # Edge defaults
    dot.attr(
        "edge",
        color="#333333",
        penwidth="2",
        arrowsize="0.8",
        fontname="Helvetica",
        fontsize="10",
    )

    # Event node (ellipse)
    dot.node("Event", "Claim\nEvent", shape="ellipse", fillcolor="#e8f5e9")

    # Processing nodes
    dot.node("AnalyzeClaimNode", "AnalyzeClaimNode\n(Concurrent)")
    dot.node("ExtractCodesNode", "ExtractCodesNode", fillcolor="#fff9c4")
    dot.node("RAGRetrievalNode", "RAGRetrievalNode\n(Vector Search)")
    dot.node("RiskAssessmentNode", "RiskAssessmentNode\n(AI Agent)")

    # Router node (diamond)
    dot.node(
        "DenialRiskRouter",
        "DenialRiskRouter",
        shape="diamond",
        fillcolor="#e3f2fd",
    )

    # Terminal nodes with different colors based on risk
    dot.node("ApproveClaimNode", "ApproveClaimNode\n(Low Risk)", fillcolor="#c8e6c9")  # Green
    dot.node("GenerateFeedbackNode", "GenerateFeedbackNode\n(Medium Risk)", fillcolor="#fff59d")  # Yellow
    dot.node("EscalateClaimNode", "EscalateClaimNode\n(High Risk)", fillcolor="#ffcdd2")  # Red

    # Edges
    dot.edge("Event", "AnalyzeClaimNode")
    dot.edge("AnalyzeClaimNode", "ExtractCodesNode", style="dashed", label="concurrent")
    dot.edge("AnalyzeClaimNode", "RAGRetrievalNode")
    dot.edge("RAGRetrievalNode", "RiskAssessmentNode")
    dot.edge("RiskAssessmentNode", "DenialRiskRouter")

    # Router edges
    dot.edge("DenialRiskRouter", "ApproveClaimNode", label="LOW")
    dot.edge("DenialRiskRouter", "GenerateFeedbackNode", label="MEDIUM")
    dot.edge("DenialRiskRouter", "EscalateClaimNode", label="HIGH")

    # Render
    output_path = PROJECT_ROOT / "playground" / "claim_review_workflow"
    dot.render(output_path, format="png", cleanup=True)
    print(f"Generated: {output_path}.png")

    return dot


def visualize_denial_learning_workflow():
    """Generate visualization for DenialLearningWorkflow."""
    dot = Digraph(comment="Denial Learning Workflow")

    # Graph settings
    dot.attr(
        rankdir="LR",
        bgcolor="#ffffff",
        fontname="Helvetica,Arial,sans-serif",
        pad="0.5",
        nodesep="0.5",
        ranksep="0.75",
    )

    # Node defaults
    dot.attr(
        "node",
        shape="rectangle",
        style="filled",
        fillcolor="#ececfd",
        color="#8e71d5",
        fontcolor="#333333",
        fontname="Helvetica",
        fontsize="12",
        height="0.6",
        width="2.0",
        penwidth="2",
    )

    # Edge defaults
    dot.attr(
        "edge",
        color="#333333",
        penwidth="2",
        arrowsize="0.8",
        fontname="Helvetica",
        fontsize="10",
    )

    # Event node (ellipse)
    dot.node("Event", "Denial\nNotification", shape="ellipse", fillcolor="#ffcdd2")

    # Processing nodes
    dot.node("AnalyzeDenialNode", "AnalyzeDenialNode\n(AI Agent)")
    dot.node("StoreInRAGNode", "StoreInRAGNode\n(Vector Store)", fillcolor="#c8e6c9")

    # Knowledge base (cylinder)
    dot.node(
        "KnowledgeBase",
        "Denial\nKnowledge Base\n(pgvector)",
        shape="cylinder",
        fillcolor="#e3f2fd",
    )

    # Edges
    dot.edge("Event", "AnalyzeDenialNode")
    dot.edge("AnalyzeDenialNode", "StoreInRAGNode")
    dot.edge("StoreInRAGNode", "KnowledgeBase", style="dashed")

    # Render
    output_path = PROJECT_ROOT / "playground" / "denial_learning_workflow"
    dot.render(output_path, format="png", cleanup=True)
    print(f"Generated: {output_path}.png")

    return dot


def visualize_system_overview():
    """Generate a system overview diagram showing both workflows."""
    dot = Digraph(comment="Denial Prevention System Overview")

    # Graph settings
    dot.attr(
        rankdir="TB",
        bgcolor="#ffffff",
        fontname="Helvetica,Arial,sans-serif",
        pad="1.0",
        nodesep="0.75",
        ranksep="1.0",
        compound="true",
    )

    # Create subgraph for Claim Review
    with dot.subgraph(name="cluster_claim_review") as c:
        c.attr(
            label="Claim Review Workflow\n(Proactive Prevention)",
            style="rounded,filled",
            fillcolor="#f3e5f5",
            color="#9c27b0",
        )
        c.node("CR_Event", "New Claim", shape="ellipse", fillcolor="#e8f5e9")
        c.node("CR_Analyze", "Analyze &\nExtract Codes", fillcolor="#ececfd")
        c.node("CR_RAG", "RAG Retrieval", fillcolor="#ececfd")
        c.node("CR_Risk", "Risk Assessment\n(AI)", fillcolor="#ececfd")
        c.node("CR_Route", "Route by Risk", shape="diamond", fillcolor="#e3f2fd")
        c.node("CR_Low", "Approve", fillcolor="#c8e6c9")
        c.node("CR_Med", "Feedback", fillcolor="#fff59d")
        c.node("CR_High", "Escalate", fillcolor="#ffcdd2")

    # Create subgraph for Denial Learning
    with dot.subgraph(name="cluster_denial_learning") as c:
        c.attr(
            label="Denial Learning Workflow\n(Continuous Improvement)",
            style="rounded,filled",
            fillcolor="#fff3e0",
            color="#ff9800",
        )
        c.node("DL_Event", "Denial\nNotification", shape="ellipse", fillcolor="#ffcdd2")
        c.node("DL_Analyze", "Analyze\nPattern (AI)", fillcolor="#ececfd")
        c.node("DL_Store", "Store in\nKnowledge Base", fillcolor="#c8e6c9")

    # Knowledge Base (shared)
    dot.node(
        "KB",
        "Denial Knowledge Base\n(PostgreSQL + pgvector)\n\n- Denial patterns\n- Remediation strategies\n- Vector embeddings",
        shape="cylinder",
        fillcolor="#e3f2fd",
        style="filled",
        height="1.5",
        width="2.5",
    )

    # Claim Review edges
    dot.edge("CR_Event", "CR_Analyze")
    dot.edge("CR_Analyze", "CR_RAG")
    dot.edge("CR_RAG", "CR_Risk")
    dot.edge("CR_Risk", "CR_Route")
    dot.edge("CR_Route", "CR_Low", label="low")
    dot.edge("CR_Route", "CR_Med", label="med")
    dot.edge("CR_Route", "CR_High", label="high")

    # Denial Learning edges
    dot.edge("DL_Event", "DL_Analyze")
    dot.edge("DL_Analyze", "DL_Store")

    # Connections to Knowledge Base
    dot.edge("CR_RAG", "KB", style="dashed", label="query")
    dot.edge("DL_Store", "KB", style="dashed", label="store")

    # Render
    output_path = PROJECT_ROOT / "playground" / "denial_prevention_system"
    dot.render(output_path, format="png", cleanup=True)
    print(f"Generated: {output_path}.png")

    return dot


def main():
    print("Generating Denial Prevention Workflow Visualizations...")
    print("=" * 50)

    try:
        visualize_claim_review_workflow()
        visualize_denial_learning_workflow()
        visualize_system_overview()
        print("=" * 50)
        print("All visualizations generated successfully!")
    except Exception as e:
        print(f"Error generating visualizations: {e}")
        print("Make sure graphviz is installed: pip install graphviz")
        print("And the system graphviz package: brew install graphviz (Mac)")


if __name__ == "__main__":
    main()
