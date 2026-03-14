"""Risk level display components."""

import streamlit as st


def render_risk_badge(risk_level: str, denial_probability: float, confidence: float = None):
    """Render a color-coded risk level indicator with probability."""
    color_map = {
        "low": ("green", "\u2705"),
        "medium": ("orange", "\u26a0\ufe0f"),
        "high": ("red", "\u274c"),
    }
    color, icon = color_map.get(risk_level, ("gray", "\u2753"))

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            label="Risk Level",
            value=f"{icon} {risk_level.upper()}",
        )
    with col2:
        st.metric(
            label="Denial Probability",
            value=f"{denial_probability:.0%}",
        )
    if confidence is not None:
        with col3:
            st.metric(
                label="Confidence",
                value=f"{confidence:.0%}",
            )

    # Progress bar with color
    st.progress(min(denial_probability, 1.0))


def render_status_badge(status: str):
    """Render the final decision status."""
    status_map = {
        "approved": ("\u2705 APPROVED", "success"),
        "needs_attention": ("\u26a0\ufe0f NEEDS ATTENTION", "warning"),
        "escalated": ("\u274c ESCALATED", "error"),
    }

    label, msg_type = status_map.get(status, (status.upper(), "info"))
    getattr(st, msg_type)(label)
