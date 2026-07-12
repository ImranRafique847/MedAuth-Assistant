"""
Pulls real Medicare coverage rules (NCDs - National Coverage Determinations)
from the official CMS Coverage API and saves them into your project folder.

No API key needed - this is a free, public government API.

NOTE: api.coverage.cms.gov is geo-restricted via CloudFront and is not
accessible from outside the United States. Run this script via the GitHub
Actions workflow (.github/workflows/fetch-cms-data.yml) which executes on
GitHub's US-based servers and bypasses the geo-block.

Run with:
    python fetch_cms_coverage_data.py

Output goes to: data/cms_coverage/ncd_documents.json
"""

import requests
import json
import os

BASE_URL = "https://api.coverage.cms.gov/v1"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "data", "cms_coverage")


def fetch_ncd_list():
    """
    Fetches the list of National Coverage Determinations (NCDs).
    These are Medicare's official rules for what's covered, for which
    conditions, nationwide - covering ALL disease areas (cardiology,
    oncology, orthopedics, diabetes, mental health, imaging, etc.)
    """
    url = f"{BASE_URL}/reports/national-coverage-ncd/"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def save_json(data, filename):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved {len(data) if isinstance(data, list) else 'data'} to {path}")


if __name__ == "__main__":
    print("Fetching National Coverage Determinations from CMS...")
    ncd_data = fetch_ncd_list()
    save_json(ncd_data, "ncd_documents.json")
    print("Done. Open data/cms_coverage/ncd_documents.json to see real coverage rules.")
