"""
Coverage Agent
--------------
Two-layer coverage check:

  Layer 1 — NCD citation lookup (data/cms_coverage/ncd_documents.json)
    Searches the 345 real CMS National Coverage Determinations by title
    keywords. If a match is found, attaches document_id, title, and the
    official CMS URL as a citation. No approval logic here — citation only.

  Layer 2 — Payer policy decision (policies.json)
    The existing keyword-match against policies.json drives the actual
    covered/not-covered decision, step therapy checks, etc.

Runs AFTER the Clinical Agent (needs its structured output).
No LLM calls — fully deterministic.
"""

import json
import os

POLICIES_PATH = os.path.join(os.path.dirname(__file__), "policies.json")
NCD_PATH = os.path.join(os.path.dirname(__file__), "data", "cms_coverage", "ncd_documents.json")

CMS_BASE_URL = "https://www.cms.gov/medicare-coverage-database"


# ---------------------------------------------------------------------------
# Layer 1: NCD citation lookup
# ---------------------------------------------------------------------------

def load_ncd_documents() -> list:
    """Loads the 345 real NCD records fetched from api.coverage.cms.gov."""
    try:
        with open(NCD_PATH, "r") as f:
            raw = json.load(f)
        # Real CMS API wraps records in {"meta": ..., "data": [...]}
        if isinstance(raw, dict) and "data" in raw:
            return raw["data"]
        # Fallback: flat list or legacy format
        if isinstance(raw, list):
            return raw
        return []
    except FileNotFoundError:
        return []


def find_ncd_citation(requested_treatment: str, ncd_documents: list) -> dict | None:
    """
    Searches NCD titles for keywords from the requested treatment.
    Uses the same simple word-overlap approach as the policy matcher.
    Returns the best matching NCD record, or None if no match found.
    """
    if not ncd_documents:
        return None

    requested_lower = requested_treatment.lower()
    # Generic procedural words that appear in many NCD titles — exclude from scoring
    # to avoid false positives (e.g. "injection" matching unrelated NCDs)
    STOPWORDS = {
        "injection", "therapy", "treatment", "procedure", "implant",
        "surgery", "device", "system", "using", "with", "weekly", "daily",
        "nasal", "spray", "infusion", "intravenous", "subcutaneous", "oral",
    }
    treatment_words = [
        w.strip("(),.-") for w in requested_lower.split()
        if len(w.strip("(),.-")) > 4 and w.strip("(),.-") not in STOPWORDS
    ]

    if not treatment_words:
        return None

    best_match = None
    best_score = 0

    for doc in ncd_documents:
        title_lower = doc.get("title", "").lower()
        # Score = sum of word lengths that match (longer words = stronger signal)
        score = sum(len(word) for word in treatment_words if word in title_lower)
        if score > best_score:
            best_score = score
            best_match = doc

    # Require a minimum score of 8 (roughly one meaningful medical term matching)
    return best_match if best_score >= 8 else None


def format_ncd_citation(ncd: dict) -> dict:
    """Formats an NCD record into a clean citation dict for the response."""
    raw_url = ncd.get("url", "")
    # CMS API returns relative URLs like /data/ncd?ncdid=108&ncdver=1
    full_url = (
        CMS_BASE_URL + raw_url
        if raw_url.startswith("/")
        else raw_url or CMS_BASE_URL
    )
    return {
        "ncd_document_id": ncd.get("document_id"),
        "ncd_display_id": ncd.get("document_display_id"),
        "ncd_title": ncd.get("title"),
        "ncd_last_updated": ncd.get("last_updated"),
        "ncd_url": full_url,
    }


# ---------------------------------------------------------------------------
# Layer 2: Payer policy decision (existing logic, unchanged)
# ---------------------------------------------------------------------------

def load_policies() -> list:
    with open(POLICIES_PATH, "r") as f:
        return json.load(f)["policies"]


def find_matching_policy(requested_treatment: str, policies: list) -> dict | None:
    """
    Simple keyword match between requested treatment and policy category.
    In a real system this would use embeddings/semantic search.
    """
    requested_lower = requested_treatment.lower()
    for policy in policies:
        category_keywords = policy["treatment_category"].lower()
        for word in category_keywords.replace("(", "").replace(")", "").split():
            if len(word) > 4 and word in requested_lower:
                return policy
    return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def evaluate_case(case: dict, clinical_result: dict = None) -> dict:
    """
    Runs the Coverage Agent on a single case.
    Returns payer policy decision + optional NCD citation from real CMS data.
    """
    requested_treatment = case["requested_treatment"]

    # --- Layer 1: NCD citation lookup ---
    ncd_documents = load_ncd_documents()
    ncd_match = find_ncd_citation(requested_treatment, ncd_documents)
    ncd_citation = format_ncd_citation(ncd_match) if ncd_match else None

    # --- Layer 2: Payer policy decision ---
    policies = load_policies()
    policy = find_matching_policy(requested_treatment, policies)

    if not policy:
        result = {
            "case_id": case["case_id"],
            "covered": False,
            "confidence": 0.6,
            "reasoning": "No matching payer policy found for this treatment category. Manual review required.",
            "matched_policy_id": None,
        }
        if ncd_citation:
            result["ncd_citation"] = ncd_citation
            result["reasoning"] += (
                f" However, a related CMS NCD was found: '{ncd_citation['ncd_title']}' "
                f"(NCD {ncd_citation['ncd_display_id']}) — see {ncd_citation['ncd_url']}"
            )
        return result

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

    result = {
        "case_id": case["case_id"],
        "covered": covered,
        "confidence": 0.9,
        "reasoning": "; ".join(reasoning_parts),
        "matched_policy_id": policy["policy_id"],
        "policy_notes": policy["notes"],
    }

    if ncd_citation:
        result["ncd_citation"] = ncd_citation

    return result


if __name__ == "__main__":
    cases = [
        {
            "case_id": "TEST-001",
            "diagnosis": "Type 2 Diabetes Mellitus, uncontrolled",
            "requested_treatment": "Semaglutide (Ozempic) 0.25mg weekly injection",
            "prior_treatments_tried": ["Metformin", "Glipizide"],
        },
        {
            "case_id": "TEST-002",
            "diagnosis": "Tension headache, occasional",
            "requested_treatment": "MRI Brain with contrast",
            "prior_treatments_tried": [],
        },
        {
            "case_id": "TEST-003",
            "diagnosis": "Parkinson disease, advanced",
            "requested_treatment": "Deep brain stimulation surgery",
            "prior_treatments_tried": ["Levodopa"],
        },
    ]
    for c in cases:
        result = evaluate_case(c)
        print(json.dumps(result, indent=2))
        print("---")
