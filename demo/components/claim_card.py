"""Reusable claim summary card component."""

import streamlit as st


def render_claim_card(claim: dict):
    """Render a compact claim summary."""
    with st.container(border=True):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown(f"**Patient:** Age {claim.get('patient_age', 'N/A')}, {claim.get('patient_gender', 'N/A')}")
            st.markdown(f"**Provider:** {claim.get('provider_name', 'N/A')}")
            st.markdown(f"**Facility:** {claim.get('facility_type', 'N/A')}")

        with col2:
            st.markdown(f"**Payer:** {claim.get('payer_name', 'N/A')} ({claim.get('plan_type', '')})")
            amount = claim.get("billed_amount", 0)
            st.markdown(f"**Billed Amount:** ${float(amount):,.2f}")
            auth_required = claim.get("prior_auth_required", False)
            auth_number = claim.get("prior_auth_number")
            if auth_required:
                if auth_number:
                    st.markdown(f"**Prior Auth:** {auth_number}")
                else:
                    st.markdown("**Prior Auth:** :red[REQUIRED - NOT PROVIDED]")

        # Codes
        diag_codes = claim.get("diagnosis_codes", [])
        proc_codes = claim.get("procedure_codes", [])

        if proc_codes:
            procs = ", ".join(
                f"`{p.get('code', '')}` {p.get('display', '')}" for p in proc_codes
            )
            st.markdown(f"**Procedures:** {procs}")

        if diag_codes:
            diags = ", ".join(
                f"`{d.get('code', '')}` {d.get('display', '')}" for d in diag_codes
            )
            st.markdown(f"**Diagnoses:** {diags}")

        # Risk factors (if test claim)
        risk_factors = claim.get("risk_factors", [])
        if risk_factors:
            st.markdown(
                f"**Known Risk Factors:** {', '.join(f'`{r}`' for r in risk_factors)}"
            )
