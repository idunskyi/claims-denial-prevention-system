"""
Denial Prevention API Endpoints

This module provides API endpoints for the denial prevention system:
1. POST /claims/review - Submit a claim for denial risk review
2. POST /denials/learn - Submit a denial notification for learning

Both endpoints can be used synchronously (immediate response) or
asynchronously (queued processing via Celery).
"""

from http import HTTPStatus
import json
import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from starlette.responses import Response

from worker.config import celery_app
from database.event import Event
from database.repository import GenericRepository
from database.session import db_session
from schemas.claim_schema import ClaimEventSchema
from schemas.denial_schema import DenialEventSchema
from workflows.workflow_registry import WorkflowRegistry
from workflows.claim_review_workflow import ClaimReviewWorkflow
from workflows.denial_learning_workflow import DenialLearningWorkflow

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/claims/review")
def review_claim(
    data: ClaimEventSchema,
    sync: bool = Query(default=True, description="If true, process synchronously and return result"),
    session: Session = Depends(db_session),
) -> Response:
    """Submit a claim for denial risk review.

    This endpoint analyzes a claim before submission to identify
    potential denial risks and provide recommendations.

    Args:
        data: The claim data
        sync: If true (default), process immediately and return result.
              If false, queue for async processing and return task ID.
        session: Database session

    Returns:
        - If sync=true: Risk assessment and recommendations
        - If sync=false: 202 Accepted with task ID

    Example response (sync):
        {
            "claim_id": "...",
            "risk_level": "medium",
            "denial_probability": 0.45,
            "recommendations": [...],
            "status": "requires_attention"
        }
    """
    # Store event in database
    repository = GenericRepository(session=session, model=Event)
    raw_event = data.model_dump(mode="json")
    event = Event(
        data=raw_event,
        workflow_type=WorkflowRegistry.CLAIM_REVIEW.name
    )
    repository.create(obj=event)

    if sync:
        # Process synchronously
        try:
            # Disable tracing if Langfuse is not configured
            import os
            enable_tracing = bool(os.getenv("LANGFUSE_SECRET_KEY"))
            workflow = ClaimReviewWorkflow(enable_tracing=enable_tracing)
            result = workflow.run(raw_event)

            # Update event with result
            event.task_context = result.model_dump(mode="json")
            repository.update(obj=event)

            # Extract the key outputs
            response_data = _format_claim_review_response(result)
            return Response(
                content=json.dumps(response_data, indent=2),
                status_code=HTTPStatus.OK,
                media_type="application/json",
            )
        except Exception as e:
            logger.error(f"Error processing claim review: {e}")
            return Response(
                content=json.dumps({"error": str(e)}),
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                media_type="application/json",
            )
    else:
        # Queue for async processing
        task_id = celery_app.send_task(
            "process_incoming_event",
            args=[str(event.id)],
        )
        return Response(
            content=json.dumps({
                "message": f"Claim review queued",
                "task_id": str(task_id),
                "event_id": str(event.id),
            }),
            status_code=HTTPStatus.ACCEPTED,
            media_type="application/json",
        )


