"""Workflow step-by-step results display."""

import streamlit as st
import pandas as pd

from demo.components.risk_display import render_risk_badge, render_status_badge


def render_workflow_steps(steps: dict):
    """Render each workflow step as an expandable section."""

    # Step 1: Rule-Based Analysis
    if "analyze_claim" in steps:
        with st.expander("**Step 1:** Rule-Based Analysis", expanded=True):
            data = steps["analyze_claim"]
            risks = data.get("rule_based_risks", [])
            if risks:
                st.warning(f"Found {len(risks)} rule-based risk(s):")
                for risk in risks:
                    st.markdown(f"- `{risk}`")
            else:
                st.success("No rule-based risks detected.")

    # Step 2: Code Extraction
    if "extract_codes" in steps:
        with st.expander("**Step 2:** Code Extraction & Validation", expanded=True):
            data = steps["extract_codes"]

            col1, col2 = st.columns(2)
            with col1:
                dx_codes = data.get("diagnosis_codes", [])
                dx_descs = data.get("diagnosis_descriptions", [])
                if dx_codes:
                    st.markdown("**Diagnosis Codes (ICD-10)**")
                    rows = []
                    for i, code in enumerate(dx_codes):
                        desc = dx_descs[i] if i < len(dx_descs) else ""
                        rows.append({"Code": code, "Description": desc})
                    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
                else:
                    st.info("No diagnosis codes.")

            with col2:
                px_codes = data.get("procedure_codes", [])
                px_descs = data.get("procedure_descriptions", [])
                if px_codes:
                    st.markdown("**Procedure Codes (CPT/HCPCS)**")
                    rows = []
                    for i, code in enumerate(px_codes):
                        desc = px_descs[i] if i < len(px_descs) else ""
                        rows.append({"Code": code, "Description": desc})
                    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
                else:
                    st.info("No procedure codes.")

            issues = data.get("code_issues", [])
            if issues:
                st.error("**Code Issues Found:**")
                for issue in issues:
                    st.markdown(f"- {issue}")

    # Step 3: RAG Retrieval
    if "rag_retrieval" in steps:
        with st.expander("**Step 3:** Knowledge Base Retrieval (RAG)", expanded=True):
            data = steps["rag_retrieval"]

            col1, col2, col3 = st.columns(3)
            col1.metric("Similar Patterns Found", data.get("num_results", 0))
            col2.metric("Avg Similarity", f"{data.get('average_similarity', 0):.2f}")
            top_cats = data.get("top_categories", [])
            col3.metric("Top Category", top_cats[0] if top_cats else "N/A")

            if data.get("has_high_risk_matches"):
                st.error("High-similarity matches found (> 0.7)")

            similar = data.get("similar_denials", [])
            if similar:
                st.markdown("**Similar Denial Patterns:**")
                for i, denial in enumerate(similar, 1):
                    similarity = denial.get("similarity", 0)
                    with st.container(border=True):
                        col1, col2 = st.columns([1, 3])
                        with col1:
                            st.metric(
                                f"Match #{i}",
                                f"{similarity:.0%}",
                            )
                            st.caption(
                                f"CARC: {denial.get('carc_code', 'N/A')}"
                            )
                        with col2:
                            category = denial.get("category", "unknown")
                            st.markdown(
                                f"**{category.replace('_', ' ').title()}** -- "
                                f"{denial.get('denial_reason', '')}"
                            )
                            if denial.get("remediation"):
                                st.caption(f"Remediation: {denial['remediation'][:200]}...")
                            if denial.get("success_rate"):
                                st.caption(
                                    f"Appeal success rate: {denial['success_rate']:.0%}"
                                )
                        st.progress(min(similarity, 1.0))
            else:
                st.info("No similar denial patterns found in the knowledge base.")

    # Step 4: AI Risk Assessment
    if "risk_assessment" in steps:
        with st.expander("**Step 4:** AI Risk Assessment", expanded=True):
            data = steps["risk_assessment"]

            render_risk_badge(
                risk_level=data.get("risk_level", "unknown"),
                denial_probability=data.get("denial_probability", 0),
                confidence=data.get("confidence"),
            )

            factors = data.get("primary_risk_factors", [])
            if factors:
                st.markdown("**Primary Risk Factors:**")
                for factor in factors:
                    st.markdown(f"- {factor}")

            categories = data.get("likely_denial_categories", [])
            if categories:
                st.markdown(
                    "**Likely Denial Categories:** "
                    + ", ".join(f"`{c}`" for c in categories)
                )

            reasoning = data.get("reasoning", "")
            if reasoning:
                st.info(f"**Reasoning:** {reasoning}")

    # Step 5: Decision
    if "decision" in steps:
        with st.expander("**Step 5:** Decision & Recommendations", expanded=True):
            data = steps["decision"]

            status = data.get("status", "unknown")
            render_status_badge(status)

            if data.get("message"):
                st.markdown(data["message"])

            if data.get("recommendation"):
                st.markdown(f"**Recommendation:** {data['recommendation']}")

            if data.get("urgency"):
                st.markdown(f"**Urgency:** {data['urgency'].upper()}")

            # GenerateFeedbackNode specific fields
            if data.get("recommendations"):
                st.markdown("**Detailed Recommendations:**")
                for rec in data["recommendations"]:
                    priority = rec.get("priority", "medium")
                    priority_colors = {
                        "high": ":red[HIGH]",
                        "medium": ":orange[MEDIUM]",
                        "low": ":green[LOW]",
                    }
                    colored = priority_colors.get(priority, priority)
                    with st.container(border=True):
                        st.markdown(f"{colored} -- **{rec.get('issue', '')}**")
                        st.markdown(f"Action: {rec.get('action', '')}")

            if data.get("required_documentation"):
                st.markdown("**Required Documentation:**")
                for doc in data["required_documentation"]:
                    st.markdown(f"- {doc}")

            if data.get("suggested_code_changes"):
                st.markdown("**Suggested Code Changes:**")
                for change in data["suggested_code_changes"]:
                    st.markdown(f"- {change}")

            if data.get("next_steps"):
                st.markdown(f"**Next Steps:** {data['next_steps']}")
