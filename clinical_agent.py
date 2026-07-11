"""
Clinical Agent
--------------
Reads a patient's diagnosis + clinical notes + requested treatment,
and decides whether the treatment is medically justified.

Uses AWS Bedrock to call an Anthropic Claude model.
"""

import json
import os
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

# ---- Config ----
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

SYSTEM_PROMPT = """You are a Clinical Review Agent for a health insurance prior authorization system.

Your job: decide if a requested medical treatment is JUSTIFIED based on:
1. Does the diagnosis match the requested treatment?
2. Has the patient tried appropriate lower-cost/simpler treatments first (step therapy), if relevant?
3. Is the treatment medically necessary given the severity/notes described?

You must respond ONLY in valid JSON, with this exact structure, no extra text:
{
  "justified": true or false,
  "confidence": a number between 0 and 1,
  "reasoning": "short explanation, 2-3 sentences",
  "missing_information": "state if anything is missing/insufficient, else null"
}
"""


def build_user_prompt(case: dict) -> str:
    return f"""Patient age: {case['patient_age']}
Diagnosis: {case['diagnosis']}
Clinical notes: {case['clinical_notes']}
Requested treatment: {case['requested_treatment']}
Prior treatments already tried: {', '.join(case['prior_treatments_tried']) or 'None'}

Evaluate whether this requested treatment is medically justified."""


def call_claude_via_bedrock(system_prompt: str, user_prompt: str) -> str:
    """Calls Claude on AWS Bedrock and returns the raw text response."""
    client = boto3.client("bedrock-runtime", region_name=AWS_REGION)

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 500,
        "system": system_prompt,
        "messages": [
            {"role": "user", "content": user_prompt}
        ],
    }

    try:
        response = client.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            body=json.dumps(body),
        )
        response_body = json.loads(response["body"].read())
        return response_body["content"][0]["text"]
    except ClientError as e:
        raise RuntimeError(f"Bedrock call failed: {e}")


def evaluate_case(case: dict) -> dict:
    """Runs the Clinical Agent on a single case and returns a structured result."""
    user_prompt = build_user_prompt(case)
    raw_response = call_claude_via_bedrock(SYSTEM_PROMPT, user_prompt)

    # Clean up in case the model wraps JSON in markdown fences
    cleaned = raw_response.strip().replace("```json", "").replace("```", "").strip()

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        result = {
            "justified": None,
            "confidence": 0,
            "reasoning": "Could not parse model response",
            "missing_information": raw_response,
        }

    result["case_id"] = case["case_id"]
    return result


if __name__ == "__main__":
    # Quick manual test with one case
    sample_case = {
        "case_id": "TEST-001",
        "patient_age": 54,
        "diagnosis": "Type 2 Diabetes Mellitus, uncontrolled (HbA1c 9.2%)",
        "clinical_notes": "Patient has been on Metformin and Glipizide for 8 months with inadequate control.",
        "requested_treatment": "Semaglutide (Ozempic) 0.25mg weekly injection",
        "prior_treatments_tried": ["Metformin", "Glipizide"],
    }

    result = evaluate_case(sample_case)
    print(json.dumps(result, indent=2))
