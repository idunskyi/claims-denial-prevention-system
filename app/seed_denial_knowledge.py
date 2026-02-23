#!/usr/bin/env python
"""
Seed Denial Knowledge Base - Docker-compatible version

This script runs inside the Docker container and seeds the denial knowledge base.
The denial knowledge data is embedded directly in the script to avoid mounting issues.

Usage (from host):
    docker exec launchpad-launchpad-api python seed_denial_knowledge.py
"""

import logging
from contextlib import contextmanager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from database.session import db_session
from database.denial_knowledge import DenialKnowledge
from database.denial_knowledge_repository import DenialKnowledgeRepository
from services.embedding_service import EmbeddingService

# Denial knowledge data - embedded to avoid file mounting issues
DENIAL_KNOWLEDGE_DATA = [
    {
        "category": "prior_authorization",
        "carc_code": "197",
        "denial_reason": "Precertification/authorization/notification absent",
        "trigger_patterns": {
            "procedure_flags": ["prior_auth_required", "experimental_treatment"],
            "high_risk_cpt": ["27447", "27130", "63030", "27446"],
            "payer_specific": ["United", "Aetna", "Cigna"]
        },
        "remediation": "Obtain prior authorization before procedure. For retrospective cases: 1) Gather clinical documentation supporting medical necessity, 2) Submit retrospective auth request within 72 hours of service, 3) Include peer-reviewed literature for experimental treatments",
        "appeal_template": "We are writing to appeal the denial of claim [CLAIM_ID] for [PROCEDURE]. Prior authorization was [not obtained/obtained but not on file] due to [REASON]. We have attached: 1) Medical records demonstrating necessity, 2) Retrospective authorization request, 3) Supporting clinical documentation.",
        "success_rate": 0.65,
        "typical_payers": ["United Healthcare", "Aetna", "Cigna", "Blue Cross Blue Shield"],
        "embedding_text": "Prior authorization denial - Precertification authorization notification absent. High risk for surgeries like knee replacement hip replacement spinal procedures. Required for United Aetna Cigna. Prevention: obtain auth before procedure."
    },
    {
        "category": "prior_authorization",
        "carc_code": "15",
        "denial_reason": "Authorization number is missing/invalid or does not apply to billed services",
        "trigger_patterns": {
            "procedure_flags": ["auth_number_missing", "auth_expired"],
            "high_risk_cpt": ["all_surgical"],
            "payer_specific": ["Medicare Advantage", "Medicaid MCO"]
        },
        "remediation": "Verify authorization number validity before claim submission. Check: 1) Auth number matches procedure codes, 2) Auth date range covers service date, 3) Auth units not exceeded",
        "appeal_template": "This letter appeals the denial for missing/invalid authorization. The valid authorization number is [AUTH_NUM] dated [DATE]. Please see attached authorization confirmation.",
        "success_rate": 0.78,
        "typical_payers": ["Medicare Advantage plans", "Medicaid MCOs"],
        "embedding_text": "Authorization number missing invalid expired prior auth. Check auth matches procedure codes dates units. Medicare Advantage Medicaid MCO high risk."
    },
    {
        "category": "prior_authorization",
        "carc_code": "177",
        "denial_reason": "Patient has not met the required eligibility requirements for this service",
        "trigger_patterns": {
            "procedure_flags": ["step_therapy_required", "conservative_treatment_first"],
            "high_risk_cpt": ["27447", "27130", "20610"],
            "payer_specific": ["all"]
        },
        "remediation": "Document completion of step therapy or conservative treatment. Include: 1) Timeline of previous treatments, 2) Outcomes of conservative measures, 3) Clinical rationale for escalation",
        "appeal_template": "Patient has completed required step therapy including [TREATMENTS] over [TIMEFRAME]. Conservative treatment was inadequate due to [CLINICAL FINDINGS]. Documentation attached.",
        "success_rate": 0.55,
        "typical_payers": ["All commercial payers"],
        "embedding_text": "Eligibility requirements not met step therapy conservative treatment required first. Document previous treatments outcomes clinical rationale for procedure."
    },
    {
        "category": "medical_necessity",
        "carc_code": "50",
        "denial_reason": "These are non-covered services because this is not deemed a medical necessity",
        "trigger_patterns": {
            "diagnosis_mismatch": True,
            "procedure_flags": ["elective", "cosmetic_potential"],
            "documentation_flags": ["insufficient_clinical_notes"]
        },
        "remediation": "Strengthen documentation: 1) Link diagnosis to procedure with clinical evidence, 2) Include functional limitations, 3) Document failed conservative treatments, 4) Add peer-reviewed support for unusual cases",
        "appeal_template": "We appeal this denial based on documented medical necessity. The patient's condition [DIAGNOSIS] requires [PROCEDURE] because [CLINICAL RATIONALE]. Conservative treatments including [TREATMENTS] have failed. See attached clinical documentation.",
        "success_rate": 0.52,
        "typical_payers": ["All payers"],
        "embedding_text": "Medical necessity denial non-covered service elective cosmetic. Strengthen documentation link diagnosis procedure clinical evidence functional limitations failed treatments."
    },
    {
        "category": "medical_necessity",
        "carc_code": "56",
        "denial_reason": "Procedure/treatment has not been deemed medically reasonable and necessary",
        "trigger_patterns": {
            "procedure_flags": ["experimental", "off_label"],
            "diagnosis_flags": ["uncommon_pairing"],
            "frequency_flags": ["excessive_units"]
        },
        "remediation": "Provide peer-reviewed evidence supporting treatment. Include: 1) Published clinical studies, 2) Specialty society guidelines, 3) Expert opinion letters if needed",
        "appeal_template": "This treatment is medically necessary per enclosed peer-reviewed literature and specialty guidelines. The procedure is standard of care for [CONDITION].",
        "success_rate": 0.48,
        "typical_payers": ["All payers"],
        "embedding_text": "Treatment not medically reasonable necessary experimental off-label. Provide peer-reviewed evidence clinical studies specialty guidelines expert opinions."
    },
    {
        "category": "medical_necessity",
        "carc_code": "151",
        "denial_reason": "Payment adjusted because the payer deems the information submitted does not support this level of service",
        "trigger_patterns": {
            "procedure_flags": ["higher_level_coded"],
            "documentation_flags": ["supports_lower_level"],
            "em_codes": ["99214", "99215", "99223", "99233"]
        },
        "remediation": "Ensure documentation supports the level billed. Include: 1) Complete HPI, 2) Comprehensive exam findings, 3) Complex medical decision making elements, 4) Time documentation if applicable",
        "appeal_template": "Documentation supports the level billed based on [COMPLEXITY/TIME]. Key elements include: [LIST KEY DOCUMENTATION POINTS].",
        "success_rate": 0.61,
        "typical_payers": ["All payers"],
        "embedding_text": "Level of service not supported documentation insufficient E/M coding. Include complete HPI exam findings medical decision making time documentation."
    },
    {
        "category": "medical_necessity",
        "carc_code": "58",
        "denial_reason": "Treatment was deemed by the payer to have been rendered in an inappropriate or invalid place of service",
        "trigger_patterns": {
            "pos_flags": ["inpatient_billed_outpatient", "hospital_billed_office"],
            "procedure_flags": ["same_day_discharge_expected"]
        },
        "remediation": "Justify place of service with clinical documentation: 1) Patient acuity level, 2) Monitoring requirements, 3) Complication risk factors",
        "appeal_template": "The place of service was appropriate because [CLINICAL JUSTIFICATION]. Patient required [LEVEL OF CARE] due to [RISK FACTORS].",
        "success_rate": 0.55,
        "typical_payers": ["All payers"],
        "embedding_text": "Place of service invalid inappropriate inpatient outpatient. Justify with patient acuity monitoring requirements complication risk factors."
    },
    {
        "category": "coding_error",
        "carc_code": "4",
        "denial_reason": "The procedure code is inconsistent with the modifier used",
        "trigger_patterns": {
            "modifier_flags": ["bilateral_missing", "incorrect_laterality"],
            "procedure_flags": ["requires_modifier"]
        },
        "remediation": "Review modifier guidelines: 1) Verify laterality (RT/LT/50), 2) Check professional vs technical (26/TC), 3) Confirm multiple procedure rules (-59, -XE, -XS, -XP, -XU)",
        "appeal_template": "We are correcting the modifier to [CORRECT_MODIFIER] per [CODING GUIDELINE]. Corrected claim attached.",
        "success_rate": 0.85,
        "typical_payers": ["All payers"],
        "embedding_text": "Modifier inconsistent incorrect missing bilateral laterality RT LT 50. Review modifier guidelines professional technical multiple procedure rules."
    },
    {
        "category": "coding_error",
        "carc_code": "5",
        "denial_reason": "The procedure code/bill type is inconsistent with the place of service",
        "trigger_patterns": {
            "pos_flags": ["mismatch_detected"],
            "bill_type_flags": ["facility_vs_professional"]
        },
        "remediation": "Verify: 1) POS code matches where service rendered, 2) Bill type appropriate for facility type, 3) Facility vs professional billing rules followed",
        "appeal_template": "Service was rendered at [LOCATION] which corresponds to POS [CODE]. Corrected claim with appropriate POS/bill type attached.",
        "success_rate": 0.88,
        "typical_payers": ["All payers"],
        "embedding_text": "Procedure code bill type inconsistent place of service POS mismatch facility professional billing."
    },
    {
        "category": "coding_error",
        "carc_code": "6",
        "denial_reason": "The procedure/revenue code is inconsistent with the patient's age",
        "trigger_patterns": {
            "age_flags": ["pediatric_code_adult", "adult_code_pediatric"],
            "procedure_flags": ["age_specific"]
        },
        "remediation": "Use age-appropriate codes. For pediatric: verify developmental stage coding. For geriatric: confirm age-specific modifiers/codes",
        "appeal_template": "Patient age at DOS was [AGE]. Corrected to age-appropriate code [CODE].",
        "success_rate": 0.90,
        "typical_payers": ["All payers"],
        "embedding_text": "Procedure code inconsistent patient age pediatric adult geriatric age-specific codes."
    },
    {
        "category": "coding_error",
        "carc_code": "16",
        "denial_reason": "Claim/service lacks information needed for adjudication",
        "trigger_patterns": {
            "missing_fields": ["npi", "diagnosis_pointer", "service_date", "units"]
        },
        "remediation": "Complete all required fields: NPI, diagnosis codes linked to procedures, exact service dates, correct units",
        "appeal_template": "Resubmitting with complete information. Previously missing [FIELD] now included.",
        "success_rate": 0.92,
        "typical_payers": ["All payers"],
        "embedding_text": "Claim lacks information adjudication missing NPI diagnosis pointer service date units incomplete."
    },
    {
        "category": "coding_error",
        "carc_code": "11",
        "denial_reason": "The diagnosis is inconsistent with the procedure",
        "trigger_patterns": {
            "diagnosis_procedure_mismatch": True,
            "lcd_ncd_flags": ["not_covered_for_diagnosis"]
        },
        "remediation": "Verify diagnosis supports procedure per LCD/NCD guidelines. Add additional diagnoses that justify medical necessity",
        "appeal_template": "Diagnosis [ICD10] supports [PROCEDURE] per [LCD/NCD reference]. Additional supporting diagnosis: [SECONDARY DX].",
        "success_rate": 0.75,
        "typical_payers": ["Medicare", "Medicaid"],
        "embedding_text": "Diagnosis inconsistent procedure ICD-10 CPT mismatch LCD NCD coverage guidelines."
    },
    {
        "category": "duplicate",
        "carc_code": "18",
        "denial_reason": "Exact duplicate claim/service",
        "trigger_patterns": {
            "submission_flags": ["same_dos_same_cpt", "multiple_submissions"]
        },
        "remediation": "Before resubmitting: 1) Verify original claim status, 2) If truly duplicate, withdraw one, 3) If distinct services, add modifier -76 or -77",
        "appeal_template": "This is not a duplicate. Services are distinct because [REASON]. See documentation of separate [ENCOUNTERS/PROCEDURES].",
        "success_rate": 0.70,
        "typical_payers": ["All payers"],
        "embedding_text": "Duplicate claim service same date same code. Verify original status use modifier 76 77 for repeat procedures."
    },
    {
        "category": "duplicate",
        "carc_code": "19",
        "denial_reason": "This is a work-related injury/illness and should be billed to Workers Compensation",
        "trigger_patterns": {
            "coordination_flags": ["workers_comp_indicator", "injury_codes"]
        },
        "remediation": "Verify correct payer. If not work-related, document with employer statement. If WC, bill appropriate WC carrier",
        "appeal_template": "This is not a work-related injury. Patient statement attached confirming injury occurred [OUTSIDE OF WORK]. Please process under medical insurance.",
        "success_rate": 0.60,
        "typical_payers": ["All payers"],
        "embedding_text": "Workers compensation work-related injury illness coordination of benefits COB payer routing."
    },
    {
        "category": "timely_filing",
        "carc_code": "29",
        "denial_reason": "The time limit for filing has expired",
        "trigger_patterns": {
            "timing_flags": ["beyond_filing_limit"],
            "payer_limits": {"Medicare": 365, "Medicaid": 365, "Commercial": "varies"}
        },
        "remediation": "Know payer deadlines. For late claims: 1) Document reason for delay, 2) Check if exceptions apply (provider enrollment issues, prior claim pending), 3) Some states mandate minimum filing periods",
        "appeal_template": "Timely filing exception applies because [REASON: prior claim pending/enrollment issue/payer error]. Original submission date was [DATE].",
        "success_rate": 0.35,
        "typical_payers": ["All payers"],
        "embedding_text": "Timely filing deadline expired late submission. Know payer deadlines exceptions enrollment issues prior claim pending."
    },
    {
        "category": "bundling",
        "carc_code": "97",
        "denial_reason": "The benefit for this service is included in the payment/allowance for another service",
        "trigger_patterns": {
            "bundling_flags": ["cci_edit", "component_of_primary"],
            "procedure_flags": ["commonly_bundled"]
        },
        "remediation": "Check CCI edits before billing. Use modifier -59 or X modifiers only when truly distinct service at different site/session",
        "appeal_template": "Service is separately billable because [DISTINCT SESSION/SITE/INDICATION]. Documentation shows [SEPARATE ENCOUNTER DETAILS].",
        "success_rate": 0.55,
        "typical_payers": ["Medicare", "Commercial"],
        "embedding_text": "Bundling benefit included another service CCI edits component procedure modifier 59 X modifiers distinct."
    },
    {
        "category": "bundling",
        "carc_code": "234",
        "denial_reason": "This procedure is not paid separately",
        "trigger_patterns": {
            "bundling_flags": ["global_period", "incidental_procedure"],
            "procedure_flags": ["minor_with_major"]
        },
        "remediation": "Review global surgery rules. Separate procedures only billable if truly distinct with modifier -59/X{EPSU} and documented separately",
        "appeal_template": "Procedure was performed at a separate site/session per documentation. Not incidental to primary procedure because [REASON].",
        "success_rate": 0.45,
        "typical_payers": ["All payers"],
        "embedding_text": "Procedure not paid separately global period incidental minor with major surgery bundling rules."
    },
    {
        "category": "documentation",
        "carc_code": "31",
        "denial_reason": "Requested information was not provided or was insufficient/incomplete",
        "trigger_patterns": {
            "documentation_flags": ["medical_records_requested", "incomplete_submission"]
        },
        "remediation": "Respond to all documentation requests within deadline. Include: complete operative reports, progress notes, diagnostic results supporting necessity",
        "appeal_template": "Requested documentation attached: [LIST DOCUMENTS]. This information supports medical necessity and proper coding.",
        "success_rate": 0.72,
        "typical_payers": ["All payers"],
        "embedding_text": "Information not provided insufficient incomplete medical records documentation request respond deadline."
    },
    {
        "category": "documentation",
        "carc_code": "32",
        "denial_reason": "Our records indicate that this service was previously paid",
        "trigger_patterns": {
            "documentation_flags": ["prior_payment_found"],
            "claim_flags": ["correction_needed"]
        },
        "remediation": "Verify: 1) Not true duplicate, 2) If adjusting, submit corrected claim format, 3) If additional service, document distinctness",
        "appeal_template": "This is a corrected claim/distinct service from prior payment dated [DATE]. Difference is: [EXPLANATION].",
        "success_rate": 0.60,
        "typical_payers": ["All payers"],
        "embedding_text": "Previously paid duplicate payment corrected claim adjustment distinct service."
    },
    {
        "category": "documentation",
        "carc_code": "252",
        "denial_reason": "An attachment/other documentation is required to adjudicate this claim",
        "trigger_patterns": {
            "attachment_flags": ["operative_report_required", "medical_necessity_docs"]
        },
        "remediation": "Submit required attachments: operative reports, pathology, medical necessity letters. Use appropriate PWK segments or attachment control numbers",
        "appeal_template": "Required documentation now attached: [LIST]. PWK/attachment reference: [NUMBER].",
        "success_rate": 0.80,
        "typical_payers": ["All payers"],
        "embedding_text": "Attachment documentation required adjudicate operative report medical necessity PWK attachment control number."
    },
    {
        "category": "non_covered_service",
        "carc_code": "96",
        "denial_reason": "Non-covered charge(s). These are charges for a service or procedure not covered by the health plan",
        "trigger_patterns": {
            "coverage_flags": ["not_in_benefits", "excluded_service"],
            "procedure_flags": ["cosmetic", "experimental"]
        },
        "remediation": "Verify coverage before service. For medical exceptions: obtain prior approval with clinical documentation supporting necessity despite exclusion",
        "appeal_template": "Although typically excluded, this service is medically necessary because [CLINICAL REASON]. This is not [COSMETIC/EXPERIMENTAL] because [EXPLANATION].",
        "success_rate": 0.25,
        "typical_payers": ["All payers"],
        "embedding_text": "Non-covered service charge not covered health plan excluded cosmetic experimental benefit exclusion."
    },
    {
        "category": "non_covered_service",
        "carc_code": "119",
        "denial_reason": "Benefit maximum for this time period has been reached",
        "trigger_patterns": {
            "benefit_flags": ["annual_max_reached", "lifetime_max"],
            "service_types": ["therapy", "mental_health", "substance_abuse"]
        },
        "remediation": "Track benefit usage. For exceeded maximums: 1) Request medical exception, 2) Document continued medical necessity, 3) Consider alternate funding sources",
        "appeal_template": "Medical exception requested. Continued treatment necessary because [CLINICAL REASON]. Stopping would result in [ADVERSE OUTCOME].",
        "success_rate": 0.30,
        "typical_payers": ["All payers"],
        "embedding_text": "Benefit maximum reached annual lifetime limit therapy mental health exception medical necessity."
    },
    {
        "category": "benefit_maximum",
        "carc_code": "119",
        "denial_reason": "Benefit maximum for this time period or occurrence has been reached",
        "trigger_patterns": {
            "benefit_flags": ["limit_reached"],
            "service_types": ["PT", "OT", "chiropractic", "mental_health"]
        },
        "remediation": "Monitor benefit usage proactively. For limit reached: request exception with documentation of medical necessity and potential harm if services stopped",
        "appeal_template": "Exception to benefit maximum requested due to [CONDITION]. Documentation shows continued need: [CLINICAL FINDINGS]. Without treatment: [PROGNOSIS].",
        "success_rate": 0.40,
        "typical_payers": ["All payers"],
        "embedding_text": "Benefit maximum limit reached PT OT chiropractic mental health visits units exception medical necessity."
    },
    {
        "category": "coverage_terminated",
        "carc_code": "27",
        "denial_reason": "Expenses incurred after coverage terminated",
        "trigger_patterns": {
            "eligibility_flags": ["termed_member", "no_coverage_dos"]
        },
        "remediation": "Verify eligibility before every service. If coverage disputed: 1) Check for retroactive eligibility, 2) Verify COBRA continuation, 3) Check for secondary coverage",
        "appeal_template": "Patient had active coverage on [DOS]. See attached eligibility confirmation/COBRA documentation.",
        "success_rate": 0.55,
        "typical_payers": ["All payers"],
        "embedding_text": "Coverage terminated expenses after termination eligibility ended COBRA continuation secondary coverage."
    },
    {
        "category": "coverage_terminated",
        "carc_code": "26",
        "denial_reason": "Expenses incurred prior to coverage",
        "trigger_patterns": {
            "eligibility_flags": ["coverage_not_effective", "waiting_period"]
        },
        "remediation": "Verify effective date before service. If disputed: check enrollment records, premium payment history",
        "appeal_template": "Coverage was effective [DATE], prior to service date. See attached enrollment confirmation.",
        "success_rate": 0.50,
        "typical_payers": ["All payers"],
        "embedding_text": "Expenses prior to coverage effective date waiting period enrollment not active."
    },
    {
        "category": "out_of_network",
        "carc_code": "B7",
        "denial_reason": "This provider was not certified for this procedure/service on the date of service",
        "trigger_patterns": {
            "network_flags": ["out_of_network", "non_participating"],
            "procedure_flags": ["network_required"]
        },
        "remediation": "For OON services: 1) Document network inadequacy if applicable, 2) Emergency exception if urgent, 3) Patient consent for balance billing where allowed",
        "appeal_template": "Network exception applies because: [NO IN-NETWORK PROVIDER AVAILABLE/EMERGENCY/CONTINUITY OF CARE]. Documentation attached.",
        "success_rate": 0.35,
        "typical_payers": ["HMO plans", "EPO plans"],
        "embedding_text": "Out of network non-participating provider not certified network inadequacy emergency exception balance billing."
    },
    {
        "category": "out_of_network",
        "carc_code": "B9",
        "denial_reason": "Patient is enrolled in a managed care plan that does not cover out-of-network services",
        "trigger_patterns": {
            "network_flags": ["hmo_oon", "closed_network"],
            "emergency_flags": ["not_emergency"]
        },
        "remediation": "For HMO OON: limited to emergency or network gap exception. Document: 1) Emergency nature of service, 2) No in-network option within reasonable distance, 3) PCP referral if obtained",
        "appeal_template": "Service provided as [EMERGENCY/NETWORK GAP]. Nearest in-network provider was [DISTANCE] away. Patient condition required immediate treatment.",
        "success_rate": 0.30,
        "typical_payers": ["HMO plans"],
        "embedding_text": "Managed care HMO out of network closed network emergency exception network gap referral required."
    },
    {
        "category": "coordination_of_benefits",
        "carc_code": "22",
        "denial_reason": "This care may be covered by another payer per coordination of benefits",
        "trigger_patterns": {
            "cob_flags": ["other_insurance_indicated", "primary_not_billed"]
        },
        "remediation": "Determine correct payment order: 1) Birthday rule for dependents, 2) Active vs COBRA, 3) Medicare Secondary Payer rules. Bill primary first.",
        "appeal_template": "This payer is primary per [COB RULE]. Other coverage is [SECONDARY/NONE]. EOB from [OTHER PAYER] attached if applicable.",
        "success_rate": 0.65,
        "typical_payers": ["All payers"],
        "embedding_text": "Coordination of benefits COB other insurance primary secondary birthday rule Medicare Secondary Payer."
    },
    {
        "category": "coordination_of_benefits",
        "carc_code": "23",
        "denial_reason": "Payment adjusted due to other insurance",
        "trigger_patterns": {
            "cob_flags": ["secondary_payment_adjusted", "primary_eob_required"]
        },
        "remediation": "Submit primary payer EOB with secondary claim. Ensure: 1) Correct COB order, 2) Primary EOB matches claim, 3) Timely secondary filing",
        "appeal_template": "Primary EOB attached showing payment of [AMOUNT]. Secondary payment requested for remaining patient responsibility.",
        "success_rate": 0.70,
        "typical_payers": ["All payers"],
        "embedding_text": "Payment adjusted other insurance primary EOB secondary claim COB coordination."
    },
    {
        "category": "medical_necessity",
        "carc_code": "55",
        "denial_reason": "Procedure/treatment is deemed investigational/experimental",
        "trigger_patterns": {
            "procedure_flags": ["investigational", "not_fda_approved", "clinical_trial"],
            "coverage_flags": ["experimental_exclusion"]
        },
        "remediation": "For experimental treatments: 1) Provide FDA status if approved, 2) Include clinical trial coverage if applicable, 3) Submit published literature showing efficacy, 4) Obtain prior approval for clinical trials",
        "appeal_template": "Treatment is not experimental because: [FDA APPROVAL/STANDARD OF CARE EVIDENCE]. Supporting literature and guidelines attached.",
        "success_rate": 0.40,
        "typical_payers": ["All payers"],
        "embedding_text": "Investigational experimental treatment FDA approval clinical trial published literature standard of care evidence."
    }
]


