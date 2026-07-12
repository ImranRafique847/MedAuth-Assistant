"""
ICD-10 Lookup / Validation
--------------------------
Uses the free NIH Clinical Tables API (no API key required) to:
  1. Validate that an ICD-10 code is real and return its description
  2. Look up likely ICD-10 codes from free-text diagnosis when no explicit
     code is available

API docs: https://clinicaltables.nlm.nih.gov/apidoc/icd10cm/v3/doc.html
"""

import requests

NIH_ICD10_API = "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search"
TIMEOUT = 10


def validate_icd10_code(code: str) -> dict:
    """
    Checks whether a given ICD-10-CM code is valid.
    Returns:
      {"valid": True,  "code": "E11.65", "description": "..."}
      {"valid": False, "code": "E99.99", "description": None}
    """
    if not code:
        return {"valid": False, "code": code, "description": None}

    try:
        r = requests.get(
            NIH_ICD10_API,
            params={"sf": "code,name", "terms": code.strip(), "maxList": 5},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        # Response format: [total, [codes], null, [[code, description], ...]]
        codes = data[1] if len(data) > 1 else []
        details = data[3] if len(data) > 3 else []

        # Exact match check (case-insensitive)
        code_upper = code.strip().upper()
        for detail in details:
            if detail[0].upper() == code_upper:
                return {"valid": True, "code": detail[0], "description": detail[1]}

        # Prefix match (e.g. "E11" matches "E11.9")
        for detail in details:
            if detail[0].upper().startswith(code_upper):
                return {"valid": True, "code": detail[0], "description": detail[1]}

        return {"valid": False, "code": code, "description": None}

    except Exception:
        # Network error or API unavailable — don't block the pipeline
        return {"valid": None, "code": code, "description": None, "error": "lookup_unavailable"}


def lookup_icd10_from_text(diagnosis_text: str, max_results: int = 3) -> list:
    """
    Searches ICD-10-CM codes by free-text diagnosis description.
    Returns a list of {"code": ..., "description": ...} dicts,
    best matches first. Returns [] on failure.
    """
    if not diagnosis_text:
        return []

    try:
        r = requests.get(
            NIH_ICD10_API,
            params={"sf": "code,name", "terms": diagnosis_text.strip(), "maxList": max_results},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        details = data[3] if len(data) > 3 else []
        return [{"code": d[0], "description": d[1]} for d in details]

    except Exception:
        return []


def resolve_icd10(diagnosis_text: str, explicit_code: str | None) -> dict:
    """
    High-level resolver used by the Coverage Agent:
      - If an explicit code is provided, validate it; use it if valid.
      - If no code or invalid, attempt text lookup from diagnosis.
      - Returns the best available code and resolution method.

    Return structure:
    {
      "code": "E11.65" or None,
      "description": "...",
      "method": "explicit" | "text_lookup" | "none",
      "confidence": "high" | "medium" | "low"
    }
    """
    # 1. Try explicit code first
    if explicit_code:
        result = validate_icd10_code(explicit_code)
        if result.get("valid"):
            return {
                "code": result["code"],
                "description": result["description"],
                "method": "explicit",
                "confidence": "high",
            }
        if result.get("valid") is None:
            # API unavailable — trust the code as-is
            return {
                "code": explicit_code,
                "description": None,
                "method": "explicit_unvalidated",
                "confidence": "medium",
            }

    # 2. Fall back to text lookup
    if diagnosis_text:
        candidates = lookup_icd10_from_text(diagnosis_text, max_results=1)
        if candidates:
            return {
                "code": candidates[0]["code"],
                "description": candidates[0]["description"],
                "method": "text_lookup",
                "confidence": "medium",
            }

    return {"code": None, "description": None, "method": "none", "confidence": "low"}


if __name__ == "__main__":
    import json

    tests = [
        ("E11.65", "Type 2 Diabetes Mellitus, uncontrolled"),
        ("G44.209", "Tension headache"),
        ("M17.11", "Osteoarthritis, right knee"),
        ("G20",    "Parkinson disease"),
        ("E99.99", "Invalid code test"),
        (None,     "Major Depressive Disorder, treatment-resistant"),
    ]

    for code, text in tests:
        result = resolve_icd10(text, code)
        print(f"Input code={code!r:<10} text={text[:40]!r}")
        print(f"  → {json.dumps(result)}\n")
