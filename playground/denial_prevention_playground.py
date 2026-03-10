"""
Denial Prevention Playground

This notebook demonstrates how to use the denial prevention system:
1. Load a test claim
2. Run the ClaimReviewWorkflow
3. See the risk assessment and recommendations

Prerequisites:
1. Docker containers running (db, redis)
2. Database migrations applied
3. Denial knowledge base seeded (run seed_denial_knowledge.py)

Usage:
    cd /path/to/genai-launchpad
    python playground/denial_prevention_playground.py
"""

import json
import logging
import sys
from pathlib import Path

# Set up paths
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "app"))

from dotenv import load_dotenv

# Load environment variables
env_path = PROJECT_ROOT / "app" / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    env_path = PROJECT_ROOT / "docker" / ".env"
    load_dotenv(env_path)

import nest_asyncio
nest_asyncio.apply()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Now import app modules
from workflows.claim_review_workflow import ClaimReviewWorkflow
from workflows.denial_learning_workflow import DenialLearningWorkflow


def load_test_claim(claim_type: str = "at_risk") -> dict:
    """Load a test claim from the generated data.

    Args:
        claim_type: "at_risk" for high-risk claims, "normal" for regular claims

    Returns:
        Claim dictionary
    """
    if claim_type == "at_risk":
        claims_dir = PROJECT_ROOT / "requests" / "denial_prevention" / "at_risk_claims"
        # Load the first at-risk claim (missing prior auth)
        claim_file = claims_dir / "at_risk_001_prior_authorization.json"
    else:
        claims_dir = PROJECT_ROOT / "requests" / "denial_prevention" / "claims"
        claim_file = claims_dir / "claim_001.json"

    with open(claim_file, 'r') as f:
        return json.load(f)


def format_risk_assessment(result) -> str:
    """Format the risk assessment output for display."""
    nodes = result.nodes
    output = []

    output.append("=" * 60)
    output.append("DENIAL RISK ASSESSMENT RESULTS")
    output.append("=" * 60)

    # Risk Assessment
    if "RiskAssessmentNode" in nodes:
        risk = nodes["RiskAssessmentNode"]
        output.append(f"\nRISK LEVEL: {risk.risk_level.value.upper()}")
        output.append(f"Denial Probability: {risk.denial_probability:.0%}")
        output.append(f"Confidence: {risk.confidence:.0%}")
        output.append(f"\nPrimary Risk Factors:")
        for factor in risk.primary_risk_factors:
            output.append(f"  - {factor}")
        output.append(f"\nLikely Denial Categories:")
        for cat in risk.likely_denial_categories:
            output.append(f"  - {cat}")
        output.append(f"\nReasoning:")
        output.append(f"  {risk.reasoning}")

    # Terminal Node Output
    if "ApproveClaimNode" in nodes:
        output.append("\n" + "-" * 40)
        output.append("STATUS: APPROVED")
        output.append(nodes["ApproveClaimNode"].message)

    elif "EscalateClaimNode" in nodes:
        escalate = nodes["EscalateClaimNode"]
        output.append("\n" + "-" * 40)
        output.append("STATUS: ESCALATED")
        output.append(f"Urgency: {escalate.urgency.upper()}")
        output.append(f"\n{escalate.message}")
        output.append(f"\nRecommendation: {escalate.recommendation}")

    elif "GenerateFeedbackNode" in nodes:
        feedback = nodes["GenerateFeedbackNode"]
        output.append("\n" + "-" * 40)
        output.append("STATUS: REQUIRES ATTENTION")
        output.append(f"\nSummary: {feedback.summary}")
        output.append(f"\nRecommendations:")
        for rec in feedback.recommendations:
            output.append(f"  [{rec.priority.upper()}] {rec.issue}")
            output.append(f"    Action: {rec.action}")
        if feedback.required_documentation:
            output.append(f"\nRequired Documentation:")
            for doc in feedback.required_documentation:
                output.append(f"  - {doc}")
        if feedback.suggested_code_changes:
            output.append(f"\nSuggested Code Changes:")
            for change in feedback.suggested_code_changes:
                output.append(f"  - {change}")
        output.append(f"\nNext Steps: {feedback.next_steps}")

    output.append("\n" + "=" * 60)
    return "\n".join(output)


