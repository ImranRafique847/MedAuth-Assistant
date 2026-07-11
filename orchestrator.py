"""
Orchestrator
------------
Runs the full pipeline in the correct order:

  Phase 0: Eligibility Agent - is this patient an active, paid member?
           If NOT eligible, STOP immediately - no point checking anything else.
  Phase 1 (parallel): Compliance + Clinical run at the same time
  Phase 2 (sequential): Coverage runs after Clinical finishes
  Phase 3: Synthesis combines all outputs into a final recommendation
"""

import asyncio
import json
import sys
import os

sys.path.append(os.path.dirname(__file__))
import eligibility_agent
import clinical_agent
import compliance_agent
import coverage_agent
import synthesis_agent


async def run_eligibility(case: dict) -> dict:
    return await asyncio.to_thread(eligibility_agent.evaluate_case, case)


async def run_clinical(case: dict) -> dict:
    return await asyncio.to_thread(clinical_agent.evaluate_case, case)


async def run_compliance(case: dict) -> dict:
    return await asyncio.to_thread(compliance_agent.evaluate_case, case)


async def run_coverage(case: dict, clinical_result: dict) -> dict:
    return await asyncio.to_thread(coverage_agent.evaluate_case, case, clinical_result)


async def run_pipeline(case: dict) -> dict:
    # Phase 0: Eligibility check - gate before spending any LLM calls
    eligibility_result = await run_eligibility(case)

    if not eligibility_result["eligible"]:
        return {
            "case_id": case.get("case_id"),
            "recommendation": "DENY - NOT ELIGIBLE",
            "weighted_confidence_score": 1.0,
            "gates": {
                "eligibility_gate": "FAIL",
                "compliance_gate": "SKIPPED",
                "clinical_gate": "SKIPPED",
                "coverage_gate": "SKIPPED",
            },
            "agent_outputs": {
                "eligibility": eligibility_result,
            },
            "requires_human_review": True,
        }

    # Phase 1: Compliance + Clinical run in parallel
    clinical_result, compliance_result = await asyncio.gather(
        run_clinical(case),
        run_compliance(case),
    )

    # Phase 2: Coverage runs after Clinical (needs its structured output)
    coverage_result = await run_coverage(case, clinical_result)

    # Phase 3: Synthesis combines everything
    final_result = synthesis_agent.synthesize(clinical_result, compliance_result, coverage_result)
    final_result["gates"]["eligibility_gate"] = "PASS"
    final_result["agent_outputs"]["eligibility"] = eligibility_result

    return final_result


def run_pipeline_sync(case: dict) -> dict:
    """Convenience wrapper for non-async callers (e.g. FastAPI sync routes, scripts)."""
    return asyncio.run(run_pipeline(case))


if __name__ == "__main__":
    # Test with an ELIGIBLE member
    print("=== Test 1: Eligible member ===")
    sample_case = {
        "case_id": "TEST-001",
        "member_id": "MEM-1001",
        "patient_age": 54,
        "diagnosis": "Type 2 Diabetes Mellitus, uncontrolled (HbA1c 9.2%)",
        "clinical_notes": "Patient has been on Metformin and Glipizide for 8 months with inadequate control.",
        "requested_treatment": "Semaglutide (Ozempic) 0.25mg weekly injection",
        "prior_treatments_tried": ["Metformin", "Glipizide"],
    }
    result = run_pipeline_sync(sample_case)
    print(json.dumps(result, indent=2))

    # Test with an INELIGIBLE member (should stop at eligibility, no LLM calls made)
    print("\n=== Test 2: Ineligible member (should short-circuit) ===")
    ineligible_case = dict(sample_case)
    ineligible_case["case_id"] = "TEST-002"
    ineligible_case["member_id"] = "MEM-1002"
    result2 = run_pipeline_sync(ineligible_case)
    print(json.dumps(result2, indent=2))
