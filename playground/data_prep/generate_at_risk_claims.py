"""
Generate at-risk claims that should trigger denial warnings.
These claims have characteristics known to cause denials.
"""

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict
import random

OUTPUT_DIR = Path(__file__).parent.parent.parent / "requests/denial_prevention/at_risk_claims"
CLAIMS_DIR = Path(__file__).parent.parent.parent / "requests/denial_prevention/claims"

# Load existing claims as base
def load_base_claims() -> List[Dict]:
    with open(CLAIMS_DIR / "_all_claims.json", 'r') as f:
        return json.load(f)


def create_at_risk_claims() -> List[Dict]:
    """Create claims with known denial risk factors."""

    base_claims = load_base_claims()
    at_risk_claims = []

    # Risk Type 1: Missing Prior Authorization for high-cost procedures
    for i in range(3):
        claim = base_claims[i].copy()
        claim["claim_id"] = str(uuid.uuid4())
        claim["procedure_codes"] = [
            {
                "code": "27447",
                "original_code": "27447",
                "system": "CPT",
                "display": "Total knee replacement"
            }
        ]
        claim["billed_amount"] = round(random.uniform(35000, 55000), 2)
        claim["prior_auth_required"] = True
        claim["prior_auth_number"] = None  # MISSING - should trigger warning
        claim["risk_factors"] = ["missing_prior_auth", "high_cost_procedure"]
        claim["expected_denial_category"] = "prior_authorization"
        at_risk_claims.append(claim)

    # Risk Type 2: Diagnosis doesn't support procedure (coding mismatch)
    for i in range(3, 6):
        claim = base_claims[i].copy()
        claim["claim_id"] = str(uuid.uuid4())
        claim["diagnosis_codes"] = [
            {
                "code": "Z00.00",
                "system": "ICD-10",
                "display": "Encounter for general adult medical examination without abnormal findings"
            }
        ]
        claim["procedure_codes"] = [
            {
                "code": "99215",
                "original_code": "99215",
                "system": "CPT",
                "display": "Office visit, established patient, high complexity"
            }
        ]
        claim["billed_amount"] = 250.00
        claim["risk_factors"] = ["diagnosis_procedure_mismatch", "upcoding_risk"]
        claim["expected_denial_category"] = "medical_necessity"
        at_risk_claims.append(claim)

    # Risk Type 3: Timely filing risk (old service date, recent submission)
    for i in range(6, 9):
        claim = base_claims[i].copy()
        claim["claim_id"] = str(uuid.uuid4())
        old_date = datetime.now() - timedelta(days=random.randint(85, 95))
        claim["service_date"] = old_date.strftime("%Y-%m-%d")
        claim["submission_date"] = datetime.now().strftime("%Y-%m-%d")
        claim["payer_name"] = "Aetna"  # 90-day limit
        claim["risk_factors"] = ["timely_filing_risk"]
        claim["expected_denial_category"] = "timely_filing"
        at_risk_claims.append(claim)

    # Risk Type 4: Duplicate submission risk (same procedure, same date, similar claim)
    for i in range(9, 11):
        claim = base_claims[i].copy()
        claim["claim_id"] = str(uuid.uuid4())
        # Keep everything same except claim_id to simulate duplicate
        claim["risk_factors"] = ["potential_duplicate"]
        claim["expected_denial_category"] = "duplicate"
        at_risk_claims.append(claim)

    # Risk Type 5: Out-of-network with HMO plan
    for i in range(11, 14):
        claim = base_claims[i].copy()
        claim["claim_id"] = str(uuid.uuid4())
        claim["plan_type"] = "HMO"
        claim["provider_name"] = "OUT OF NETWORK SPECIALIST"
        claim["provider_npi"] = "9999999999"
        claim["risk_factors"] = ["out_of_network", "hmo_no_referral"]
        claim["expected_denial_category"] = "out_of_network"
        at_risk_claims.append(claim)

    # Risk Type 6: Service bundling issues
    for i in range(14, 16):
        claim = base_claims[i].copy()
        claim["claim_id"] = str(uuid.uuid4())
        claim["procedure_codes"] = [
            {
                "code": "99213",
                "original_code": "99213",
                "system": "CPT",
                "display": "Office visit, established patient"
            },
            {
                "code": "36415",
                "original_code": "36415",
                "system": "CPT",
                "display": "Venipuncture"
            }
        ]
        claim["modifiers"] = []  # Missing modifier 25
        claim["risk_factors"] = ["bundling_issue", "missing_modifier"]
        claim["expected_denial_category"] = "bundling"
        at_risk_claims.append(claim)

    # Risk Type 7: Benefit maximum likely exceeded (PT visits)
    for i in range(16, 18):
        claim = base_claims[i].copy()
        claim["claim_id"] = str(uuid.uuid4())
        claim["procedure_codes"] = [
            {
                "code": "97110",
                "original_code": "97110",
                "system": "CPT",
                "display": "Therapeutic exercises"
            }
        ]
        claim["clinical_notes_summary"] = "Visit 58 of physical therapy for chronic back pain. Patient has received 57 prior visits this year."
        claim["risk_factors"] = ["benefit_maximum_risk", "high_utilization"]
        claim["expected_denial_category"] = "benefit_maximum"
        at_risk_claims.append(claim)

    # Risk Type 8: Documentation likely insufficient
    for i in range(18, 20):
        claim = base_claims[i].copy()
        claim["claim_id"] = str(uuid.uuid4())
        claim["procedure_codes"] = [
            {
                "code": "99215",
                "original_code": "99215",
                "system": "CPT",
                "display": "Office visit, high complexity"
            }
        ]
        claim["clinical_notes_summary"] = None  # No notes attached
        claim["diagnosis_codes"] = [
            {
                "code": "R10.9",
                "system": "ICD-10",
                "display": "Unspecified abdominal pain"
            }
        ]
        claim["risk_factors"] = ["documentation_insufficient", "vague_diagnosis"]
        claim["expected_denial_category"] = "documentation"
        at_risk_claims.append(claim)

    return at_risk_claims


def main():
    print("Generating at-risk claims...")

    at_risk_claims = create_at_risk_claims()

    print(f"Generated {len(at_risk_claims)} at-risk claims")

    # Count by risk type
    from collections import Counter
    risk_types = Counter()
    for claim in at_risk_claims:
        for rf in claim.get("risk_factors", []):
            risk_types[rf] += 1

    print("\nRisk factors represented:")
    for risk, count in sorted(risk_types.items()):
        print(f"  {risk}: {count}")

    # Save
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Individual files
    for i, claim in enumerate(at_risk_claims):
        filename = f"at_risk_{i+1:03d}_{claim['expected_denial_category']}.json"
        with open(OUTPUT_DIR / filename, 'w') as f:
            json.dump(claim, f, indent=2)

    # Combined file
    with open(OUTPUT_DIR / "_all_at_risk_claims.json", 'w') as f:
        json.dump(at_risk_claims, f, indent=2)

    print(f"\nSaved to {OUTPUT_DIR}")

    # Show sample
    print("\nSample at-risk claim (missing prior auth):")
    print(json.dumps(at_risk_claims[0], indent=2)[:1500])


if __name__ == "__main__":
    main()