def seed_knowledge_base():
    """Seed the denial knowledge base with embeddings."""
    embedding_service = EmbeddingService()

    with contextmanager(db_session)() as session:
        repository = DenialKnowledgeRepository(session)
        current_count = repository.count()
        logger.info(f"Current denial knowledge entries: {current_count}")

        if current_count > 0:
            logger.info("Clearing existing entries...")
            repository.clear_all()
            logger.info("Cleared existing entries")

    logger.info(f"Generating embeddings for {len(DENIAL_KNOWLEDGE_DATA)} entries...")

    embedding_texts = [e.get("embedding_text", "") for e in DENIAL_KNOWLEDGE_DATA]
    embeddings = []

    batch_size = 10
    for i in range(0, len(embedding_texts), batch_size):
        batch = embedding_texts[i:i + batch_size]
        logger.info(f"  Processing batch {i // batch_size + 1}/{(len(embedding_texts) + batch_size - 1) // batch_size}")
        try:
            batch_embeddings = embedding_service.embed_texts(batch)
            embeddings.extend(batch_embeddings)
        except Exception as e:
            logger.error(f"  Error generating embeddings for batch: {e}")
            embeddings.extend([[0.0] * 1536 for _ in batch])

    logger.info(f"Generated {len(embeddings)} embeddings")

    logger.info("Storing entries in database...")
    stored = 0

    with contextmanager(db_session)() as session:
        repository = DenialKnowledgeRepository(session)

        for entry, embedding in zip(DENIAL_KNOWLEDGE_DATA, embeddings):
            try:
                repository.create(
                    DenialKnowledge(
                        category=entry.get("category"),
                        carc_code=entry.get("carc_code"),
                        denial_reason=entry.get("denial_reason"),
                        trigger_patterns=entry.get("trigger_patterns"),
                        remediation=entry.get("remediation"),
                        appeal_template=entry.get("appeal_template"),
                        success_rate=entry.get("success_rate"),
                        typical_payers=entry.get("typical_payers"),
                        embedding_text=entry.get("embedding_text"),
                    ),
                    embedding=embedding
                )
                stored += 1
            except Exception as e:
                logger.error(f"  Error storing entry: {e}")

    logger.info(f"Successfully stored {stored}/{len(DENIAL_KNOWLEDGE_DATA)} entries")
    return stored


def verify_seeding():
    """Verify with a test query."""
    logger.info("Verifying with test query...")

    embedding_service = EmbeddingService()
    test_query = "Missing prior authorization for surgical procedure"
    query_embedding = embedding_service.embed_text(test_query)

    with contextmanager(db_session)() as session:
        repository = DenialKnowledgeRepository(session)
        count = repository.count()
        logger.info(f"Total entries: {count}")

        results = repository.search_similar(query_embedding=query_embedding, top_k=3)

        if results:
            logger.info(f"Test query: '{test_query}'")
            logger.info(f"Found {len(results)} similar entries:")
            for i, result in enumerate(results, 1):
                logger.info(f"  {i}. [{result['category']}] {result['denial_reason'][:60]}...")
                logger.info(f"     Similarity: {result['similarity']:.2f}")
        else:
            logger.warning("No results found!")


def main():
    logger.info("=" * 60)
    logger.info("DENIAL KNOWLEDGE BASE SEEDING")
    logger.info("=" * 60)

    seed_knowledge_base()
    verify_seeding()

    logger.info("=" * 60)
    logger.info("SEEDING COMPLETE")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
