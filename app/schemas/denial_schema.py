"""
Denial Event Schema Module

This module defines the Pydantic schemas for denial notifications.
When a claim is denied by a payer, this event is sent to the system
so it can learn from the denial and improve future predictions.

The denial learning workflow:
1. Receive denial notification with reason codes
2. Analyze the denial pattern
3. Store in the denial knowledge base
4. Future claims benefit from this knowledge
"""

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class DenialCategory(str, Enum):
    """Standard denial categories.

    These map to common denial reasons across payers.
    """

    MEDICAL_NECESSITY = "medical_necessity"
    PRIOR_AUTHORIZATION = "prior_authorization"
    CODING_ERROR = "coding_error"
    DUPLICATE = "duplicate"
    TIMELY_FILING = "timely_filing"
    COVERAGE_TERMINATED = "coverage_terminated"
    NON_COVERED_SERVICE = "non_covered_service"
    OUT_OF_NETWORK = "out_of_network"
    DOCUMENTATION = "documentation"
    BUNDLING = "bundling"
    BENEFIT_MAXIMUM = "benefit_maximum"
    OTHER = "other"


class AppealOutcome(str, Enum):
    """Possible outcomes of an appeal."""

    APPROVED = "approved"
    DENIED = "denied"
    PARTIAL = "partial"
    PENDING = "pending"
    NOT_FILED = "not_filed"


class DenialEventSchema(BaseModel):
    """Schema for denial notifications.

    This schema captures information about a denied claim so the
    system can learn from it and improve future predictions.

    The information includes:
    - The denial reason and codes
    - The original claim characteristics
    - Appeal outcome (if known)

    Example:
        {
            "denial_id": "denial123",
            "original_claim_id": "claim456",
            "denial_date": "2024-01-20",
            "denial_code": "50",
            "denial_reason": "Service not medically necessary",
            "diagnosis_codes": ["M17.11"],
            "procedure_codes": ["27447"],
            "payer_id": "bcbs"
        }
    """

    # Identifiers
    denial_id: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for this denial record",
    )
    original_claim_id: UUID = Field(
        ...,
        description="ID of the original claim that was denied",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Time when the denial was received",
    )

    # Denial details
    denial_date: datetime = Field(
        ...,
        description="Date when the payer issued the denial",
    )
    denial_code: str = Field(
        ...,
        description="CARC (Claim Adjustment Reason Code) from the payer",
    )
    denial_reason: str = Field(
        ...,
        description="Human-readable denial reason from the payer",
    )
    denial_category: DenialCategory = Field(
        default=DenialCategory.OTHER,
        description="Categorized denial type",
    )
    rarc_codes: List[str] = Field(
        default_factory=list,
        description="RARC (Remittance Advice Remark Codes) for additional detail",
    )

    # Original claim snapshot (for context)
    diagnosis_codes: List[str] = Field(
        default_factory=list,
        description="Diagnosis codes from the original claim",
    )
    procedure_codes: List[str] = Field(
        default_factory=list,
        description="Procedure codes from the original claim",
    )
    modifiers: List[str] = Field(
        default_factory=list,
        description="Modifiers from the original claim",
    )
    billed_amount: Optional[Decimal] = Field(
        default=None,
        description="Original billed amount",
    )
    allowed_amount: Optional[Decimal] = Field(
        default=None,
        description="Amount allowed by payer (if any)",
    )

    # Payer information
    payer_id: str = Field(..., description="Payer identifier")
    payer_name: Optional[str] = Field(
        default=None,
        description="Payer name",
    )
    plan_type: Optional[str] = Field(
        default=None,
        description="Type of insurance plan",
    )

    # Provider information
    provider_npi: Optional[str] = Field(
        default=None,
        description="NPI of the rendering provider",
    )
    facility_type: Optional[str] = Field(
        default=None,
        description="Type of facility",
    )

    # Appeal information (if available)
    appeal_filed: bool = Field(
        default=False,
        description="Whether an appeal has been filed",
    )
    appeal_date: Optional[datetime] = Field(
        default=None,
        description="Date when appeal was filed",
    )
    appeal_outcome: Optional[AppealOutcome] = Field(
        default=None,
        description="Outcome of the appeal if filed",
    )
    appeal_notes: Optional[str] = Field(
        default=None,
        description="Notes about the appeal process or outcome",
    )

    # Additional context
    clinical_notes: Optional[str] = Field(
        default=None,
        description="Relevant clinical notes or documentation",
    )
    remediation_applied: Optional[str] = Field(
        default=None,
        description="What remediation was attempted for the appeal",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "denial_id": "550e8400-e29b-41d4-a716-446655440001",
                "original_claim_id": "550e8400-e29b-41d4-a716-446655440000",
                "denial_date": "2024-01-20T00:00:00Z",
                "denial_code": "50",
                "denial_reason": "These are non-covered services because this is not deemed a 'medical necessity'",
                "denial_category": "medical_necessity",
                "diagnosis_codes": ["M17.11"],
                "procedure_codes": ["27447"],
                "billed_amount": 45000.00,
                "payer_id": "bcbs",
                "payer_name": "Blue Cross Blue Shield",
                "appeal_filed": True,
                "appeal_outcome": "approved",
            }
        }
    )
