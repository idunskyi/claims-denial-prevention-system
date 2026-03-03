"""
Denial Prevention Service Layer

Clean interface between denial prevention workflows and any frontend.
All methods return plain dictionaries - no workflow internals leak through.

Usage:
    service = DenialPreventionService()
    result = service.review_claim(claim_dict)
    # result is a plain dict, ready for JSON serialization
"""

import json
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from database.denial_knowledge_repository import DenialKnowledgeRepository
from database.session import db_session
from workflows.claim_review_workflow import ClaimReviewWorkflow
from workflows.denial_learning_workflow import DenialLearningWorkflow

logger = logging.getLogger(__name__)


class DenialPreventionService:
    """Service layer for denial prevention operations.

    This class is the single point of contact for any UI.
    Streamlit imports this. A future FastAPI router imports this.
    """

    def __init__(self, enable_tracing: bool = False):
        self._enable_tracing = enable_tracing
        self._data_root = (
            Path(__file__).parent.parent.parent
            / "requests"
            / "denial_prevention"
        )

    # ── Test Data Loading ────────────────────────────────────

    def list_test_claims(self, category: str = "all") -> list[dict]:
        """Return summaries of available test claims.

        Args:
            category: "normal", "at_risk", or "all"

        Returns:
            List of dicts with claim metadata for display in dropdowns.
        """
        claims = []

        if category in ("normal", "all"):
            claims_dir = self._data_root / "claims"
            if claims_dir.exists():
                for f in sorted(claims_dir.glob("claim_*.json")):
                    claims.append(self._summarize_claim(f, "normal"))

        if category in ("at_risk", "all"):
            claims_dir = self._data_root / "at_risk_claims"
            if claims_dir.exists():
                for f in sorted(claims_dir.glob("at_risk_*.json")):
                    claims.append(self._summarize_claim(f, "at_risk"))

        return claims

    def _summarize_claim(self, path: Path, category: str) -> dict:
        with open(path) as f:
            claim = json.load(f)

        procedures = claim.get("procedure_codes", [])
        proc_summary = procedures[0].get("display", "") if procedures else ""

        return {
            "filename": path.name,
            "category": category,
            "claim_id": claim.get("claim_id", ""),
            "patient_age": claim.get("patient_age"),
            "patient_gender": claim.get("patient_gender"),
            "billed_amount": claim.get("billed_amount"),
            "payer_name": claim.get("payer_name"),
            "procedure_summary": proc_summary,
            "risk_factors": claim.get("risk_factors", []),
            "expected_denial_category": claim.get("expected_denial_category"),
        }

    def load_claim(self, filename: str) -> dict:
        """Load a single claim JSON by filename.

        Searches both claims/ and at_risk_claims/ directories.
        """
        for subdir in ("claims", "at_risk_claims"):
            path = self._data_root / subdir / filename
            if path.exists():
                with open(path) as f:
                    return json.load(f)

        raise FileNotFoundError(f"Claim file not found: {filename}")

    def list_denial_templates(self) -> list[dict]:
        """Return available denial category files for the learning workflow."""
        denials_dir = self._data_root / "denials"
        templates = []

        if not denials_dir.exists():
            return templates

        for f in sorted(denials_dir.glob("*.json")):
            if f.name.startswith("_"):
                continue
            with open(f) as fh:
                data = json.load(fh)
            count = len(data) if isinstance(data, list) else 1
            templates.append({
                "category": f.stem,
                "filename": f.name,
                "count": count,
            })

        return templates

    def load_denial_template(self, category: str) -> list[dict]:
        """Load denial entries for a given category."""
        path = self._data_root / "denials" / f"{category}.json"
        if not path.exists():
            raise FileNotFoundError(f"Denial template not found: {category}")

        with open(path) as f:
            data = json.load(f)

        return data if isinstance(data, list) else [data]

    # ── Claim Review Workflow ────────────────────────────────

    def review_claim(self, claim: dict) -> dict:
        """Run the ClaimReviewWorkflow and return structured results.

        Args:
            claim: Claim dict matching ClaimEventSchema fields

        Returns:
            Dict with status, steps (one per workflow node), and execution_path.
        """
        workflow = ClaimReviewWorkflow(enable_tracing=self._enable_tracing)
        result = workflow.run(claim)
        return self._format_review_result(result, claim)

    def _format_review_result(self, task_context, claim: dict) -> dict:
        nodes = task_context.nodes
        steps = {}

        # Map internal node names to stable API keys
        node_key_map = {
            "AnalyzeClaimNode": "analyze_claim",
            "ExtractCodesNode": "extract_codes",
            "RAGRetrievalNode": "rag_retrieval",
            "RiskAssessmentNode": "risk_assessment",
        }

        for node_name, key in node_key_map.items():
            if node_name in nodes:
                output = nodes[node_name]
                steps[key] = (
                    output.model_dump() if hasattr(output, "model_dump") else output
                )

        # Handle enum serialization in risk_assessment
        if "risk_assessment" in steps and hasattr(
            steps["risk_assessment"].get("risk_level"), "value"
        ):
            steps["risk_assessment"]["risk_level"] = steps["risk_assessment"][
                "risk_level"
            ].value

        # Determine terminal node and status
        terminal_map = {
            "ApproveClaimNode": "approved",
            "GenerateFeedbackNode": "needs_attention",
            "EscalateClaimNode": "escalated",
        }

        status = "unknown"
        for node_name, status_val in terminal_map.items():
            if node_name in nodes:
                output = nodes[node_name]
                steps["decision"] = (
                    output.model_dump() if hasattr(output, "model_dump") else output
                )
                status = status_val
                break

        return {
            "claim_id": str(claim.get("claim_id", "")),
            "status": status,
            "steps": steps,
            "execution_path": list(nodes.keys()),
        }

    # ── Denial Learning Workflow ─────────────────────────────

    def learn_from_denial(self, denial: dict) -> dict:
        """Run the DenialLearningWorkflow and return structured results.

        Args:
            denial: Denial dict matching DenialEventSchema fields

        Returns:
            Dict with denial_id, steps, and stored flag.
        """
        workflow = DenialLearningWorkflow(enable_tracing=self._enable_tracing)
        result = workflow.run(denial)
        return self._format_learning_result(result, denial)

    def _format_learning_result(self, task_context, denial: dict) -> dict:
        nodes = task_context.nodes
        steps = {}

        if "AnalyzeDenialNode" in nodes:
            output = nodes["AnalyzeDenialNode"]
            steps["analyze_denial"] = (
                output.model_dump() if hasattr(output, "model_dump") else output
            )

        if "StoreInRAGNode" in nodes:
            output = nodes["StoreInRAGNode"]
            steps["store_in_rag"] = (
                output.model_dump() if hasattr(output, "model_dump") else output
            )

        stored = False
        if "store_in_rag" in steps:
            stored = steps["store_in_rag"].get("stored", False)

        return {
            "denial_id": str(denial.get("denial_id", "")),
            "steps": steps,
            "stored": stored,
        }

    # ── Knowledge Base ───────────────────────────────────────

    def get_knowledge_base_stats(self) -> dict:
        """Get summary statistics of the knowledge base."""
        try:
            with contextmanager(db_session)() as session:
                repo = DenialKnowledgeRepository(session)
                all_entries = repo.get_all()
                categories = {}
                for entry in all_entries:
                    cat = entry.category or "unknown"
                    categories[cat] = categories.get(cat, 0) + 1
                return {
                    "total_entries": len(all_entries),
                    "categories": categories,
                }
        except Exception as e:
            logger.error(f"Failed to get knowledge base stats: {e}")
            return {"total_entries": 0, "categories": {}}

    def get_knowledge_entries(self, category: Optional[str] = None) -> list[dict]:
        """Get knowledge base entries, optionally filtered by category."""
        try:
            with contextmanager(db_session)() as session:
                repo = DenialKnowledgeRepository(session)
                if category:
                    entries = repo.get_by_category(category)
                else:
                    entries = repo.get_all()
                return [e.to_dict() for e in entries]
        except Exception as e:
            logger.error(f"Failed to get knowledge entries: {e}")
            return []

    def search_knowledge_base(
        self, query_text: str, top_k: int = 5
    ) -> list[dict]:
        """Search knowledge base by text similarity."""
        from services.embedding_service import get_embedding_service

        try:
            with contextmanager(db_session)() as session:
                repo = DenialKnowledgeRepository(session)
                return repo.search_by_text(
                    text=query_text,
                    embedding_service=get_embedding_service(),
                    top_k=top_k,
                )
        except Exception as e:
            logger.error(f"Failed to search knowledge base: {e}")
            return []
