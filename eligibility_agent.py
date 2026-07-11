"""
Eligibility Agent
------------------
Checks whether the patient is an active, paid-up member of THIS insurance
company, using the company's own member database.

This runs FIRST, before Compliance/Clinical/Coverage - if the patient isn't
covered at all, there's no point running the rest of the pipeline.

No LLM needed here - this is a straightforward database lookup.
"""

import json
import os
from datetime import datetime, timezone

MEMBERS_PATH = os.path.join(os.path.dirname(__file__), "members.json")


def load_members() -> list:
    with open(MEMBERS_PATH, "r") as f:
        return json.load(f)["members"]


def find_member(member_id: str, members: list) -> dict:
    for member in members:
        if member["member_id"].strip().upper() == member_id.strip().upper():
            return member
    return None


def is_within_coverage_dates(member: dict) -> bool:
    today = datetime.now(timezone.utc).date()
    start = datetime.strptime(member["coverage_start_date"], "%Y-%m-%d").date()
    end = datetime.strptime(member["coverage_end_date"], "%Y-%m-%d").date()
    return start <= today <= end


def evaluate_case(case: dict) -> dict:
    """
    Looks up the member_id in the case against the company's member database.
    Returns eligible=True only if: member exists, premium is PAID, coverage
    status is ACTIVE, and today's date falls within the coverage window.
    """
    member_id = case.get("member_id")

    if not member_id:
        return {
            "case_id": case.get("case_id"),
            "eligible": False,
            "reasoning": "No member ID provided - cannot verify insurance coverage.",
            "member_record": None,
        }

    members = load_members()
    member = find_member(member_id, members)

    if not member:
        return {
            "case_id": case.get("case_id"),
            "eligible": False,
            "reasoning": f"Member ID {member_id} not found in company records.",
            "member_record": None,
        }

    reasons = []
    eligible = True

    if member["premium_status"] != "PAID":
        eligible = False
        reasons.append(f"premium status is {member['premium_status']}, not PAID")

    if member["coverage_status"] != "ACTIVE":
        eligible = False
        reasons.append(f"coverage status is {member['coverage_status']}, not ACTIVE")

    if not is_within_coverage_dates(member):
        eligible = False
        reasons.append("today's date falls outside the member's coverage window")

    reasoning = (
        "Member is active and eligible for coverage."
        if eligible
        else "Not eligible: " + "; ".join(reasons)
    )

    return {
        "case_id": case.get("case_id"),
        "eligible": eligible,
        "reasoning": reasoning,
        "member_record": member,
    }


if __name__ == "__main__":
    # Test with an active member and an inactive member
    for test_id in ["MEM-1001", "MEM-1002", "MEM-9999"]:
        result = evaluate_case({"case_id": "TEST", "member_id": test_id})
        print(json.dumps(result, indent=2))
        print("---")
