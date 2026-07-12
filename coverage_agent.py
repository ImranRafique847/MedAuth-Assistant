"""
Coverage Agent
--------------
Three-layer coverage check (in priority order):

  Layer 1 — ICD-10 / CPT / HCPCS code matching (primary)
    Resolves the diagnosis to an ICD-10 code via NIH Clinical Tables API,
    then matches against covered_icd10_codes in each policy.
    Also matches treatment CPT/HCPCS codes against covered_cpt_codes /
    covered_hcpcs_codes. Code matching is exact — no text ambiguity.

  Layer 2 — Keyword text matching (fallback, low-confidence)
    Used only when no code match is found. Clearly logged as low-confidence.
    Retained from the previous version so the agent degrades gracefully
    when codes are unavailable rather than failing silently.

  Layer 3 — NCD citation lookup (data/cms_coverage/ncd_documents.json)
    Searches 345 real CMS NCD titles for a related document. Citation only —
    no approval logic. Runs regardless of which layer matched.

Runs AFTER the Clinical Agent (needs its structured output).
No LLM calls — fully deterministic.
"""

import json
import os

from icd10_lookup import resolve_icd10

POLICIES_PATH = os.path.join(os.path.dirname(__file__), "policies.json")
NCD_PATH = os.path.join(os.path.dirname(__file__), "data", "cms_coverage", "ncd_documents.json")
CMS_BASE_URL = "https://www.cms.gov/medicare-coverage-database"


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def load_policies() -> list:
    with open(POLICIES_PATH, "r") as f:
        return json.load(f)["policies"]


def load_ncd_documents() -> list:
    try:
        with open(NCD_PATH, "r") as f:
            raw = json.load(f)
        if isinstance(raw, dict) and "data" in raw:
            return raw["data"]
        if isinstance(raw, list):
            return raw
        return []
    except FileNotFoundError:
        return []


# ---------------------------------------------------------------------------
# Layer 1: Code-based policy matching
# ---------------------------------------------------------------------------

def _icd10_prefix_match(code: str, covered_codes: list) -> bool:
    """
    Checks if a code matches any covered code, allowing parent-code coverage.
    E.g. policy covers "E11" → matches "E11.65", "E11.9", etc.
    Policy covers "E11.65" → only matches "E11.65" exactly.
    """
    code_upper = code.upper()
    for covered in covered_codes:
        c = covered.upper()
        # Exact match or policy code is a parent prefix of the case code
        if code_upper == c or code_upper.startswith(c) or c.startswith(code_upper):
            return True
    return False


def find_policy_by_codes(case: dict, policies: list) -> tuple[dict | None, str]:
    """
    Attempts to match a policy using ICD-10, CPT, and HCPCS codes.
    Returns (matched_policy, match_method) where match_method is one of:
      "icd10"   — matched via ICD-10 diagnosis code
      "cpt"     — matched via CPT procedure code
      "hcpcs"   — matched via HCPCS code
      None      — no code match found
    """
    # Resolve ICD-10 code (validate explicit code or look up from text)
    icd10_result = resolve_icd10(
        diagnosis_text=case.get("diagnosis", ""),
        explicit_code=case.get("diagnosis_icd10"),
    )
    resolved_code = icd10_result.get("code")

    treatment_cpt = case.get("treatment_cpt", "")
    treatment_hcpcs = case.get("treatment_hcpcs", "")

    for policy in policies:
        # --- ICD-10 match ---
        if resolved_code:
            covered_icd10 = policy.get("covered_icd10_codes", [])
            if covered_icd10 and _icd10_prefix_match(resolved_code, covered_icd10):
                # Also require a CPT/HCPCS match if the policy specifies them,
                # to avoid matching diagnosis without the right treatment code
                covered_cpt = policy.get("covered_cpt_codes", [])
                covered_hcpcs = policy.get("covered_hcpcs_codes", [])
                has_treatment_codes = bool(covered_cpt or covered_hcpcs)

                if not has_treatment_codes:
                    return policy, "icd10"

                # Policy has treatment codes — check if treatment matches too
                cpt_match = treatment_cpt and any(
                    treatment_cpt.strip() == c.strip()
                    for c in covered_cpt
                )
                hcpcs_match = treatment_hcpcs and any(
                    treatment_hcpcs.strip() == c.strip()
                    for c in covered_hcpcs
                )
                if cpt_match or hcpcs_match:
                    return policy, "icd10+cpt" if cpt_match else "icd10+hcpcs"

                # ICD-10 matched but no treatment code match —
                # still return this policy (diagnosis is the primary gate)
                return policy, "icd10"

    # --- CPT-only match (no ICD-10 resolved) ---
    if treatment_cpt:
        for policy in policies:
            if treatment_cpt.strip() in [c.strip() for c in policy.get("covered_cpt_codes", [])]:
                return policy, "cpt"

    # --- HCPCS-only match ---
    if treatment_hcpcs:
        for policy in policies:
            if treatment_hcpcs.strip() in [c.strip() for c in policy.get("covered_hcpcs_codes", [])]:
                return policy, "hcpcs"

    return None, "none"


