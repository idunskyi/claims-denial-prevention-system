"""
Claims Denial Prevention System - Demo

Run:
    cd genai-launchpad
    streamlit run demo/Home.py
"""

import sys
from pathlib import Path

# Set up paths so app modules and demo components are importable
PROJECT_ROOT = Path(__file__).parent.parent
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
import pandas as pd

from services.denial_prevention_service import DenialPreventionService

st.set_page_config(
    page_title="Claims Denial Prevention",
    page_icon="\U0001f6e1\ufe0f",
    layout="wide",
)


@st.cache_resource
def get_service():
    return DenialPreventionService(enable_tracing=False)


service = get_service()

# ── Home Page ────────────────────────────────────────────────

st.title("\U0001f6e1\ufe0f Claims Denial Prevention System")

st.markdown(
    """
This system uses **AI-powered workflows** to prevent claim denials before they happen
and continuously learns from past denials to improve predictions.

**How it works:**
1. **Claim Review** -- Incoming claims are analyzed for denial risk using rule-based checks,
   vector similarity search against known denial patterns, and AI risk assessment.
2. **Learning Loop** -- When denials occur, the system extracts patterns and stores them
   as vector embeddings for future retrieval.
3. **Knowledge Base** -- A growing repository of denial patterns, remediation strategies,
   and appeal templates powered by pgvector.
"""
)

st.divider()

# Knowledge base stats
st.subheader("Knowledge Base Overview")

stats = service.get_knowledge_base_stats()

col1, col2, col3 = st.columns(3)
col1.metric("Total Denial Patterns", stats["total_entries"])
col2.metric("Categories Covered", len(stats["categories"]))

test_claims = service.list_test_claims()
col3.metric("Test Claims Available", len(test_claims))

if stats["categories"]:
    st.markdown("**Patterns by Category**")
    df = pd.DataFrame(
        [
            {"Category": cat.replace("_", " ").title(), "Count": count}
            for cat, count in sorted(
                stats["categories"].items(), key=lambda x: x[1], reverse=True
            )
        ]
    )
    st.bar_chart(df, x="Category", y="Count", horizontal=True)

st.divider()

# Navigation
st.subheader("Demo Pages")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### \U0001f50d Claim Review")
    st.markdown(
        "Submit a claim and see the full analysis pipeline: "
        "code extraction, RAG retrieval, AI risk assessment, and recommendations."
    )

with col2:
    st.markdown("### \U0001f9e0 Learning Loop")
    st.markdown(
        "See the system learn in real-time: run a baseline review, "
        "teach it a new denial pattern, then re-review to see improved predictions."
    )

with col3:
    st.markdown("### \U0001f4da Knowledge Base")
    st.markdown(
        "Browse and search the denial pattern knowledge base. "
        "See categories, CARC codes, remediation strategies, and similarity search."
    )