@router.post("/denials/learn")
def learn_from_denial(
    data: DenialEventSchema,
    sync: bool = Query(default=True, description="If true, process synchronously"),
    session: Session = Depends(db_session),
) -> Response:
    """Submit a denial notification for learning.

    This endpoint processes denial notifications and stores the
    patterns in the knowledge base for future prevention.

    Args:
        data: The denial notification data
        sync: If true (default), process immediately.
              If false, queue for async processing.
        session: Database session

    Returns:
        - If sync=true: Confirmation of pattern storage
        - If sync=false: 202 Accepted with task ID

    Example response (sync):
        {
            "denial_id": "...",
            "pattern_stored": true,
            "category": "prior_authorization",
            "message": "Pattern added to knowledge base"
        }
    """
    # Store event in database
    repository = GenericRepository(session=session, model=Event)
    raw_event = data.model_dump(mode="json")
    event = Event(
        data=raw_event,
        workflow_type=WorkflowRegistry.DENIAL_LEARNING.name
    )
    repository.create(obj=event)

    if sync:
        # Process synchronously
        try:
            enable_tracing = bool(os.getenv("LANGFUSE_SECRET_KEY"))
            workflow = DenialLearningWorkflow(enable_tracing=enable_tracing)
            result = workflow.run(raw_event)

            # Update event with result
            event.task_context = result.model_dump(mode="json")
            repository.update(obj=event)

            # Extract the key outputs
            response_data = _format_denial_learning_response(result)
            return Response(
                content=json.dumps(response_data, indent=2),
                status_code=HTTPStatus.OK,
                media_type="application/json",
            )
        except Exception as e:
            logger.error(f"Error processing denial learning: {e}")
            return Response(
                content=json.dumps({"error": str(e)}),
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                media_type="application/json",
            )
    else:
        # Queue for async processing
        task_id = celery_app.send_task(
            "process_incoming_event",
            args=[str(event.id)],
        )
        return Response(
            content=json.dumps({
                "message": f"Denial learning queued",
                "task_id": str(task_id),
                "event_id": str(event.id),
            }),
            status_code=HTTPStatus.ACCEPTED,
            media_type="application/json",
        )


def _format_claim_review_response(result) -> dict:
    """Format the claim review result for API response."""
    nodes = result.nodes

    response = {
        "claim_id": str(result.event.claim_id) if hasattr(result.event, 'claim_id') else None,
        "workflow": "claim_review",
    }

    # Extract risk assessment if available
    if "RiskAssessmentNode" in nodes:
        risk = nodes["RiskAssessmentNode"]
        response["risk_level"] = risk.risk_level.value if hasattr(risk.risk_level, 'value') else risk.risk_level
        response["denial_probability"] = risk.denial_probability
        response["primary_risk_factors"] = risk.primary_risk_factors
        response["likely_denial_categories"] = risk.likely_denial_categories
        response["reasoning"] = risk.reasoning

    # Determine final status based on which terminal node was reached
    if "ApproveClaimNode" in nodes:
        response["status"] = "approved"
        response["message"] = nodes["ApproveClaimNode"].message
    elif "EscalateClaimNode" in nodes:
        response["status"] = "escalated"
        response["message"] = nodes["EscalateClaimNode"].message
        response["urgency"] = nodes["EscalateClaimNode"].urgency
        response["recommendation"] = nodes["EscalateClaimNode"].recommendation
    elif "GenerateFeedbackNode" in nodes:
        response["status"] = "requires_attention"
        feedback = nodes["GenerateFeedbackNode"]
        response["summary"] = feedback.summary
        response["recommendations"] = [r.model_dump() if hasattr(r, 'model_dump') else r for r in feedback.recommendations]
        response["required_documentation"] = feedback.required_documentation
        response["suggested_code_changes"] = feedback.suggested_code_changes
        response["next_steps"] = feedback.next_steps

    return response


def _format_denial_learning_response(result) -> dict:
    """Format the denial learning result for API response."""
    nodes = result.nodes

    response = {
        "denial_id": str(result.event.denial_id) if hasattr(result.event, 'denial_id') else None,
        "workflow": "denial_learning",
    }

    # Extract analysis results
    if "AnalyzeDenialNode" in nodes:
        analysis = nodes["AnalyzeDenialNode"]
        response["confirmed_category"] = analysis.confirmed_category
        response["denial_pattern_summary"] = analysis.denial_pattern_summary
        response["recommended_remediation"] = analysis.recommended_remediation

    # Extract storage results
    if "StoreInRAGNode" in nodes:
        storage = nodes["StoreInRAGNode"]
        response["pattern_stored"] = storage.stored
        response["knowledge_id"] = storage.knowledge_id
        response["message"] = storage.message

    return response