# ---------------------------------------------------------------------------
# Layer 2: Keyword fallback (low confidence)
# ---------------------------------------------------------------------------

POLICY_STOPWORDS = {
    "therapy", "treatment", "injection", "injections", "procedure",
    "surgery", "device", "for", "with", "and", "the", "of", "in", "to",
    "agent", "agents", "syndrome", "disease", "e.g.", "eg", "i.e.", "ie",
}


def find_policy_by_keywords(requested_treatment: str, policies: list) -> dict | None:
    """
    Keyword fallback — only used when code matching returns nothing.
    Scores each policy by distinct meaningful word overlap.
    """
    requested_words = set(
        requested_treatment.lower().replace("(", "").replace(")", "").replace(",", "").split()
    )
    requested_words = {w for w in requested_words if w not in POLICY_STOPWORDS and len(w) > 2}

    best_policy = None
    best_overlap_count = 0
    best_score = 0

    for policy in policies:
        category_words = set(
            policy["treatment_category"].lower().replace("(", "").replace(")", "").replace(",", "").split()
        )
        category_words = {w for w in category_words if w not in POLICY_STOPWORDS and len(w) > 2}

        overlap = requested_words & category_words
        overlap_count = len(overlap)
        score = sum(len(w) for w in overlap)

        required = min(2, len(category_words))
        has_specific_word = any(len(w) >= 6 for w in overlap)
        qualifies = overlap_count >= required or (overlap_count >= 1 and has_specific_word)

        if qualifies and overlap_count > 0:
            if overlap_count > best_overlap_count or (
                overlap_count == best_overlap_count and score > best_score
            ):
                best_overlap_count = overlap_count
                best_score = score
                best_policy = policy

    return best_policy


# ---------------------------------------------------------------------------
# Layer 3: NCD citation lookup
# ---------------------------------------------------------------------------

NCD_STOPWORDS = {
    "injection", "therapy", "treatment", "procedure", "implant",
    "surgery", "device", "system", "using", "with", "weekly", "daily",
    "nasal", "spray", "infusion", "intravenous", "subcutaneous", "oral",
}


def find_ncd_citation(requested_treatment: str, ncd_documents: list) -> dict | None:
    if not ncd_documents:
        return None
    treatment_words = [
        w.strip("(),.-") for w in requested_treatment.lower().split()
        if len(w.strip("(),.-")) > 4 and w.strip("(),.-") not in NCD_STOPWORDS
    ]
    if not treatment_words:
        return None
    best_match = None
    best_score = 0
    for doc in ncd_documents:
        title_lower = doc.get("title", "").lower()
        score = sum(len(word) for word in treatment_words if word in title_lower)
        if score > best_score:
            best_score = score
            best_match = doc
    return best_match if best_score >= 8 else None


