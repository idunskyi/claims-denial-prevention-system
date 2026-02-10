"""
Extract Codes Node

This node extracts and validates diagnosis and procedure codes from a claim.
It's a simple processing node (not an agent) that runs as part of the
concurrent analysis step.

What this node does:
1. Extracts all diagnosis codes (ICD-10)
2. Extracts all procedure codes (CPT/HCPCS)
3. Validates code formats
4. Identifies potential code-related issues

The output is used by the RAG retrieval node to build the search query.
"""

from typing import List, Optional
import re

from pydantic import Field

from core.nodes.base import Node
from core.task import TaskContext
from schemas.claim_schema import ClaimEventSchema


class ExtractCodesNode(Node):
    """Node that extracts and validates medical codes from claims.

    This node runs concurrently with other analysis nodes to extract
    the clinical codes that are central to denial prediction.
    """

    class OutputType(Node.OutputType):
        """Output structure for extracted codes."""

        diagnosis_codes: List[str] = Field(
            default_factory=list,
            description="List of diagnosis codes (e.g., ['M17.11', 'E11.9'])",
        )
        diagnosis_descriptions: List[str] = Field(
            default_factory=list,
            description="Human-readable descriptions of diagnoses",
        )
        procedure_codes: List[str] = Field(
            default_factory=list,
            description="List of procedure codes (e.g., ['99213', '27447'])",
        )
        procedure_descriptions: List[str] = Field(
            default_factory=list,
            description="Human-readable descriptions of procedures",
        )
        modifiers: List[str] = Field(
            default_factory=list,
            description="Procedure modifiers (e.g., ['25', '59'])",
        )
        code_issues: List[str] = Field(
            default_factory=list,
            description="Identified issues with codes",
        )
        has_valid_codes: bool = Field(
            default=True,
            description="Whether the claim has valid codes",
        )

    async def process(self, task_context: TaskContext) -> TaskContext:
        """Extract and validate codes from the claim.

        Args:
            task_context: The workflow context containing the claim

        Returns:
            Updated TaskContext with extracted codes
        """
        event: ClaimEventSchema = task_context.event

        # Extract codes
        diagnosis_codes = []
        diagnosis_descriptions = []
        for diag in event.diagnosis_codes:
            diagnosis_codes.append(diag.code)
            if diag.display:
                diagnosis_descriptions.append(diag.display)

        procedure_codes = []
        procedure_descriptions = []
        for proc in event.procedure_codes:
            procedure_codes.append(proc.code)
            if proc.display:
                procedure_descriptions.append(proc.display)

        modifiers = event.modifiers or []

        # Validate codes and identify issues
        code_issues = []

        # Check for missing diagnosis codes
        if not diagnosis_codes:
            code_issues.append("No diagnosis codes provided")

        # Check for missing procedure codes
        if not procedure_codes:
            code_issues.append("No procedure codes provided")

        # Validate ICD-10 format (basic check)
        for code in diagnosis_codes:
            if not self._is_valid_icd10(code):
                code_issues.append(f"Invalid ICD-10 format: {code}")

        # Validate CPT format (basic check)
        for code in procedure_codes:
            if not self._is_valid_cpt(code):
                code_issues.append(f"Invalid CPT format: {code}")

        # Check for common coding issues
        if self._has_unspecified_codes(diagnosis_codes):
            code_issues.append("Contains unspecified diagnosis codes - may be denied for lack of specificity")

        has_valid_codes = len(code_issues) == 0 or (
            len(diagnosis_codes) > 0 and len(procedure_codes) > 0
        )

        # Save output
        output = self.OutputType(
            diagnosis_codes=diagnosis_codes,
            diagnosis_descriptions=diagnosis_descriptions,
            procedure_codes=procedure_codes,
            procedure_descriptions=procedure_descriptions,
            modifiers=modifiers,
            code_issues=code_issues,
            has_valid_codes=has_valid_codes,
        )
        self.save_output(output)

        return task_context

    def _is_valid_icd10(self, code: str) -> bool:
        """Basic ICD-10 format validation.

        ICD-10 codes are 3-7 characters:
        - First character is a letter
        - Second and third are digits
        - Optional decimal and 1-4 more characters

        Examples: A01, A01.0, M17.11, Z00.00
        """
        if not code:
            return False

        # Also accept SNOMED codes (numeric)
        if code.isdigit():
            return True

        # ICD-10 pattern
        pattern = r'^[A-Z]\d{2}(\.\d{1,4})?$'
        return bool(re.match(pattern, code.upper()))

    def _is_valid_cpt(self, code: str) -> bool:
        """Basic CPT/HCPCS format validation.

        CPT codes are 5 digits
        HCPCS codes start with a letter followed by 4 digits

        Examples: 99213, 27447, G0439, J1234
        """
        if not code:
            return False

        # CPT: 5 digits
        if re.match(r'^\d{5}$', code):
            return True

        # HCPCS: Letter + 4 digits
        if re.match(r'^[A-Z]\d{4}$', code.upper()):
            return True

        # Category III CPT: 4 digits + T
        if re.match(r'^\d{4}T$', code.upper()):
            return True

        # SNOMED codes (longer numeric)
        if code.isdigit() and len(code) > 5:
            return True

        return False

    def _has_unspecified_codes(self, codes: List[str]) -> bool:
        """Check if any codes are unspecified (end in .9 or similar)."""
        for code in codes:
            # Unspecified ICD-10 codes often end in .9
            if code.endswith('.9') or code.endswith('.90') or code.endswith('.99'):
                return True
            # Or have format like X99
            if re.match(r'^[A-Z]\d{2}$', code.upper()):
                return True
        return False
