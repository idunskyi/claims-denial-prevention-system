"""
Claim Review Page

The main demo page. Select a test claim, run the review workflow,
and see step-by-step results.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "app"))
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

env_path = PROJECT_ROOT / "app" / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv(PROJECT_ROOT / "docker" / ".env")

import nest_asyncio

nest_asyncio.apply()

import streamlit as st

from services.denial_prevention_service import DenialPreventionService
from demo.components.claim_card import render_claim_card
from demo.components.workflow_steps import render_workflow_steps
from demo.components.risk_display import render_status_badge

st.set_page_config(page_title="Claim Review", page_icon="\U0001f50d", layout="wide")


@st.cache_resource
def get_service():
    return DenialPreventionService(enable_tracing=False)


service = get_service()

st.title("\U0001f50d Claim Review")
st.markdown(
    "Select a claim and run the denial prevention workflow to see the full analysis pipeline."
)

# ── Sidebar: Claim Selection ─────────────────────────────────

with st.sidebar:
    st.header("Select a Claim")

    category = st.radio(
        "Claim Category",
        ["at_risk", "normal"],
        format_func=lambda x: "At-Risk Claims" if x == "at_risk" else "Normal Claims",
    )

    claims = service.list_test_claims(category=category)

    if not claims:
        st.warning("No test claims found.")
        st.stop()

    # Build display labels for dropdown
    claim_labels = {}
    for c in claims:
        proc = c.get("procedure_summary", "")[:40]
        label = f"{c['filename']} - ${float(c.get('billed_amount', 0)):,.0f}"
        if c.get("expected_denial_category"):
            label += f" ({c['expected_denial_category']})"
        claim_labels[c["filename"]] = label

    selected_file = st.selectbox(
        "Choose claim",
        options=list(claim_labels.keys()),
        format_func=lambda x: claim_labels[x],
    )

    # Load full claim
    claim = service.load_claim(selected_file)

    st.divider()
    st.subheader("Claim Details")
    render_claim_card(claim)

    run_review = st.button(
        "\U0001f680 Analyze Claim",
        type="primary",
        use_container_width=True,
    )

# ── Main Area: Results ───────────────────────────────────────

if run_review:
    with st.spinner("Running denial prevention workflow... This may take 15-30 seconds."):
        try:
            result = service.review_claim(claim)
            st.session_state["last_review_result"] = result
            st.session_state["last_reviewed_claim"] = selected_file
        except Exception as e:
            st.error(f"Workflow error: {e}")
            st.stop()

# Display results if available
result = st.session_state.get("last_review_result")

if result:
    reviewed_file = st.session_state.get("last_reviewed_claim", "")
    st.caption(f"Results for: **{reviewed_file}**")

    # Status banner
    render_status_badge(result["status"])

    st.divider()

    # Execution path
    st.markdown(
        "**Workflow Path:** "
        + " \u2192 ".join(f"`{node}`" for node in result.get("execution_path", []))
    )

    st.divider()

    # Step-by-step results
    render_workflow_steps(result.get("steps", {}))

else:
    st.info(
        "\U0001f448 Select a claim from the sidebar and click **Analyze Claim** to begin."
    )