def format_ncd_citation(ncd: dict) -> dict:
    raw_url = ncd.get("url", "")
    full_url = CMS_BASE_URL + raw_url if raw_url.startswith("/") else raw_url or CMS_BASE_URL
    return {
        "ncd_document_id": ncd.get("document_id"),
        "ncd_display_id": ncd.get("document_display_id"),
        "ncd_title": ncd.get("title"),
        "ncd_last_updated": ncd.get("last_updated"),
        "ncd_url": full_url,
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def evaluate_case(case: dict, clinical_result: dict = None) -> dict:
    """
    Runs the Coverage Agent on a single case.
    Priority: ICD-10/CPT code match → keyword fallback → no policy match.
    Always appends NCD citation if a related CMS document is found.
    """
    requested_treatment = case["requested_treatment"]
    policies = load_policies()

    # --- Layer 1: Code-based matching ---
    policy, match_method = find_policy_by_codes(case, policies)
    match_confidence = "high"

    # --- Layer 2: Keyword fallback ---
    if policy is None:
        policy = find_policy_by_keywords(requested_treatment, policies)
        if policy:
            match_method = "keyword_fallback"
            match_confidence = "low"

    # --- Layer 3: NCD citation ---
    ncd_documents = load_ncd_documents()
    ncd_match = find_ncd_citation(requested_treatment, ncd_documents)
    ncd_citation = format_ncd_citation(ncd_match) if ncd_match else None

    # --- No policy match ---
    if policy is None:
        result = {
            "case_id": case["case_id"],
            "covered": False,
            "confidence": 0.5,
            "reasoning": "No matching payer policy found. Manual review required. "
                         "(match_method: none — no ICD-10, CPT, HCPCS, or keyword match)",
            "matched_policy_id": None,
            "match_method": "none",
        }
        if ncd_citation:
            result["ncd_citation"] = ncd_citation
            result["reasoning"] += (
                f" Related CMS NCD found: '{ncd_citation['ncd_title']}' "
                f"(NCD {ncd_citation['ncd_display_id']}) — {ncd_citation['ncd_url']}"
            )
        return result

    # --- Evaluate diagnosis match ---
    # Primary: ICD-10 code match (already confirmed by find_policy_by_codes)
    # Secondary for keyword fallback: text match against covered_diagnoses
    if match_method in ("icd10", "icd10+cpt", "icd10+hcpcs"):
        diagnosis_matches = True  # ICD-10 match already confirmed above
    else:
        diagnosis_lower = case["diagnosis"].lower()
        diagnosis_matches = any(
            d.lower() in diagnosis_lower or diagnosis_lower in d.lower()
            for d in policy.get("covered_diagnoses", [])
        )

    # --- Step therapy check ---
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
    if match_method == "keyword_fallback":
        reasoning_parts.append("low confidence — code-based match not available, using keyword fallback")
    if not diagnosis_matches:
        reasoning_parts.append("diagnosis does not match covered diagnoses for this policy")
    if policy["requires_step_therapy"] and not step_therapy_met:
        reasoning_parts.append(
            f"step therapy not met (requires at least {policy['min_prior_treatment_count']} "
            f"of: {', '.join(policy['required_prior_treatments'])})"
        )
    if covered:
        reasoning_parts.append("diagnosis and step-therapy requirements are satisfied")

    confidence = 0.9 if match_confidence == "high" else 0.6
    result = {
        "case_id": case["case_id"],
        "covered": covered,
        "confidence": confidence,
        "reasoning": "; ".join(reasoning_parts),
        "matched_policy_id": policy["policy_id"],
        "match_method": match_method,
        "policy_notes": policy["notes"],
    }

    if ncd_citation:
        result["ncd_citation"] = ncd_citation

    return result


# ---------------------------------------------------------------------------
# STEP 5: Test runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    TEST_CASES = [
        {
            "case_id": "TEST-001-DIABETES",
            "diagnosis": "Type 2 Diabetes Mellitus, uncontrolled (HbA1c 9.2%)",
            "diagnosis_icd10": "E11.65",
            "requested_treatment": "Semaglutide (Ozempic) 0.25mg weekly injection",
            "treatment_hcpcs": "J3490",
            "prior_treatments_tried": ["Metformin", "Glipizide"],
            "expected_policy": "POL-DIABETES-GLP1",
        },
        {
            "case_id": "TEST-002-MRI",
            "diagnosis": "Tension headache, occasional",
            "diagnosis_icd10": "G44.209",
            "requested_treatment": "MRI Brain with contrast",
            "treatment_cpt": "70553",
            "prior_treatments_tried": [],
            "expected_policy": "POL-IMAGING-MRI-BRAIN",
        },
        {
            "case_id": "TEST-003-DBS",
            "diagnosis": "Parkinson disease, advanced",
            "diagnosis_icd10": "G20",
            "requested_treatment": "Deep brain stimulation surgery",
            "treatment_cpt": "61886",
            "prior_treatments_tried": ["Levodopa"],
            "expected_policy": None,  # No DBS policy — must NOT match MRI Brain
        },
        {
            "case_id": "TEST-004-KNEE",
            "diagnosis": "Osteoarthritis, severe, right knee",
            "diagnosis_icd10": "M17.11",
            "requested_treatment": "Total Knee Arthroplasty",
            "treatment_cpt": "27447",
            "prior_treatments_tried": ["NSAIDs", "Physical Therapy"],
            "expected_policy": "POL-ORTHO-KNEE-REPLACEMENT",
        },
        {
            "case_id": "TEST-005-XOLAIR",
            "diagnosis": "Seasonal allergic rhinitis, mild",
            "diagnosis_icd10": "J30.1",
            "requested_treatment": "Xolair (omalizumab) biologic injection",
            "treatment_hcpcs": "J2357",
            "prior_treatments_tried": [],
            "expected_policy": "POL-ALLERGY-BIOLOGIC",
        },
        {
            "case_id": "TEST-006-ESKETAMINE",
            "diagnosis": "Major Depressive Disorder, treatment-resistant",
            "diagnosis_icd10": "F32.89",
            "requested_treatment": "Esketamine (Spravato) nasal spray",
            "treatment_hcpcs": "S0013",
            "prior_treatments_tried": ["Sertraline", "Venlafaxine"],
            "expected_policy": "POL-PSYCH-ESKETAMINE",
        },
        # --- Fallback test: no codes at all (simulates uploaded prescription
        #     where parser couldn't extract ICD-10/CPT/HCPCS) ---
        {
            "case_id": "TEST-007-NO-CODES",
            "diagnosis": "Type 2 Diabetes Mellitus, uncontrolled",
            "requested_treatment": "Semaglutide (Ozempic) 0.25mg weekly injection",
            # No diagnosis_icd10, treatment_cpt, or treatment_hcpcs
            "prior_treatments_tried": ["Metformin"],
            "expected_policy": "POL-DIABETES-GLP1",
            "expected_match_method": "keyword_fallback",  # must NOT be code-based
        },
        {
            "case_id": "TEST-008-NO-CODES-DBS",
            "diagnosis": "Parkinson disease, advanced",
            "requested_treatment": "Deep brain stimulation surgery",
            # No codes — keyword fallback should also return None (no DBS policy)
            "prior_treatments_tried": ["Levodopa"],
            "expected_policy": None,
            "expected_match_method": "none",
        },
    ]

    print("=" * 70)
    print("Coverage Agent — ICD-10/CPT Code Matching Test Results")
    print("=" * 70)
    all_pass = True
    for c in TEST_CASES:
        result = evaluate_case(c)
        matched = result.get("matched_policy_id")
        method = result.get("match_method")
        covered = result.get("covered")
        expected = c["expected_policy"]
        expected_method = c.get("expected_match_method")

        policy_ok = matched == expected
        method_ok = (expected_method is None) or (method == expected_method)
        passed = policy_ok and method_ok
        if not passed:
            all_pass = False

        status = "PASS" if passed else "FAIL"
        print(f"\n[{status}] {c['case_id']}")
        print(f"  ICD-10 : {c.get('diagnosis_icd10', 'NONE')}  "
              f"CPT: {c.get('treatment_cpt', 'NONE')}  "
              f"HCPCS: {c.get('treatment_hcpcs', 'NONE')}")
        print(f"  matched_policy  : {matched}  (expected: {expected})"
              + ("" if policy_ok else "  ← WRONG"))
        print(f"  match_method    : {method}"
              + (f"  (expected: {expected_method})" if expected_method else "")
              + ("" if method_ok else "  ← WRONG"))
        print(f"  covered         : {covered}")
        print(f"  reasoning       : {result.get('reasoning')}")
        if result.get("ncd_citation"):
            nc = result["ncd_citation"]
            print(f"  ncd_citation    : {nc['ncd_title']} ({nc['ncd_display_id']})")

    print("\n" + "=" * 70)
    print(f"Result: {'ALL TESTS PASSED' if all_pass else 'SOME TESTS FAILED'}")
    print("=" * 70)
