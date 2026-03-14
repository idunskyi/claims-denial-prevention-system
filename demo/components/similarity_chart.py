"""Similarity results visualization."""

import streamlit as st
import pandas as pd


def render_similarity_results(similar_denials: list[dict]):
    """Render similarity search results as a styled table with bars."""
    if not similar_denials:
        st.info("No results found.")
        return

    rows = []
    for d in similar_denials:
        rows.append({
            "Similarity": d.get("similarity", 0),
            "Category": d.get("category", "").replace("_", " ").title(),
            "CARC": d.get("carc_code", ""),
            "Denial Reason": d.get("denial_reason", "")[:80],
            "Success Rate": d.get("success_rate", 0) or 0,
        })

    df = pd.DataFrame(rows)

    st.dataframe(
        df.style.bar(subset=["Similarity"], color="#5fba7d", vmin=0, vmax=1)
        .bar(subset=["Success Rate"], color="#4a90d9", vmin=0, vmax=1)
        .format({"Similarity": "{:.0%}", "Success Rate": "{:.0%}"}),
        use_container_width=True,
        hide_index=True,
    )
