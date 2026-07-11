"""
Prescription Parser
--------------------
Takes raw text extracted from an uploaded prescription (PDF or typed image)
and uses Claude to pull out structured fields: member_id, patient_age,
diagnosis, clinical_notes, requested_treatment, prior_treatments_tried.

This handles TYPED prescriptions reliably. Handwritten prescriptions are
NOT reliably supported - OCR accuracy on handwriting is too low for
medical use, so this assumes the input text was extracted from a
typed/digital document.
"""

import json
import os
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

SYSTEM_PROMPT = """You extract structured data from a prescription/clinical document for a
prior authorization system. Read the raw text and extract these fields.

If a field is not present in the text, use null (do not guess or invent information).

Respond ONLY in valid JSON, no extra text, exactly this structure:
{
  "member_id": "the patient's insurance member ID, or null if not found",
  "patient_name": "patient's full name, or null",
  "patient_age": a number, or null,
  "diagnosis": "the diagnosis as stated in the document",
  "clinical_notes": "relevant clinical notes/history from the document",
  "requested_treatment": "the medicine/procedure/treatment being requested",
  "prior_treatments_tried": ["list", "of", "prior treatments mentioned"],
  "extraction_confidence": "high, medium, or low - based on how clear/complete the document was"
}
"""


def call_claude_via_bedrock(system_prompt: str, user_prompt: str) -> str:
    client = boto3.client("bedrock-runtime", region_name=AWS_REGION)
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 600,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    try:
        response = client.invoke_model(modelId=BEDROCK_MODEL_ID, body=json.dumps(body))
        response_body = json.loads(response["body"].read())
        return response_body["content"][0]["text"]
    except ClientError as e:
        raise RuntimeError(f"Bedrock call failed: {e}")


def parse_prescription_text(raw_text: str, case_id: str = "UPLOADED-CASE") -> dict:
    """
    Takes raw extracted text (from PDF/typed document) and returns
    a structured case dict ready to feed into the agent pipeline.
    """
    if not raw_text or len(raw_text.strip()) < 10:
        return {
            "case_id": case_id,
            "parse_error": "Document text is empty or too short to extract meaningful data.",
        }

    raw_response = call_claude_via_bedrock(SYSTEM_PROMPT, raw_text)
    cleaned = raw_response.strip().replace("```json", "").replace("```", "").strip()

    try:
        extracted = json.loads(cleaned)
    except json.JSONDecodeError:
        return {
            "case_id": case_id,
            "parse_error": "Could not parse structured data from this document.",
            "raw_model_output": raw_response,
        }

    extracted["case_id"] = case_id
    return extracted


def extract_text_from_pdf(pdf_file) -> str:
    """
    Extracts raw text from an uploaded PDF file object.
    Requires: pip install pdfplumber
    """
    import pdfplumber

    text_parts = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n".join(text_parts)


if __name__ == "__main__":
    sample_text = """
    Patient: Ahmed Raza
    Member ID: MEM-1001
    Age: 54

    Diagnosis: Type 2 Diabetes Mellitus, uncontrolled (HbA1c 9.2%)

    Notes: Patient has been on Metformin 1000mg and Glipizide for 8 months
    with inadequate glycemic control. No history of pancreatitis.

    Requested Treatment: Semaglutide (Ozempic) 0.25mg weekly injection
    Prior treatments tried: Metformin, Glipizide
    """

    result = parse_prescription_text(sample_text, case_id="TEST-UPLOAD-001")
    print(json.dumps(result, indent=2))
