"""
Knowledge Base Explorer Page

Browse and search the denial pattern knowledge base.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "app"))
sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
import pandas as pd

from services.denial_prevention_service import DenialPreventionService
from demo.components.similarity_chart import render_similarity_results

st.set_page_config(page_title="Knowledge Base", page_icon="\U0001f4da", layout="wide")


@st.cache_resource
def get_service():
    return DenialPreventionService(enable_tracing=False)


service = get_service()

st.title("\U0001f4da Knowledge Base Explorer")
st.markdown("Browse and search the denial pattern knowledge base powered by pgvector.")

# ── Stats ────────────────────────────────────────────────────

stats = service.get_knowledge_base_stats()

cols = st.columns(4)
cols[0].metric("Total Patterns", stats["total_entries"])
cols[1].metric("Categories", len(stats["categories"]))

# Top 2 categories
sorted_cats = sorted(stats["categories"].items(), key=lambda x: x[1], reverse=True)
if len(sorted_cats) > 0:
    cols[2].metric(
        f"Top: {sorted_cats[0][0].replace('_', ' ').title()}",
        sorted_cats[0][1],
    )
if len(sorted_cats) > 1:
    cols[3].metric(
        f"2nd: {sorted_cats[1][0].replace('_', ' ').title()}",
        sorted_cats[1][1],
    )

st.divider()

# ── Tabs: Browse vs Search ───────────────────────────────────

tab_browse, tab_search = st.tabs(["Browse by Category", "Semantic Search"])

with tab_browse:
    categories = ["All"] + [
        cat for cat, _ in sorted_cats
    ]

    selected_cat = st.selectbox(
        "Filter by category",
        categories,
        format_func=lambda x: x.replace("_", " ").title(),
    )

    cat_filter = None if selected_cat == "All" else selected_cat
    entries = service.get_knowledge_entries(category=cat_filter)

    if entries:
        st.markdown(f"**{len(entries)} entries**")

        for entry in entries:
            with st.expander(
                f"**{entry.get('category', '').replace('_', ' ').title()}** -- "
                f"CARC {entry.get('carc_code', 'N/A')} -- "
                f"{entry.get('denial_reason', '')[:60]}..."
            ):
                col1, col2 = st.columns(2)

                with col1:
                    st.markdown(f"**Category:** {entry.get('category', '')}")
                    st.markdown(f"**CARC Code:** {entry.get('carc_code', 'N/A')}")
                    st.markdown(f"**Denial Reason:** {entry.get('denial_reason', '')}")

                    success = entry.get("success_rate")
                    if success:
                        st.markdown(f"**Appeal Success Rate:** {success:.0%}")

                    payers = entry.get("typical_payers", [])
                    if payers:
                        st.markdown(f"**Typical Payers:** {', '.join(payers)}")

                with col2:
                    if entry.get("remediation"):
                        st.markdown("**Remediation Strategy:**")
                        st.info(entry["remediation"])

                    if entry.get("appeal_template"):
                        st.markdown("**Appeal Template:**")
                        st.code(entry["appeal_template"], language=None)

                trigger = entry.get("trigger_patterns")
                if trigger:
                    st.markdown("**Trigger Patterns:**")
                    st.json(trigger)
    else:
        st.info("No entries found.")

with tab_search:
    st.markdown(
        "Search the knowledge base using natural language. "
        "The query is converted to an embedding and matched against stored patterns."
    )

    query = st.text_input(
        "Search query",
        placeholder="e.g., Missing prior authorization for surgical procedure",
    )
    top_k = st.slider("Number of results", min_value=1, max_value=20, value=5)

    if query:
        with st.spinner("Searching..."):
            results = service.search_knowledge_base(query, top_k=top_k)

        if results:
            st.markdown(f"**{len(results)} results:**")
            render_similarity_results(results)

            st.divider()

            # Detailed view
            for i, r in enumerate(results, 1):
                with st.expander(
                    f"#{i} ({r.get('similarity', 0):.0%}) -- "
                    f"{r.get('category', '').replace('_', ' ').title()} -- "
                    f"{r.get('denial_reason', '')[:60]}..."
                ):
                    st.markdown(f"**Denial Reason:** {r.get('denial_reason', '')}")
                    if r.get("remediation"):
                        st.info(f"**Remediation:** {r['remediation']}")
                    if r.get("carc_code"):
                        st.markdown(f"**CARC Code:** {r['carc_code']}")
                    if r.get("success_rate"):
                        st.markdown(f"**Success Rate:** {r['success_rate']:.0%}")
        else:
            st.warning("No matching patterns found.")
