"""
Streamlit Frontend
-------------------
Simple UI: submit a PA case, watch the 4 agents evaluate it, then
Accept or Override the AI's recommendation as a human reviewer.

Run with:
    streamlit run frontend/app.py

Requires the FastAPI backend to be running at http://localhost:8000
(run with: uvicorn api.main:app --reload)
"""

import streamlit as st
import requests

API_URL = "http://localhost:8000"

st.set_page_config(page_title="Prior Authorization AI Review", layout="wide")
st.title("Prior Authorization — AI-Assisted Review")

tab1, tab2 = st.tabs(["Submit New Case", "Review Queue"])

# ---------------- Tab 1: Submit new case ----------------
with tab1:
    st.subheader("Submit a Prior Authorization Request")

    with st.form("pa_form"):
        case_id = st.text_input("Case ID", value="CASE-NEW-001")
        patient_age = st.number_input("Patient age", min_value=0, max_value=120, value=45)
        diagnosis = st.text_area("Diagnosis")
        clinical_notes = st.text_area("Clinical notes")
        requested_treatment = st.text_input("Requested treatment")
        prior_treatments = st.text_input("Prior treatments tried (comma separated)")

        submitted = st.form_submit_button("Run AI Review")

    if submitted:
        payload = {
            "case_id": case_id,
            "patient_age": int(patient_age),
            "diagnosis": diagnosis,
            "clinical_notes": clinical_notes,
            "requested_treatment": requested_treatment,
            "prior_treatments_tried": [t.strip() for t in prior_treatments.split(",") if t.strip()],
        }

        with st.spinner("Running Compliance + Clinical agents in parallel, then Coverage, then Synthesis..."):
            try:
                response = requests.post(f"{API_URL}/review", json=payload, timeout=60)
                response.raise_for_status()
                result = response.json()
            except Exception as e:
                st.error(f"Error calling API: {e}")
                result = None

        if result:
            st.success(f"Recommendation: **{result['recommendation']}**")
            st.metric("Weighted Confidence Score", result["weighted_confidence_score"])

            col1, col2, col3 = st.columns(3)
            gates = result["gates"]
            col1.metric("Compliance Gate", gates["compliance_gate"])
            col2.metric("Clinical Gate", gates["clinical_gate"])
            col3.metric("Coverage Gate", gates["coverage_gate"])

            with st.expander("Clinical Agent details"):
                st.json(result["agent_outputs"]["clinical"])
            with st.expander("Compliance Agent details"):
                st.json(result["agent_outputs"]["compliance"])
            with st.expander("Coverage Agent details"):
                st.json(result["agent_outputs"]["coverage"])

            st.info(f"Saved as record #{result['record_id']} — go to 'Review Queue' tab to Accept/Override.")

# ---------------- Tab 2: Review queue ----------------
with tab2:
    st.subheader("Human Reviewer Queue")

    if st.button("Refresh queue"):
        st.rerun()

    try:
        requests_list = requests.get(f"{API_URL}/requests", timeout=10).json()
    except Exception as e:
        st.error(f"Could not load requests: {e}")
        requests_list = []

    for req in requests_list:
        with st.container(border=True):
            st.write(f"**{req['case_id']}** — {req['diagnosis']} → {req['requested_treatment']}")
            st.write(f"AI Recommendation: **{req['ai_recommendation']}** "
                     f"(confidence: {req['weighted_confidence_score']})")

            if req["reviewer_decision"]:
                st.write(f"✅ Reviewer decision: {req['reviewer_decision']} "
                         f"— notes: {req['reviewer_notes'] or 'none'}")
            else:
                colA, colB = st.columns(2)
                notes = st.text_input(f"Notes for {req['case_id']}", key=f"notes_{req['id']}")

                if colA.button("Accept", key=f"accept_{req['id']}"):
                    requests.post(
                        f"{API_URL}/requests/{req['id']}/decision",
                        json={"decision": "ACCEPT", "notes": notes},
                    )
                    st.rerun()

                if colB.button("Override", key=f"override_{req['id']}"):
                    requests.post(
                        f"{API_URL}/requests/{req['id']}/decision",
                        json={"decision": "OVERRIDE", "notes": notes},
                    )
                    st.rerun()
