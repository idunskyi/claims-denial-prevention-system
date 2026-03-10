"""
Generate a synthetic denial knowledge base for the denial prevention PoC.
This creates realistic denial patterns based on common healthcare claim denial reasons.

The knowledge base uses actual CARC (Claim Adjustment Reason Codes) and RARC
(Remittance Advice Remark Codes) used in real healthcare billing.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

OUTPUT_DIR = Path(__file__).parent.parent.parent / "requests/denial_prevention/denials"

# Common CARC codes (Claim Adjustment Reason Codes)
CARC_CODES = {
    "1": "Deductible Amount",
    "2": "Coinsurance Amount",
    "3": "Co-payment Amount",
    "4": "The procedure code is inconsistent with the modifier used",
    "5": "The procedure code/bill type is inconsistent with the place of service",
    "6": "The procedure/revenue code is inconsistent with the patient's age",
    "7": "The procedure/revenue code is inconsistent with the patient's gender",
    "8": "The procedure code is inconsistent with the provider type/specialty",
    "9": "The diagnosis is inconsistent with the patient's age",
    "10": "The diagnosis is inconsistent with the patient's gender",
    "11": "The diagnosis is inconsistent with the procedure",
    "12": "The diagnosis is inconsistent with the provider type",
    "15": "The authorization number is missing, invalid, or does not apply",
    "16": "Claim/service lacks information or has submission errors",
    "18": "Exact duplicate claim/service",
    "19": "Claim/service adjusted because it is a work-related injury/illness",
    "20": "Claim/service adjusted because it is not a work-related injury/illness",
    "22": "Claim/service adjusted because this care may be covered by another payer",
    "23": "The claim lacked required certification or authorization",
    "26": "Expenses incurred prior to coverage",
    "27": "Expenses incurred after coverage terminated",
    "29": "The time limit for filing has expired",
    "31": "Patient cannot be identified as our insured",
    "32": "Our records indicate that this dependent is not an eligible dependent",
    "33": "Claim/service adjusted because it is not covered",
    "35": "Lifetime benefit maximum has been reached",
    "39": "Services denied at the time authorization/pre-certification was requested",
    "45": "Charge exceeds fee schedule/maximum allowable",
    "49": "This is a non-covered service because it is a routine/preventive exam",
    "50": "These are non-covered services because this is not deemed a 'medical necessity'",
    "51": "These are non-covered services because this is a pre-existing condition",
    "55": "Procedure/treatment/drug is not approved by the FDA",
    "56": "Procedure/treatment has not been deemed 'proven to be effective'",
    "57": "Payment denied/reduced because this service is not medically necessary",
    "58": "Treatment was deemed by the payer to have been rendered in an inappropriate setting",
    "59": "Services processed under another claim/encounter",
    "96": "Non-covered charge(s). At least one Remark Code must be provided",
    "97": "The benefit for this service is included in the payment for another service",
    "119": "Benefit maximum for this time period or occurrence has been reached",
    "151": "Payment adjusted because the payer deems the information submitted does not support this level of service",
    "167": "This (these) diagnosis(es) is (are) not covered",
    "170": "Payment is denied when performed/billed by this type of provider",
    "171": "Payment is denied when performed/billed by this type of provider in this type of facility",
    "181": "Procedure code was invalid on the date of service",
    "182": "Procedure modifier was invalid on the date of service",
    "183": "The referring provider is not eligible to refer the service billed",
    "192": "Non standard adjustment code from paper remittance",
    "197": "Precertification/authorization/notification absent",
    "198": "Precertification/authorization/notification exceeded",
    "199": "Revenue code and Procedure code do not match",
    "204": "This service/equipment/drug is not covered under the patient's current benefit plan",
    "207": "The modifier is missing",
    "208": "National Drug Codes (NDC) are missing",
    "209": "National Drug Code (NDC) is invalid",
    "226": "Information requested from the Billing/Rendering Provider was not provided",
    "227": "Information requested from the patient/insured/responsible party was not provided",
    "242": "Services not provided by network/primary care providers",
    "243": "Services not authorized by network/primary care providers",
    "252": "An attachment/other documentation is required to adjudicate this claim",
    "256": "Service not payable per managed care contract",
}

# Denial categories with detailed knowledge entries
DENIAL_KNOWLEDGE = []


def add_medical_necessity_denials():
    """Add denials related to medical necessity (most common category - ~30% of denials)."""

    entries = [
        {
            "category": "medical_necessity",
            "carc_code": "50",
            "denial_reason": "Service not deemed medically necessary based on submitted diagnosis codes",
            "trigger_patterns": {
                "diagnosis_codes": ["Z00.00", "Z00.01"],  # Routine encounters
                "procedure_codes": ["99214", "99215"],     # Higher-level E/M codes
            },
            "remediation": "Provide additional clinical documentation supporting medical necessity. Include chief complaint, detailed HPI, and clinical findings that justify the service level.",
            "appeal_template": "The patient presented with [symptoms] requiring thorough evaluation. Clinical examination revealed [findings]. The complexity of medical decision-making warranted the service level billed.",
            "success_rate": 0.65,
            "typical_payers": ["all"],
        },
        {
            "category": "medical_necessity",
            "carc_code": "57",
            "denial_reason": "Imaging study not supported by diagnosis",
            "trigger_patterns": {
                "diagnosis_codes": ["M54.5", "M54.2"],  # Low back pain
                "procedure_codes": ["72148", "72149", "72158"],  # MRI lumbar spine
            },
            "remediation": "Document failed conservative treatment (6+ weeks physical therapy, NSAIDs). Include red flag symptoms if present (neurological deficits, progressive weakness).",
            "appeal_template": "Patient has failed conservative management including [treatments] for [duration]. Progressive symptoms warrant imaging to rule out serious pathology.",
            "success_rate": 0.72,
            "typical_payers": ["all"],
        },
        {
            "category": "medical_necessity",
            "carc_code": "50",
            "denial_reason": "Preventive service billed with illness diagnosis",
            "trigger_patterns": {
                "diagnosis_codes": ["J06.9", "J02.9"],  # URI, sore throat
                "procedure_codes": ["99395", "99396"],  # Preventive visits
            },
            "remediation": "Separate preventive and problem-focused services. Use modifier 25 for E/M if both are provided on same date.",
            "appeal_template": "Patient was seen for scheduled preventive visit. An additional problem-focused service was provided for [condition]. Both services are separately identifiable.",
            "success_rate": 0.85,
            "typical_payers": ["all"],
        },
        {
            "category": "medical_necessity",
            "carc_code": "151",
            "denial_reason": "Documentation does not support level of service billed",
            "trigger_patterns": {
                "procedure_codes": ["99215", "99205"],  # High complexity visits
            },
            "remediation": "Ensure documentation meets 2021 E/M guidelines: document time OR medical decision making (MDM) complexity including diagnoses addressed, data reviewed, and risk.",
            "appeal_template": "Documentation demonstrates [MDM complexity level] based on: [number] diagnoses addressed, [data elements] reviewed, and [risk level] of treatment options.",
            "success_rate": 0.55,
            "typical_payers": ["all"],
        },
        {
            "category": "medical_necessity",
            "carc_code": "56",
            "denial_reason": "Experimental/investigational procedure not covered",
            "trigger_patterns": {
                "procedure_codes": ["0402T", "0403T"],  # Category III codes
            },
            "remediation": "Provide peer-reviewed literature supporting efficacy. Consider patient assistance programs or self-pay options.",
            "appeal_template": "This procedure has demonstrated efficacy in [studies]. Patient has exhausted standard treatment options including [treatments].",
            "success_rate": 0.25,
            "typical_payers": ["all"],
        },
    ]

    DENIAL_KNOWLEDGE.extend(entries)


def add_prior_auth_denials():
    """Add denials related to prior authorization (second most common)."""

    entries = [
        {
            "category": "prior_authorization",
            "carc_code": "197",
            "denial_reason": "Prior authorization was not obtained before service was rendered",
            "trigger_patterns": {
                "procedure_codes": ["27447", "27130"],  # Knee/hip replacement
                "prior_auth_required": True,
                "prior_auth_number": None,
            },
            "remediation": "Submit retroactive authorization request with clinical documentation. Many payers allow 48-72 hour grace period for urgent services.",
            "appeal_template": "Service was rendered urgently due to [clinical urgency]. Retroactive authorization is requested based on medical necessity documentation.",
            "success_rate": 0.45,
            "typical_payers": ["all"],
        },
        {
            "category": "prior_authorization",
            "carc_code": "15",
            "denial_reason": "Authorization number is invalid or expired",
            "trigger_patterns": {
                "prior_auth_required": True,
            },
            "remediation": "Verify authorization validity dates. Resubmit with correct authorization number or request extension if treatment delayed.",
            "appeal_template": "Original authorization [number] was valid at time of scheduling. Treatment was delayed due to [reason]. Request approval for services rendered within reasonable timeframe.",
            "success_rate": 0.80,
            "typical_payers": ["all"],
        },
        {
            "category": "prior_authorization",
            "carc_code": "198",
            "denial_reason": "Services exceeded authorized quantity or duration",
            "trigger_patterns": {
                "procedure_codes": ["97110", "97140"],  # Physical therapy
            },
            "remediation": "Document continued medical necessity. Request authorization extension with updated treatment plan showing progress and remaining goals.",
            "appeal_template": "Patient requires additional sessions due to [clinical reason]. Functional progress documented: [metrics]. Anticipated discharge in [timeframe].",
            "success_rate": 0.70,
            "typical_payers": ["all"],
        },
        {
            "category": "prior_authorization",
            "carc_code": "39",
            "denial_reason": "Services denied at time authorization was requested",
            "trigger_patterns": {
                "procedure_codes": ["43239", "43249"],  # Upper GI endoscopy
            },
            "remediation": "Appeal with additional clinical documentation. Consider peer-to-peer review with payer medical director.",
            "appeal_template": "Initial authorization denial did not consider [additional clinical factors]. Peer-reviewed guidelines support this service for patients with [criteria].",
            "success_rate": 0.50,
            "typical_payers": ["all"],
        },
    ]

    DENIAL_KNOWLEDGE.extend(entries)


def add_coding_error_denials():
    """Add denials related to coding errors and mismatches."""

    entries = [
        {
            "category": "coding_error",
            "carc_code": "4",
            "denial_reason": "Procedure code is inconsistent with modifier used",
            "trigger_patterns": {
                "procedure_codes": ["99213"],
                "modifiers": ["25"],  # Without separate E/M service
            },
            "remediation": "Modifier 25 requires separately identifiable E/M service. Remove modifier or ensure documentation supports distinct service.",
            "appeal_template": "Modifier 25 was appropriately used to indicate a separately identifiable E/M service distinct from the procedure performed.",
            "success_rate": 0.75,
            "typical_payers": ["all"],
        },
        {
            "category": "coding_error",
            "carc_code": "11",
            "denial_reason": "Diagnosis code does not support procedure code",
            "trigger_patterns": {
                "diagnosis_codes": ["Z23"],  # Immunization encounter
                "procedure_codes": ["99213"],  # Office visit instead of immunization admin
            },
            "remediation": "Review diagnosis codes for specificity. Use codes that clearly indicate medical necessity for the procedure performed.",
            "appeal_template": "Primary diagnosis [code] directly supports the medical necessity for [procedure]. Supporting documentation attached.",
            "success_rate": 0.80,
            "typical_payers": ["all"],
        },
        {
            "category": "coding_error",
            "carc_code": "5",
            "denial_reason": "Procedure code inconsistent with place of service",
            "trigger_patterns": {
                "procedure_codes": ["99281", "99282"],  # ED codes
                "place_of_service": "11",  # Office
            },
            "remediation": "Verify place of service code matches where service was actually rendered. POS 11=Office, 21=Hospital Inpatient, 22=Outpatient, 23=ER.",
            "appeal_template": "Place of service has been corrected to accurately reflect service location. Corrected claim attached.",
            "success_rate": 0.90,
            "typical_payers": ["all"],
        },
        {
            "category": "coding_error",
            "carc_code": "181",
            "denial_reason": "Procedure code was invalid on the date of service",
            "trigger_patterns": {},
            "remediation": "Verify procedure code is valid for date of service. Check for code changes in annual CPT updates. Use successor code if applicable.",
            "appeal_template": "Corrected claim submitted with valid procedure code [code] effective for date of service.",
            "success_rate": 0.95,
            "typical_payers": ["all"],
        },
        {
            "category": "coding_error",
            "carc_code": "207",
            "denial_reason": "Required modifier is missing",
            "trigger_patterns": {
                "procedure_codes": ["77067"],  # Screening mammography
                "modifiers": [],
            },
            "remediation": "Add required modifier (e.g., bilateral modifier 50, distinct procedural service modifier 59, screening modifier 33).",
            "appeal_template": "Claim corrected with appropriate modifier [modifier] to indicate [reason].",
            "success_rate": 0.92,
            "typical_payers": ["all"],
        },
        {
            "category": "coding_error",
            "carc_code": "97",
            "denial_reason": "Service bundled with another procedure - separate payment not allowed",
            "trigger_patterns": {
                "procedure_codes": ["36415", "99213"],  # Venipuncture with office visit
            },
            "remediation": "Review NCCI edits for bundling rules. Use modifier 59 or X{EPSU} only if services are truly distinct and separately documented.",
            "appeal_template": "Services were distinct and separately identifiable per documentation. Modifier 59 appropriately indicates services were not bundled.",
            "success_rate": 0.60,
            "typical_payers": ["all"],
        },
    ]

    DENIAL_KNOWLEDGE.extend(entries)


def add_duplicate_denials():
    """Add denials related to duplicate claims."""

    entries = [
        {
            "category": "duplicate",
            "carc_code": "18",
            "denial_reason": "Exact duplicate claim/service - already adjudicated",
            "trigger_patterns": {},
            "remediation": "Verify original claim status. If paid, no action needed. If denied incorrectly, submit appeal rather than new claim.",
            "appeal_template": "This is not a duplicate submission. Original claim [number] was for [different service/date/provider]. Current claim is for distinct service.",
            "success_rate": 0.85,
            "typical_payers": ["all"],
        },
        {
            "category": "duplicate",
            "carc_code": "59",
            "denial_reason": "Processed under another claim - benefits applied to previous submission",
            "trigger_patterns": {},
            "remediation": "Request EOB for original claim to verify benefits applied. If services are distinct, appeal with documentation showing separate services.",
            "appeal_template": "Services billed are distinct from claim [number]. Documentation demonstrates [distinguishing factors].",
            "success_rate": 0.70,
            "typical_payers": ["all"],
        },
    ]

    DENIAL_KNOWLEDGE.extend(entries)


def add_timely_filing_denials():
    """Add denials related to timely filing limits."""

    entries = [
        {
            "category": "timely_filing",
            "carc_code": "29",
            "denial_reason": "Claim submitted after filing deadline",
            "trigger_patterns": {},
            "remediation": "Document reason for delay (prior payer processing, coordination of benefits, etc.). Most payers have exceptions for delays outside provider control.",
            "appeal_template": "Timely filing exception requested. Initial submission to [payer] on [date] resulted in [outcome]. Coordination of benefits delayed secondary submission.",
            "success_rate": 0.40,
            "typical_payers": ["all"],
            "payer_specific_limits": {
                "Medicare": 365,
                "Medicaid": 365,
                "Blue Cross Blue Shield": 180,
                "Aetna": 90,
                "UnitedHealthcare": 90,
                "Cigna": 90,
                "Humana": 365,
            },
        },
    ]

    DENIAL_KNOWLEDGE.extend(entries)


def add_coverage_denials():
    """Add denials related to coverage issues."""

    entries = [
        {
            "category": "coverage_terminated",
            "carc_code": "27",
            "denial_reason": "Patient coverage terminated prior to date of service",
            "trigger_patterns": {},
            "remediation": "Verify eligibility with patient. Bill patient directly or identify other coverage (COBRA, marketplace, Medicaid).",
            "appeal_template": "Eligibility verification on [date] confirmed active coverage. Documentation of verification attached.",
            "success_rate": 0.30,
            "typical_payers": ["all"],
        },
        {
            "category": "coverage_terminated",
            "carc_code": "26",
            "denial_reason": "Service date is prior to coverage effective date",
            "trigger_patterns": {},
            "remediation": "Verify coverage dates. Consider billing retroactive coverage if patient has applied.",
            "appeal_template": "Patient's coverage was applied retroactively per [state law/plan provision]. Updated coverage dates attached.",
            "success_rate": 0.35,
            "typical_payers": ["all"],
        },
        {
            "category": "non_covered_service",
            "carc_code": "96",
            "denial_reason": "Service is excluded from patient's benefit plan",
            "trigger_patterns": {
                "procedure_codes": ["D0120", "D0220"],  # Dental codes
            },
            "remediation": "Verify benefit coverage with payer. Consider medical necessity appeal if service is typically excluded but medically indicated.",
            "appeal_template": "Service is medically necessary due to [condition]. Request exception to exclusion based on [medical justification].",
            "success_rate": 0.20,
            "typical_payers": ["all"],
        },
        {
            "category": "non_covered_service",
            "carc_code": "204",
            "denial_reason": "Service not covered under patient's current benefit plan",
            "trigger_patterns": {},
            "remediation": "Review plan benefits. Inform patient of non-covered status. Patient may appeal for plan exception or pay out-of-pocket.",
            "appeal_template": "Request benefit exception based on medical necessity. Patient has no alternative covered treatment option.",
            "success_rate": 0.25,
            "typical_payers": ["all"],
        },
        {
            "category": "out_of_network",
            "carc_code": "242",
            "denial_reason": "Services not provided by in-network provider",
            "trigger_patterns": {},
            "remediation": "Document lack of in-network providers for specialty. Request in-network exception or gap exception for continuity of care.",
            "appeal_template": "No in-network providers available within [distance] miles for [specialty]. Request in-network exception per [state law/plan provision].",
            "success_rate": 0.55,
            "typical_payers": ["HMO", "EPO"],
        },
        {
            "category": "out_of_network",
            "carc_code": "243",
            "denial_reason": "Referral not obtained from primary care provider",
            "trigger_patterns": {},
            "remediation": "Obtain retroactive referral from PCP if possible. Appeal citing urgent/emergent circumstances if applicable.",
            "appeal_template": "Services were [urgent/emergent], precluding standard referral process. Retroactive referral obtained on [date].",
            "success_rate": 0.60,
            "typical_payers": ["HMO"],
        },
    ]

    DENIAL_KNOWLEDGE.extend(entries)


def add_documentation_denials():
    """Add denials related to missing/insufficient documentation."""

    entries = [
        {
            "category": "documentation",
            "carc_code": "252",
            "denial_reason": "Additional documentation required to process claim",
            "trigger_patterns": {},
            "remediation": "Submit requested documentation within payer's timeframe (typically 30-45 days). Include cover letter referencing original claim.",
            "appeal_template": "Requested documentation attached: [list documents]. Original claim reference: [claim number].",
            "success_rate": 0.85,
            "typical_payers": ["all"],
        },
        {
            "category": "documentation",
            "carc_code": "226",
            "denial_reason": "Information requested from provider not received",
            "trigger_patterns": {},
            "remediation": "Verify request was received. Submit information promptly via secure method with confirmation of receipt.",
            "appeal_template": "Requested information was not received at this office. Information now attached. Request reconsideration.",
            "success_rate": 0.75,
            "typical_payers": ["all"],
        },
        {
            "category": "documentation",
            "carc_code": "16",
            "denial_reason": "Claim lacks required information - cannot process",
            "trigger_patterns": {},
            "remediation": "Review rejection reason code for specific missing element. Correct and resubmit complete claim.",
            "appeal_template": "Corrected claim submitted with all required information. Missing element [field] has been added.",
            "success_rate": 0.90,
            "typical_payers": ["all"],
        },
    ]

    DENIAL_KNOWLEDGE.extend(entries)


def add_bundling_denials():
    """Add denials related to service bundling."""

    entries = [
        {
            "category": "bundling",
            "carc_code": "97",
            "denial_reason": "Service included in payment for primary procedure per NCCI edits",
            "trigger_patterns": {
                "procedure_codes": ["99213", "36415"],  # Office visit + venipuncture
            },
            "remediation": "Review CCI edits. If services are separately identifiable and documented, use appropriate modifier (59, XE, XP, XS, XU).",
            "appeal_template": "Services were distinct and separately identifiable. [Procedure] was performed at a different anatomic site/session/encounter.",
            "success_rate": 0.50,
            "typical_payers": ["all"],
        },
        {
            "category": "bundling",
            "carc_code": "97",
            "denial_reason": "Global surgical package - service included in surgical payment",
            "trigger_patterns": {
                "procedure_codes": ["99213"],  # Post-op visit within global period
            },
            "remediation": "Verify service is outside global period or use modifier 24 (unrelated E/M during postoperative period) or 25 (significant, separately identifiable E/M).",
            "appeal_template": "E/M service on [date] was for condition unrelated to [surgery] performed on [date]. Modifier 24 appropriately indicates unrelated service.",
            "success_rate": 0.65,
            "typical_payers": ["all"],
        },
    ]

    DENIAL_KNOWLEDGE.extend(entries)


def add_benefit_maximum_denials():
    """Add denials related to benefit limits."""

    entries = [
        {
            "category": "benefit_maximum",
            "carc_code": "119",
            "denial_reason": "Annual or lifetime benefit maximum reached",
            "trigger_patterns": {
                "procedure_codes": ["97110", "97140", "97530"],  # PT services
            },
            "remediation": "Verify remaining benefits. Request exception for additional coverage due to medical necessity. Consider alternative payment arrangements.",
            "appeal_template": "Request benefit exception. Patient requires continued treatment due to [medical necessity]. Documentation demonstrates ongoing progress toward functional goals.",
            "success_rate": 0.35,
            "typical_payers": ["all"],
        },
        {
            "category": "benefit_maximum",
            "carc_code": "35",
            "denial_reason": "Lifetime maximum benefit has been reached",
            "trigger_patterns": {},
            "remediation": "Inform patient of lifetime max. Explore other coverage options, charity care programs, or payment plans.",
            "appeal_template": "Request exception to lifetime maximum. Patient's condition is [unique circumstance]. No alternative treatment options exist.",
            "success_rate": 0.15,
            "typical_payers": ["all"],
        },
    ]

    DENIAL_KNOWLEDGE.extend(entries)


def enrich_with_embeddings_placeholder(entries: List[Dict]) -> List[Dict]:
    """Add placeholder for embedding field - will be computed during system initialization."""
    for entry in entries:
        entry["id"] = str(uuid.uuid4())
        entry["created_at"] = datetime.now().isoformat()
        entry["embedding"] = None  # Will be computed by embedding service
        entry["embedding_text"] = f"{entry['category']} {entry['denial_reason']} {entry.get('remediation', '')}"
    return entries


def main():
    print("Generating denial knowledge base...")

    # Build knowledge base
    add_medical_necessity_denials()
    add_prior_auth_denials()
    add_coding_error_denials()
    add_duplicate_denials()
    add_timely_filing_denials()
    add_coverage_denials()
    add_documentation_denials()
    add_bundling_denials()
    add_benefit_maximum_denials()

    print(f"Generated {len(DENIAL_KNOWLEDGE)} denial knowledge entries")

    # Add IDs and embedding placeholders
    entries = enrich_with_embeddings_placeholder(DENIAL_KNOWLEDGE)

    # Count by category
    from collections import Counter
    categories = Counter(e["category"] for e in entries)
    print("\nEntries by category:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")

    # Save to files
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Save all entries
    with open(OUTPUT_DIR / "_all_denials.json", 'w') as f:
        json.dump(entries, f, indent=2)

    # Save individual entries by category
    for category in categories:
        cat_entries = [e for e in entries if e["category"] == category]
        with open(OUTPUT_DIR / f"{category}.json", 'w') as f:
            json.dump(cat_entries, f, indent=2)

    print(f"\nSaved to {OUTPUT_DIR}")

    # Show sample
    print("\nSample entry:")
    print(json.dumps(entries[0], indent=2))


if __name__ == "__main__":
    main()
