"""
Extract and transform claims from Synthea FHIR bundles into a simplified format.
This creates format-agnostic claim records suitable for the denial prevention PoC.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import random

# Paths
SYNTHEA_FILE = Path(__file__).parent.parent.parent / "requests/events/Lorriane838_Illa976_Lebsack687_55087eb9-d0fe-bcab-4b86-5b8ea0c45077.json"
OUTPUT_DIR = Path(__file__).parent.parent.parent / "requests/denial_prevention/claims"

# SNOMED to CPT/ICD mapping (simplified - in production would use a proper terminology service)
SNOMED_TO_CPT = {
    "162673000": "99213",  # General examination -> Office visit
    "430193006": "99214",  # Medication reconciliation -> Office visit detailed
    "710824005": "99406",  # Assessment of health risks -> Counseling
    "428211000124100": "99497",  # Assessment of substance use -> Advance care planning
    "763302001": "99395",  # Counseling for risk -> Preventive visit
    "225358003": "99213",  # Wound care -> Office visit
    "76601001": "93000",   # ECG -> Electrocardiogram
    "252160004": "36415",  # Blood test -> Venipuncture
    "167271000": "80053",  # Serum chemistry -> Comprehensive metabolic panel
    "82078001": "36415",   # Blood collection -> Venipuncture
    "43789009": "71046",   # Chest X-ray -> Chest X-ray
    "169553002": "99385",  # Breast exam -> Preventive visit
    "24623002": "81025",   # Urinalysis -> Urine pregnancy test
    "268556000": "G0101",  # Pelvic exam -> Screening pelvic exam
    "117010004": "87491",  # Urine culture -> Chlamydia test
    "34896006": "90471",   # Immunization -> Immunization admin
    "308335008": "99213",  # Patient encounter -> Office visit
    "410620009": "99283",  # Well child visit -> ED visit
    "185349003": "99213",  # Encounter for check up -> Office visit
    "390906007": "99212",  # Follow-up encounter -> Office visit brief
    "699134002": "G0439",  # Annual wellness visit -> AWV
}

# Common payer names for variety
PAYERS = ["Blue Cross Blue Shield", "Aetna", "UnitedHealthcare", "Cigna", "Medicare", "Medicaid", "Humana"]

# Facility types
FACILITY_TYPES = ["outpatient", "inpatient", "emergency", "ambulatory", "office"]


def load_synthea_bundle(file_path: Path) -> Dict:
    """Load a Synthea FHIR bundle."""
    with open(file_path, 'r') as f:
        return json.load(f)


def extract_resources_by_type(bundle: Dict) -> Dict[str, List[Dict]]:
    """Index all resources by their type for easy lookup."""
    resources = {}
    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        resource_type = resource.get("resourceType")
        if resource_type:
            if resource_type not in resources:
                resources[resource_type] = []
            resources[resource_type].append(resource)
    return resources


def get_diagnosis_codes(claim: Dict, resources: Dict) -> List[Dict[str, str]]:
    """Extract diagnosis codes from a claim, looking up the actual condition."""
    diagnoses = []
    for diag in claim.get("diagnosis", []):
        diag_ref = diag.get("diagnosisReference", {}).get("reference", "")

        # Look up the actual condition
        condition_id = diag_ref.replace("urn:uuid:", "")
        for condition in resources.get("Condition", []):
            if condition.get("id") == condition_id:
                code_info = condition.get("code", {}).get("coding", [{}])[0]
                diagnoses.append({
                    "code": code_info.get("code", ""),
                    "system": "SNOMED" if "snomed" in code_info.get("system", "").lower() else "ICD-10",
                    "display": code_info.get("display", "")
                })
                break

    # If no diagnoses found via reference, try inline
    if not diagnoses:
        for diag in claim.get("diagnosis", []):
            if "diagnosisCodeableConcept" in diag:
                code_info = diag["diagnosisCodeableConcept"].get("coding", [{}])[0]
                diagnoses.append({
                    "code": code_info.get("code", ""),
                    "system": "SNOMED" if "snomed" in code_info.get("system", "").lower() else "ICD-10",
                    "display": code_info.get("display", "")
                })

    return diagnoses


def get_procedure_codes(claim: Dict) -> List[Dict[str, str]]:
    """Extract procedure codes from claim items."""
    procedures = []
    for item in claim.get("item", []):
        product = item.get("productOrService", {})
        coding = product.get("coding", [{}])[0]

        snomed_code = coding.get("code", "")
        display = coding.get("display", product.get("text", ""))

        # Map SNOMED to CPT where possible
        cpt_code = SNOMED_TO_CPT.get(snomed_code, snomed_code)

        procedures.append({
            "code": cpt_code,
            "original_code": snomed_code,
            "system": "CPT" if cpt_code != snomed_code else "SNOMED",
            "display": display
        })

    return procedures


def transform_claim(claim: Dict, resources: Dict, patient: Dict) -> Dict[str, Any]:
    """Transform a FHIR Claim into our simplified format."""

    # Parse dates
    billable_period = claim.get("billablePeriod", {})
    service_date = billable_period.get("start", claim.get("created", ""))

    # Get provider info
    provider = claim.get("provider", {})
    facility = claim.get("facility", {})

    # Get insurance info
    insurance = claim.get("insurance", [{}])[0]
    payer_name = insurance.get("coverage", {}).get("display", random.choice(PAYERS))

    # Determine facility type based on claim type
    claim_type = claim.get("type", {}).get("coding", [{}])[0].get("code", "professional")
    facility_type = "inpatient" if claim_type == "institutional" else "outpatient"

    # Get total amount
    total = claim.get("total", {})
    amount = total.get("value", random.uniform(100, 5000))

    # Build simplified claim
    return {
        "claim_id": str(uuid.uuid4()),
        "original_fhir_id": claim.get("id", ""),
        "timestamp": datetime.now().isoformat(),

        # Patient info (de-identified)
        "patient_id": patient.get("id", "")[:8] + "..." ,  # Truncated for privacy
        "patient_age": calculate_age(patient.get("birthDate", "1970-01-01")),
        "patient_gender": patient.get("gender", "unknown"),

        # Provider info
        "provider_name": provider.get("display", "Unknown Provider"),
        "provider_npi": "1234567890",  # Synthetic NPI
        "facility_name": facility.get("display", provider.get("display", "Unknown Facility")),
        "facility_type": facility_type,

        # Dates
        "service_date": service_date[:10] if service_date else "2024-01-01",
        "submission_date": datetime.now().strftime("%Y-%m-%d"),

        # Clinical codes
        "diagnosis_codes": get_diagnosis_codes(claim, resources),
        "procedure_codes": get_procedure_codes(claim),

        # Modifiers (empty for now - would come from real claims)
        "modifiers": [],

        # Place of service
        "place_of_service": "11" if facility_type == "office" else "22",  # CMS place of service codes

        # Financial
        "billed_amount": round(amount, 2),
        "currency": "USD",

        # Payer info
        "payer_name": payer_name,
        "payer_id": payer_name.lower().replace(" ", "_"),
        "plan_type": random.choice(["PPO", "HMO", "EPO", "POS", "Medicare", "Medicaid"]),

        # Prior auth (will be used to create at-risk scenarios)
        "prior_auth_number": None,
        "prior_auth_required": False,

        # Clinical notes summary (synthetic)
        "clinical_notes_summary": None
    }


def calculate_age(birth_date_str: str) -> int:
    """Calculate age from birth date string."""
    try:
        birth_date = datetime.strptime(birth_date_str[:10], "%Y-%m-%d")
        today = datetime.now()
        return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    except:
        return 50  # Default age


def select_diverse_claims(claims: List[Dict], n: int = 50) -> List[Dict]:
    """Select a diverse set of claims based on various criteria."""

    # Group by procedure type
    by_procedure = {}
    for claim in claims:
        procs = claim.get("procedure_codes", [])
        if procs:
            proc_code = procs[0].get("code", "unknown")
            if proc_code not in by_procedure:
                by_procedure[proc_code] = []
            by_procedure[proc_code].append(claim)

    selected = []

    # Take at least one from each procedure type (up to limit)
    procedure_types = list(by_procedure.keys())
    random.shuffle(procedure_types)

    for proc_type in procedure_types[:min(30, len(procedure_types))]:
        if by_procedure[proc_type]:
            selected.append(random.choice(by_procedure[proc_type]))

    # Fill remaining with random selection ensuring amount diversity
    remaining = [c for c in claims if c not in selected]

    # Sort by amount and take from different ranges
    remaining.sort(key=lambda x: x.get("billed_amount", 0))

    while len(selected) < n and remaining:
        # Take from different parts of the amount distribution
        idx = random.randint(0, len(remaining) - 1)
        selected.append(remaining.pop(idx))

    return selected[:n]


def main():
    print(f"Loading Synthea bundle from {SYNTHEA_FILE}...")
    bundle = load_synthea_bundle(SYNTHEA_FILE)

    print("Indexing resources by type...")
    resources = extract_resources_by_type(bundle)

    # Get patient info
    patients = resources.get("Patient", [])
    patient = patients[0] if patients else {}

    print(f"Found {len(resources.get('Claim', []))} claims")

    # Transform all claims
    print("Transforming claims to simplified format...")
    transformed_claims = []
    for claim in resources.get("Claim", []):
        try:
            transformed = transform_claim(claim, resources, patient)
            transformed_claims.append(transformed)
        except Exception as e:
            print(f"  Warning: Could not transform claim {claim.get('id', 'unknown')}: {e}")

    print(f"Successfully transformed {len(transformed_claims)} claims")

    # Select diverse subset
    print(f"Selecting 50 diverse claims...")
    selected_claims = select_diverse_claims(transformed_claims, n=50)

    # Update dates to be more recent
    for i, claim in enumerate(selected_claims):
        # Spread claims over last 6 months
        days_ago = random.randint(1, 180)
        service_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        from datetime import timedelta
        service_date = service_date - timedelta(days=days_ago)
        claim["service_date"] = service_date.strftime("%Y-%m-%d")
        claim["submission_date"] = (service_date + timedelta(days=random.randint(1, 14))).strftime("%Y-%m-%d")

        # Assign varied payers
        claim["payer_name"] = PAYERS[i % len(PAYERS)]
        claim["payer_id"] = claim["payer_name"].lower().replace(" ", "_")

    # Save individual claims
    print(f"Saving claims to {OUTPUT_DIR}...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for i, claim in enumerate(selected_claims):
        filename = f"claim_{i+1:03d}.json"
        with open(OUTPUT_DIR / filename, 'w') as f:
            json.dump(claim, f, indent=2)

    # Also save a combined file for easy loading
    with open(OUTPUT_DIR / "_all_claims.json", 'w') as f:
        json.dump(selected_claims, f, indent=2)

    print(f"\nDone! Created {len(selected_claims)} claims in {OUTPUT_DIR}")
    print("\nSample claim structure:")
    print(json.dumps(selected_claims[0], indent=2)[:1500])


if __name__ == "__main__":
    main()
