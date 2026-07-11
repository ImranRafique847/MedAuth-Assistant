"""
Synthesis Agent
----------------
Combines outputs from Clinical, Compliance, and Coverage agents into one
final recommendation, using weighted scoring (based on the pattern used in
Microsoft's Prior-Authorization-Multi-Agent-Solution-Accelerator):

    40% coverage criteria
    30% clinical extraction/justification
    20% compliance
    10% policy match confidence

This does NOT make the final binding decision - it produces a DRAFT
recommendation that a human reviewer must Accept or Override.
"""


def compute_weighted_score(clinical: dict, compliance: dict, coverage: dict) -> float:
    clinical_score = clinical.get("confidence", 0) if clinical.get("justified") else 0
    compliance_score = compliance.get("confidence", 0) if compliance.get("compliant") else 0
    coverage_score = coverage.get("confidence", 0) if coverage.get("covered") else 0
    policy_match_score = 1.0 if coverage.get("matched_policy_id") else 0.0

    weighted = (
        0.40 * coverage_score
        + 0.30 * clinical_score
        + 0.20 * compliance_score
        + 0.10 * policy_match_score
    )
    return round(weighted, 3)


def apply_gate_rubric(clinical: dict, compliance: dict, coverage: dict) -> dict:
    """
    Three-gate rubric: Provider/Compliance gate, Codes/Coverage gate,
    Medical Necessity/Clinical gate. All three gates must pass for
    auto-approval; otherwise it's routed to human review.
    """
    gates = {
        "compliance_gate": "PASS" if compliance.get("compliant") else "FAIL",
        "coverage_gate": "PASS" if coverage.get("covered") else "FAIL",
        "clinical_gate": "PASS" if clinical.get("justified") else "FAIL",
    }
    return gates


def synthesize(clinical: dict, compliance: dict, coverage: dict) -> dict:
    gates = apply_gate_rubric(clinical, compliance, coverage)
    score = compute_weighted_score(clinical, compliance, coverage)

    all_gates_pass = all(v == "PASS" for v in gates.values())

    if all_gates_pass and score >= 0.75:
        recommendation = "APPROVE"
    elif gates["compliance_gate"] == "FAIL":
        recommendation = "PEND - INCOMPLETE REQUEST"
    elif gates["clinical_gate"] == "FAIL" or gates["coverage_gate"] == "FAIL":
        recommendation = "DENY - CRITERIA NOT MET"
    else:
        recommendation = "PEND - MANUAL REVIEW REQUIRED"

    return {
        "case_id": clinical.get("case_id"),
        "recommendation": recommendation,
        "weighted_confidence_score": score,
        "gates": gates,
        "agent_outputs": {
            "clinical": clinical,
            "compliance": compliance,
            "coverage": coverage,
        },
        "requires_human_review": recommendation != "APPROVE" or score < 0.9,
    }


if __name__ == "__main__":
    # Example combining dummy outputs from all three agents
    clinical = {"case_id": "TEST-001", "justified": True, "confidence": 0.9, "reasoning": "Meets criteria"}
    compliance = {"case_id": "TEST-001", "compliant": True, "confidence": 0.95, "missing_fields": []}
    coverage = {"case_id": "TEST-001", "covered": True, "confidence": 0.9, "matched_policy_id": "POL-DIABETES-GLP1"}

    import json
    result = synthesize(clinical, compliance, coverage)
    print(json.dumps(result, indent=2))