def test_claim_review(claim_type: str = "at_risk"):
    """Test the claim review workflow."""
    print("\n" + "=" * 60)
    print(f"TESTING CLAIM REVIEW WORKFLOW ({claim_type.upper()} CLAIM)")
    print("=" * 60)

    # Load test claim
    claim = load_test_claim(claim_type)
    print(f"\nLoaded claim:")
    print(f"  Procedure: {claim.get('procedure_codes', [{}])[0].get('display', 'N/A')}")
    print(f"  Billed Amount: ${claim.get('billed_amount', 0):,.2f}")
    print(f"  Payer: {claim.get('payer_name', 'N/A')}")
    print(f"  Prior Auth Required: {claim.get('prior_auth_required', False)}")
    print(f"  Prior Auth Number: {claim.get('prior_auth_number', 'NOT PROVIDED')}")

    if claim.get('risk_factors'):
        print(f"  Known Risk Factors: {', '.join(claim.get('risk_factors', []))}")

    # Run workflow
    print("\nRunning ClaimReviewWorkflow...")
    workflow = ClaimReviewWorkflow(enable_tracing=True)

    try:
        result = workflow.run(claim)
        print("\nWorkflow completed!")
        print(format_risk_assessment(result))
    except Exception as e:
        print(f"\nError running workflow: {e}")
        import traceback
        traceback.print_exc()


def test_multiple_claims():
    """Test multiple claims to see different risk levels."""
    print("\n" + "=" * 60)
    print("TESTING MULTIPLE CLAIMS")
    print("=" * 60)

    claims_dir = PROJECT_ROOT / "requests" / "denial_prevention" / "at_risk_claims"
    claim_files = sorted(claims_dir.glob("at_risk_*.json"))[:5]  # Test first 5

    workflow = ClaimReviewWorkflow(enable_tracing=False)  # Disable tracing for speed

    for claim_file in claim_files:
        with open(claim_file, 'r') as f:
            claim = json.load(f)

        print(f"\n--- {claim_file.name} ---")
        print(f"Expected: {claim.get('expected_denial_category', 'N/A')}")

        try:
            result = workflow.run(claim)
            if "RiskAssessmentNode" in result.nodes:
                risk = result.nodes["RiskAssessmentNode"]
                print(f"Assessed: {risk.risk_level.value} ({risk.denial_probability:.0%})")
                print(f"Categories: {', '.join(risk.likely_denial_categories[:2])}")
        except Exception as e:
            print(f"Error: {e}")


def main():
    print("=" * 60)
    print("DENIAL PREVENTION SYSTEM - PLAYGROUND")
    print("=" * 60)

    print("\nThis playground demonstrates the denial prevention workflows.")
    print("Make sure you have:")
    print("  1. Docker containers running (docker-compose up)")
    print("  2. Database migrations applied (alembic upgrade head)")
    print("  3. Knowledge base seeded (python playground/data_prep/seed_denial_knowledge.py)")

    print("\n" + "-" * 60)
    print("TEST 1: High-Risk Claim (Missing Prior Authorization)")
    print("-" * 60)
    test_claim_review("at_risk")

    # Uncomment to test a normal claim:
    # print("\n" + "-" * 60)
    # print("TEST 2: Normal Claim")
    # print("-" * 60)
    # test_claim_review("normal")

    # Uncomment to test multiple claims:
    # print("\n" + "-" * 60)
    # print("TEST 3: Multiple Claims")
    # print("-" * 60)
    # test_multiple_claims()


if __name__ == "__main__":
    main()
