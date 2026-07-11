"""
FastAPI Backend
---------------
Exposes the multi-agent pipeline as a web API.

Run with:
    uvicorn api.main:app --reload
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from orchestrator import run_pipeline_sync
import database

app = FastAPI(title="Prior Authorization AI API")

database.init_db()


class PACaseRequest(BaseModel):
    case_id: str
    patient_age: int
    diagnosis: str
    clinical_notes: str
    requested_treatment: str
    prior_treatments_tried: List[str] = []


class ReviewDecision(BaseModel):
    decision: str  # "ACCEPT" or "OVERRIDE"
    notes: Optional[str] = ""


@app.post("/review")
def review_case(case: PACaseRequest):
    """
    Submits a new PA request through the full agent pipeline
    (Compliance + Clinical -> Coverage -> Synthesis), saves it to the
    audit trail, and returns the AI's draft recommendation.
    """
    case_dict = case.dict()
    try:
        result = run_pipeline_sync(case_dict)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)}")

    record_id = database.save_pa_request(case_dict, result)
    result["record_id"] = record_id
    return result


@app.get("/requests")
def list_requests():
    """Returns all PA requests for the reviewer dashboard."""
    return database.get_all_requests()


@app.get("/requests/{record_id}")
def get_request(record_id: int):
    record = database.get_request_by_id(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Request not found")
    return record


@app.post("/requests/{record_id}/decision")
def submit_review_decision(record_id: int, review: ReviewDecision):
    """Human reviewer Accepts or Overrides the AI's recommendation."""
    if review.decision not in ("ACCEPT", "OVERRIDE"):
        raise HTTPException(status_code=400, detail="decision must be ACCEPT or OVERRIDE")

    record = database.get_request_by_id(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Request not found")

    database.update_reviewer_decision(record_id, review.decision, review.notes)
    return {"status": "updated", "record_id": record_id, "decision": review.decision}


@app.get("/health")
def health_check():
    return {"status": "ok"}
