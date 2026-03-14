"""
Learning Loop Page

Demonstrates the system learning from denials in real-time:
1. Run a baseline claim review
2. Submit a denial for learning
3. Re-review the same claim and compare results
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "app"))
sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from services.denial_prevention_service import DenialPreventionService
from demo.components.claim_card import render_claim_card
from demo.components.risk_display import render_risk_badge, render_status_badge
from demo.components.workflow_steps import render_workflow_steps

st.set_page_config(page_title="Learning Loop", page_icon="\U0001f9e0", layout="wide")


@st.cache_resource
def get_service():
    return DenialPreventionService(enable_tracing=False)


service = get_service()

st.title("\U0001f9e0 Learning Loop Demo")
st.markdown(
    "See the system learn in real-time: run a baseline, teach it a new pattern, "
    "then re-review to see improved predictions."
)

# Initialize session state
for key in ("baseline_result", "learning_result", "rerun_result", "loop_claim"):
    if key not in st.session_state:
        st.session_state[key] = None

# ── Step 1: Baseline Review ─────────────────────────────────

st.header("Step 1: Baseline Claim Review")

claims = service.list_test_claims(category="at_risk")
if not claims:
    st.warning("No test claims found.")
    st.stop()

claim_labels = {}
for c in claims:
    label = f"{c['filename']} - ${float(c.get('billed_amount', 0)):,.0f}"
    if c.get("expected_denial_category"):
        label += f" ({c['expected_denial_category']})"
    claim_labels[c["filename"]] = label

selected_file = st.selectbox(
    "Select a claim for the learning loop",
    options=list(claim_labels.keys()),
    format_func=lambda x: claim_labels[x],
)

claim = service.load_claim(selected_file)
render_claim_card(claim)

if st.button("\U0001f680 Run Baseline Review", type="primary"):
    with st.spinner("Running baseline review..."):
        try:
            result = service.review_claim(claim)
            st.session_state["baseline_result"] = result
            st.session_state["loop_claim"] = selected_file
            # Clear downstream results when baseline changes
            st.session_state["learning_result"] = None
            st.session_state["rerun_result"] = None
        except Exception as e:
            st.error(f"Error: {e}")

baseline = st.session_state.get("baseline_result")
if baseline:
    with st.expander("Baseline Results", expanded=True):
        render_status_badge(baseline["status"])
        risk = baseline.get("steps", {}).get("risk_assessment", {})
        if risk:
            render_risk_badge(
                risk.get("risk_level", "unknown"),
                risk.get("denial_probability", 0),
                risk.get("confidence"),
            )
        rag = baseline.get("steps", {}).get("rag_retrieval", {})
        if rag:
            st.metric("Similar Patterns Found", rag.get("num_results", 0))

    st.divider()

    # ── Step 2: Teach the System ─────────────────────────────

    st.header("Step 2: Teach the System a New Denial Pattern")
    st.markdown(
        "Submit a denial notification for the system to learn from. "
        "This will analyze the denial, extract patterns, and store them in the knowledge base."
    )

    templates = service.list_denial_templates()
    if not templates:
        st.warning("No denial templates found.")
        st.stop()

    template_labels = {
        t["category"]: f"{t['category'].replace('_', ' ').title()} ({t['count']} patterns)"
        for t in templates
    }

    selected_category = st.selectbox(
        "Select denial category to learn from",
        options=list(template_labels.keys()),
        format_func=lambda x: template_labels[x],
    )

    denial_entries = service.load_denial_template(selected_category)

    if denial_entries:
        # Pick first entry for simplicity
        denial = denial_entries[0] if isinstance(denial_entries, list) else denial_entries

        with st.expander("Denial data to submit"):
            st.json(denial)

        if st.button("\U0001f9e0 Submit Denial for Learning", type="primary"):
            with st.spinner("Processing denial... Analyzing patterns and storing in knowledge base..."):
                try:
                    result = service.learn_from_denial(denial)
                    st.session_state["learning_result"] = result
                    st.session_state["rerun_result"] = None
                except Exception as e:
                    st.error(f"Error: {e}")

    learning = st.session_state.get("learning_result")
    if learning:
        with st.expander("Learning Results", expanded=True):
            if learning.get("stored"):
                st.success("Pattern successfully stored in knowledge base!")
            else:
                st.warning("Pattern was not stored.")

            analyze = learning.get("steps", {}).get("analyze_denial", {})
            if analyze:
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Category:** {analyze.get('confirmed_category', '')}")
                    st.markdown(f"**Pattern:** {analyze.get('denial_pattern_summary', '')}")
                    st.markdown(
                        f"**Success Rate:** {analyze.get('estimated_success_rate', 0):.0%}"
                    )
                with col2:
                    if analyze.get("recommended_remediation"):
                        st.info(f"**Remediation:** {analyze['recommended_remediation']}")

                triggers = analyze.get("trigger_characteristics", [])
                if triggers:
                    st.markdown(
                        "**Trigger Characteristics:** "
                        + ", ".join(f"`{t}`" for t in triggers)
                    )

            store = learning.get("steps", {}).get("store_in_rag", {})
            if store:
                st.caption(f"Knowledge ID: {store.get('knowledge_id', 'N/A')}")

        st.divider()

        # ── Step 3: Re-Review ────────────────────────────────

        st.header("Step 3: Re-Review the Same Claim")
        st.markdown(
            "Run the same claim through the review workflow again. "
            "The knowledge base now contains the new pattern -- "
            "see how RAG retrieval and risk assessment change."
        )

        loop_file = st.session_state.get("loop_claim", selected_file)

        if st.button("\U0001f504 Re-Review Claim", type="primary"):
            rerun_claim = service.load_claim(loop_file)
            with st.spinner("Re-running review with updated knowledge base..."):
                try:
                    result = service.review_claim(rerun_claim)
                    st.session_state["rerun_result"] = result
                except Exception as e:
                    st.error(f"Error: {e}")

        rerun = st.session_state.get("rerun_result")
        if rerun:
            st.subheader("Before vs After Comparison")

            col_before, col_after = st.columns(2)

            with col_before:
                st.markdown("### Before Learning")
                render_status_badge(baseline["status"])
                b_risk = baseline.get("steps", {}).get("risk_assessment", {})
                if b_risk:
                    st.metric("Denial Probability", f"{b_risk.get('denial_probability', 0):.0%}")
                    st.metric("Risk Level", b_risk.get("risk_level", "unknown").upper())
                b_rag = baseline.get("steps", {}).get("rag_retrieval", {})
                if b_rag:
                    st.metric("RAG Matches", b_rag.get("num_results", 0))
                    st.metric("Avg Similarity", f"{b_rag.get('average_similarity', 0):.2f}")

            with col_after:
                st.markdown("### After Learning")
                render_status_badge(rerun["status"])
                a_risk = rerun.get("steps", {}).get("risk_assessment", {})
                if a_risk:
                    b_prob = b_risk.get("denial_probability", 0) if b_risk else 0
                    a_prob = a_risk.get("denial_probability", 0)
                    delta = a_prob - b_prob
                    delta_str = f"{delta:+.0%}" if delta != 0 else None
                    st.metric(
                        "Denial Probability",
                        f"{a_prob:.0%}",
                        delta=delta_str,
                        delta_color="inverse",
                    )
                    st.metric("Risk Level", a_risk.get("risk_level", "unknown").upper())
                a_rag = rerun.get("steps", {}).get("rag_retrieval", {})
                if a_rag:
                    b_matches = b_rag.get("num_results", 0) if b_rag else 0
                    a_matches = a_rag.get("num_results", 0)
                    st.metric(
                        "RAG Matches",
                        a_matches,
                        delta=a_matches - b_matches if a_matches != b_matches else None,
                    )
                    st.metric(
                        "Avg Similarity",
                        f"{a_rag.get('average_similarity', 0):.2f}",
                    )

            st.divider()
            st.subheader("Full Re-Review Results")
            render_workflow_steps(rerun.get("steps", {}))
