"""
FastAPI Backend
---------------
Exposes the multi-agent pipeline as a web API.

Routes:
  POST /review                        - run full agent pipeline on a PA case
  GET  /requests                      - list all PA requests
  GET  /requests/{id}                 - get single PA request
  POST /requests/{id}/decision        - human reviewer Accept/Override
  POST /upload-prescription           - extract fields from uploaded PDF
  GET  /health                        - health check

Run with:
    uvicorn main:app --reload
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List

from orchestrator import run_pipeline_sync
import prescription_parser
import database

app = FastAPI(title="MedAuth Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

database.init_db()


class PACaseRequest(BaseModel):
    case_id: str
    member_id: Optional[str] = None
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
    Submits a PA request through the full 5-agent pipeline
    (Eligibility -> Compliance + Clinical -> Coverage -> Synthesis),
    saves to the audit trail, and returns the AI draft recommendation.
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


@app.post("/upload-prescription")
async def upload_prescription(file: UploadFile = File(...)):
    """
    Accepts an uploaded typed PDF prescription, extracts text via pdfplumber,
    then uses Claude to parse out structured fields. Returns extracted data
    for the user to review/correct before submitting to /review.
    Does NOT run the agent pipeline - just extraction.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    try:
        raw_text = prescription_parser.extract_text_from_pdf(file.file)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not read PDF: {str(e)}")

    case_id = f"UPLOAD-{file.filename.rsplit('.', 1)[0]}"
    extracted = prescription_parser.parse_prescription_text(raw_text, case_id=case_id)

    if "parse_error" in extracted:
        raise HTTPException(status_code=422, detail=extracted["parse_error"])

    return extracted


@app.get("/health")
def health_check():
    return {"status": "ok"}
