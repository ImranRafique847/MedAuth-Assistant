"""
Coverage Agent
--------------
Checks the request against payer policy criteria (data/sample_policies/policies.json).

Runs AFTER the Clinical Agent, because it needs Clinical's structured
understanding of the diagnosis/treatment to match against the right policy.
"""

import json
import os

POLICIES_PATH = os.path.join(os.path.dirname(__file__), "policies.json")


def load_policies() -> list:
    with open(POLICIES_PATH, "r") as f:
        return json.load(f)["policies"]


def find_matching_policy(requested_treatment: str, policies: list) -> dict:
    """Simple keyword match between requested treatment and policy category.
    In a real system this would use embeddings/semantic search instead of
    substring matching."""
    requested_lower = requested_treatment.lower()
    for policy in policies:
        category_keywords = policy["treatment_category"].lower()
        # crude match: check if any significant word overlaps
        for word in category_keywords.replace("(", "").replace(")", "").split():
            if len(word) > 4 and word in requested_lower:
                return policy
    return None


def evaluate_case(case: dict, clinical_result: dict = None) -> dict:
    """
    Runs the Coverage Agent on a single case.
    clinical_result is optional context from the Clinical Agent (per the
    sequential dependency in the real pipeline).
    """
    policies = load_policies()
    policy = find_matching_policy(case["requested_treatment"], policies)

    if not policy:
        return {
            "case_id": case["case_id"],
            "covered": False,
            "confidence": 0.6,
            "reasoning": "No matching payer policy found for this treatment category. Manual review required.",
            "matched_policy_id": None,
        }

    diagnosis_lower = case["diagnosis"].lower()
    diagnosis_matches = any(
        d.lower() in diagnosis_lower or diagnosis_lower in d.lower()
        for d in policy["covered_diagnoses"]
    )

    prior_treatments = case.get("prior_treatments_tried", [])
    step_therapy_met = True
    if policy["requires_step_therapy"]:
        matched_count = sum(
            1 for req in policy["required_prior_treatments"]
            for tried in prior_treatments
            if req.lower() in tried.lower() or tried.lower() in req.lower()
        )
        step_therapy_met = matched_count >= policy["min_prior_treatment_count"]

    covered = diagnosis_matches and step_therapy_met

    reasoning_parts = []
    if not diagnosis_matches:
        reasoning_parts.append("diagnosis does not match covered diagnoses for this policy")
    if policy["requires_step_therapy"] and not step_therapy_met:
        reasoning_parts.append(
            f"step therapy not met (requires at least {policy['min_prior_treatment_count']} "
            f"of: {', '.join(policy['required_prior_treatments'])})"
        )
    if covered:
        reasoning_parts.append("diagnosis and step-therapy requirements are satisfied")

    return {
        "case_id": case["case_id"],
        "covered": covered,
        "confidence": 0.9 if policy else 0.5,
        "reasoning": "; ".join(reasoning_parts),
        "matched_policy_id": policy["policy_id"],
        "policy_notes": policy["notes"],
    }


if __name__ == "__main__":
    sample_case = {
        "case_id": "TEST-001",
        "diagnosis": "Type 2 Diabetes Mellitus, uncontrolled",
        "requested_treatment": "Semaglutide (Ozempic) 0.25mg weekly injection",
        "prior_treatments_tried": ["Metformin", "Glipizide"],
    }
    result = evaluate_case(sample_case)
    print(json.dumps(result, indent=2))
