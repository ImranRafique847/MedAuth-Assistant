"""
Orchestrator
------------
Runs the full pipeline in the correct order:

  Phase 1 (parallel): Compliance + Clinical run at the same time
  Phase 2 (sequential): Coverage runs after Clinical finishes
  Phase 3: Synthesis combines all outputs into a final recommendation
"""

import asyncio
import json
import sys
import os

sys.path.append(os.path.dirname(__file__))
import clinical_agent
import compliance_agent
import coverage_agent
import synthesis_agent


async def run_clinical(case: dict) -> dict:
    # boto3 calls are blocking, so run them in a thread to allow real parallelism
    return await asyncio.to_thread(clinical_agent.evaluate_case, case)


async def run_compliance(case: dict) -> dict:
    return await asyncio.to_thread(compliance_agent.evaluate_case, case)


async def run_coverage(case: dict, clinical_result: dict) -> dict:
    return await asyncio.to_thread(coverage_agent.evaluate_case, case, clinical_result)


async def run_pipeline(case: dict) -> dict:
    # Phase 1: Compliance + Clinical run in parallel
    clinical_result, compliance_result = await asyncio.gather(
        run_clinical(case),
        run_compliance(case),
    )

    # Phase 2: Coverage runs after Clinical (needs its structured output)
    coverage_result = await run_coverage(case, clinical_result)

    # Phase 3: Synthesis combines everything
    final_result = synthesis_agent.synthesize(clinical_result, compliance_result, coverage_result)

    return final_result


def run_pipeline_sync(case: dict) -> dict:
    """Convenience wrapper for non-async callers (e.g. FastAPI sync routes, scripts)."""
    return asyncio.run(run_pipeline(case))


if __name__ == "__main__":
    sample_case = {
        "case_id": "TEST-001",
        "patient_age": 54,
        "diagnosis": "Type 2 Diabetes Mellitus, uncontrolled (HbA1c 9.2%)",
        "clinical_notes": "Patient has been on Metformin and Glipizide for 8 months with inadequate control.",
        "requested_treatment": "Semaglutide (Ozempic) 0.25mg weekly injection",
        "prior_treatments_tried": ["Metformin", "Glipizide"],
    }

    result = run_pipeline_sync(sample_case)
    print(json.dumps(result, indent=2))
