"""
Claim Event Schema Module

This module defines the Pydantic schemas for healthcare claims.
These schemas are used to validate incoming claim data and provide
type safety throughout the workflow.

The schema is designed to be format-agnostic - it can be populated
from FHIR, X12 837, CSV, or any other source with appropriate mapping.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class DiagnosisCode(BaseModel):
    """A diagnosis code (ICD-10, SNOMED, etc.)."""

    code: str = Field(..., description="The diagnosis code (e.g., 'M17.11')")
    system: str = Field(
        default="ICD-10",
        description="The coding system (ICD-10, SNOMED, etc.)",
    )
    display: str = Field(
        default="",
        description="Human-readable description of the diagnosis",
    )


class ProcedureCode(BaseModel):
    """A procedure code (CPT, HCPCS, etc.)."""

    code: str = Field(..., description="The procedure code (e.g., '99213')")
    original_code: Optional[str] = Field(
        default=None,
        description="Original code if mapped from another system",
    )
    system: str = Field(
        default="CPT",
        description="The coding system (CPT, HCPCS, SNOMED, etc.)",
    )
    display: str = Field(
        default="",
        description="Human-readable description of the procedure",
    )


class PlanType(str, Enum):
    """Insurance plan types."""

    HMO = "HMO"
    PPO = "PPO"
    EPO = "EPO"
    POS = "POS"
    MEDICARE = "Medicare"
    MEDICAID = "Medicaid"
    OTHER = "Other"


class FacilityType(str, Enum):
    """Healthcare facility types."""

    INPATIENT = "inpatient"
    OUTPATIENT = "outpatient"
    EMERGENCY = "emergency"
    AMBULATORY = "ambulatory"
    OFFICE = "office"
    HOME = "home"
    OTHER = "other"


class ClaimEventSchema(BaseModel):
    """Schema for incoming healthcare claims.

    This schema represents a claim submitted for review. It contains
    all the information needed to assess denial risk.

    The schema is designed to accept data from various sources:
    - FHIR Claims/ExplanationOfBenefit
    - X12 837 Professional/Institutional
    - CSV exports from billing systems

    Example:
        {
            "claim_id": "abc123",
            "patient_id": "patient456",
            "service_date": "2024-01-15",
            "diagnosis_codes": [{"code": "M17.11", "display": "Primary osteoarthritis, right knee"}],
            "procedure_codes": [{"code": "27447", "display": "Total knee replacement"}],
            "payer_name": "Blue Cross Blue Shield",
            "billed_amount": 45000.00
        }
    """

    # Identifiers
    claim_id: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for the claim",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Time when the claim was received for review",
    )

    # Patient information (de-identified for PoC)
    patient_id: str = Field(..., description="De-identified patient identifier")
    patient_age: Optional[int] = Field(
        default=None,
        ge=0,
        le=150,
        description="Patient age in years",
    )
    patient_gender: Optional[str] = Field(
        default=None,
        description="Patient gender (male, female, other, unknown)",
    )

    # Provider information
    provider_name: str = Field(..., description="Name of the rendering provider")
    provider_npi: Optional[str] = Field(
        default=None,
        description="National Provider Identifier (10-digit)",
    )
    facility_name: Optional[str] = Field(
        default=None,
        description="Name of the facility where services were rendered",
    )
    facility_type: Optional[str] = Field(
        default="outpatient",
        description="Type of facility (inpatient, outpatient, etc.)",
    )

    # Dates
    service_date: date = Field(..., description="Date when services were rendered")
    submission_date: Optional[date] = Field(
        default=None,
        description="Date when claim was submitted to payer",
    )

    # Clinical codes - the most important fields for denial prediction
    diagnosis_codes: List[DiagnosisCode] = Field(
        default_factory=list,
        description="List of diagnosis codes (ICD-10)",
    )
    procedure_codes: List[ProcedureCode] = Field(
        default_factory=list,
        description="List of procedure codes (CPT/HCPCS)",
    )
    modifiers: List[str] = Field(
        default_factory=list,
        description="Procedure modifiers (e.g., '25', '59')",
    )

    # Place of service
    place_of_service: Optional[str] = Field(
        default=None,
        description="CMS Place of Service code (e.g., '11' for office)",
    )

    # Financial
    billed_amount: Decimal = Field(
        ...,
        ge=0,
        description="Total billed amount in USD",
    )
    currency: str = Field(default="USD", description="Currency code")

    # Payer information
    payer_name: str = Field(..., description="Name of the insurance payer")
    payer_id: Optional[str] = Field(
        default=None,
        description="Payer identifier",
    )
    plan_type: Optional[str] = Field(
        default=None,
        description="Type of insurance plan (HMO, PPO, etc.)",
    )

    # Prior authorization
    prior_auth_number: Optional[str] = Field(
        default=None,
        description="Prior authorization number if obtained",
    )
    prior_auth_required: bool = Field(
        default=False,
        description="Whether prior authorization is required for this service",
    )

    # Supporting documentation
    clinical_notes_summary: Optional[str] = Field(
        default=None,
        description="Summary of clinical notes supporting medical necessity",
    )

    # Risk factors (populated by system, not input)
    risk_factors: Optional[List[str]] = Field(
        default=None,
        description="Identified risk factors (populated during analysis)",
    )
    expected_denial_category: Optional[str] = Field(
        default=None,
        description="Expected denial category if known (for testing)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "claim_id": "550e8400-e29b-41d4-a716-446655440000",
                "patient_id": "patient123",
                "patient_age": 65,
                "patient_gender": "female",
                "provider_name": "Dr. Smith Orthopedics",
                "provider_npi": "1234567890",
                "service_date": "2024-01-15",
                "diagnosis_codes": [
                    {
                        "code": "M17.11",
                        "system": "ICD-10",
                        "display": "Primary osteoarthritis, right knee",
                    }
                ],
                "procedure_codes": [
                    {
                        "code": "27447",
                        "system": "CPT",
                        "display": "Total knee replacement",
                    }
                ],
                "billed_amount": 45000.00,
                "payer_name": "Blue Cross Blue Shield",
                "plan_type": "PPO",
                "prior_auth_required": True,
                "prior_auth_number": None,
            }
        }
    )
