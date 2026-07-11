"""
Compliance Agent
----------------
Checks that the PA request has all required administrative fields filled
correctly. This does NOT judge medical necessity (that's Clinical Agent's job)
- it just checks the request is procedurally complete and valid.

Runs in PARALLEL with the Clinical Agent (neither depends on the other).
"""

import json
import re
import os
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

SYSTEM_PROMPT = """You are a Compliance Review Agent for a health insurance prior authorization system.

Your job is ONLY to check procedural/administrative completeness — NOT medical necessity.
Check for:
1. Is patient age provided and reasonable (0-120)?
2. Is diagnosis clearly stated (not vague/missing)?
3. Is requested treatment clearly stated?
4. Are clinical notes present and non-trivial (not empty or one word)?

Respond ONLY in valid JSON, no extra text:
{
  "compliant": true or false,
  "confidence": a number between 0 and 1,
  "missing_fields": ["list any missing or inadequate fields, empty list if none"],
  "reasoning": "short explanation, 1-2 sentences"
}
"""


def _basic_field_check(case: dict) -> list:
    """Deterministic rule-based checks (fast, no LLM needed for these)."""
    issues = []
    if not case.get("diagnosis") or len(case["diagnosis"].strip()) < 3:
        issues.append("diagnosis missing or too short")
    if not case.get("requested_treatment"):
        issues.append("requested_treatment missing")
    if not case.get("clinical_notes") or len(case["clinical_notes"].strip()) < 10:
        issues.append("clinical_notes missing or too brief")
    age = case.get("patient_age")
    if age is None or not isinstance(age, (int, float)) or age < 0 or age > 120:
        issues.append("patient_age missing or invalid")
    return issues


def build_user_prompt(case: dict) -> str:
    return f"""Patient age: {case.get('patient_age')}
Diagnosis: {case.get('diagnosis')}
Clinical notes: {case.get('clinical_notes')}
Requested treatment: {case.get('requested_treatment')}
Prior treatments listed: {case.get('prior_treatments_tried')}

Check this request for procedural/administrative completeness."""


def call_claude_via_bedrock(system_prompt: str, user_prompt: str) -> str:
    client = boto3.client("bedrock-runtime", region_name=AWS_REGION)
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 400,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    try:
        response = client.invoke_model(modelId=BEDROCK_MODEL_ID, body=json.dumps(body))
        response_body = json.loads(response["body"].read())
        return response_body["content"][0]["text"]
    except ClientError as e:
        raise RuntimeError(f"Bedrock call failed: {e}")


def evaluate_case(case: dict) -> dict:
    """Runs the Compliance Agent on a single case."""
    # Fast deterministic pre-check first
    rule_based_issues = _basic_field_check(case)

    user_prompt = build_user_prompt(case)
    raw_response = call_claude_via_bedrock(SYSTEM_PROMPT, user_prompt)
    cleaned = raw_response.strip().replace("```json", "").replace("```", "").strip()

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        result = {
            "compliant": len(rule_based_issues) == 0,
            "confidence": 0.5,
            "missing_fields": rule_based_issues,
            "reasoning": "Could not parse model response, used rule-based check only.",
        }

    # Merge rule-based issues in, in case the model missed something obvious
    merged_missing = list(set(result.get("missing_fields", []) + rule_based_issues))
    result["missing_fields"] = merged_missing
    if merged_missing:
        result["compliant"] = False

    result["case_id"] = case["case_id"]
    return result


if __name__ == "__main__":
    sample_case = {
        "case_id": "TEST-001",
        "patient_age": 54,
        "diagnosis": "Type 2 Diabetes Mellitus, uncontrolled",
        "clinical_notes": "Patient has been on Metformin and Glipizide for 8 months.",
        "requested_treatment": "Semaglutide (Ozempic) 0.25mg weekly injection",
        "prior_treatments_tried": ["Metformin", "Glipizide"],
    }
    result = evaluate_case(sample_case)
    print(json.dumps(result, indent=2))
