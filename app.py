"""
Streamlit Frontend
-------------------
Two ways to submit a case:
  1. Upload a typed prescription PDF — auto-extracts fields via Claude
  2. Manually type in the fields

Then runs the 5-agent pipeline (Eligibility -> Compliance+Clinical -> Coverage -> Synthesis)
and lets a human reviewer Accept or Override the recommendation.

Run with:
    streamlit run app.py

Requires the FastAPI backend running at http://localhost:8000
(run with: uvicorn main:app --reload)
"""

import streamlit as st
import requests

API_URL = "http://localhost:8000"

st.set_page_config(page_title="MedAuth Assistant", layout="wide")
st.title("MedAuth Assistant — AI-Assisted Prior Authorization Review")

tab1, tab2, tab3 = st.tabs(["Upload Prescription", "Manual Entry", "Review Queue"])

# ---------------- Tab 1: Upload prescription PDF ----------------
with tab1:
    st.subheader("Upload a Prescription (typed PDF)")
    st.caption(
        "Handwritten prescriptions are not supported — OCR accuracy on handwriting "
        "is too unreliable for medical use. Upload a typed/digital PDF."
    )

    uploaded_file = st.file_uploader("Choose a PDF prescription", type=["pdf"])

    if uploaded_file is not None and st.button("Extract Data"):
        with st.spinner("Reading document and extracting fields..."):
            try:
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                response = requests.post(f"{API_URL}/upload-prescription", files=files, timeout=60)
                response.raise_for_status()
                extracted = response.json()
                st.session_state["extracted_case"] = extracted
            except Exception as e:
                st.error(f"Error extracting prescription: {e}")

    if "extracted_case" in st.session_state:
        extracted = st.session_state["extracted_case"]
        st.success(f"Extraction confidence: {extracted.get('extraction_confidence', 'unknown')}")

        with st.form("uploaded_case_form"):
            case_id = st.text_input("Case ID", value=extracted.get("case_id", ""))
            member_id = st.text_input("Member ID", value=extracted.get("member_id") or "")
            patient_age = st.number_input(
                "Patient age", min_value=0, max_value=120,
                value=int(extracted.get("patient_age") or 45)
            )
            diagnosis = st.text_area("Diagnosis", value=extracted.get("diagnosis") or "")
            clinical_notes = st.text_area("Clinical notes", value=extracted.get("clinical_notes") or "")
            requested_treatment = st.text_input(
                "Requested treatment", value=extracted.get("requested_treatment") or ""
            )
            prior_treatments = st.text_input(
                "Prior treatments tried (comma separated)",
                value=", ".join(extracted.get("prior_treatments_tried") or [])
            )
            submit_extracted = st.form_submit_button("Run AI Review on this data")

        if submit_extracted:
            payload = {
                "case_id": case_id,
                "member_id": member_id,
                "patient_age": int(patient_age),
                "diagnosis": diagnosis,
                "clinical_notes": clinical_notes,
                "requested_treatment": requested_treatment,
                "prior_treatments_tried": [t.strip() for t in prior_treatments.split(",") if t.strip()],
            }
            with st.spinner("Running full agent pipeline..."):
                try:
                    resp = requests.post(f"{API_URL}/review", json=payload, timeout=60)
                    resp.raise_for_status()
                    result = resp.json()
                    st.session_state.pop("extracted_case", None)
                except Exception as e:
                    st.error(f"Error calling API: {e}")
                    result = None

            if result:
                st.success(f"Recommendation: **{result['recommendation']}**")
                st.metric("Weighted Confidence Score", result["weighted_confidence_score"])
                gates = result["gates"]
                cols = st.columns(len(gates))
                for col, (gate_name, gate_value) in zip(cols, gates.items()):
                    col.metric(gate_name.replace("_", " ").title(), gate_value)
                for agent_name, agent_result in result["agent_outputs"].items():
                    with st.expander(f"{agent_name.title()} Agent details"):
                        st.json(agent_result)
                if "record_id" in result:
                    st.info(f"Saved as record #{result['record_id']} — go to 'Review Queue' tab to Accept/Override.")

# ---------------- Tab 2: Manual entry ----------------
with tab2:
    st.subheader("Submit a Prior Authorization Request Manually")

    with st.form("pa_form"):
        case_id = st.text_input("Case ID", value="CASE-NEW-001")
        member_id = st.text_input(
            "Member ID", value="MEM-1001",
            help="Test IDs: MEM-1001 (active), MEM-1002 (inactive/overdue), MEM-1003 (active), MEM-1004 (expired)"
        )
        patient_age = st.number_input("Patient age", min_value=0, max_value=120, value=45)
        diagnosis = st.text_area("Diagnosis")
        clinical_notes = st.text_area("Clinical notes")
        requested_treatment = st.text_input("Requested treatment")
        prior_treatments = st.text_input("Prior treatments tried (comma separated)")

        submitted = st.form_submit_button("Run AI Review")

    if submitted:
        payload = {
            "case_id": case_id,
            "member_id": member_id,
            "patient_age": int(patient_age),
            "diagnosis": diagnosis,
            "clinical_notes": clinical_notes,
            "requested_treatment": requested_treatment,
            "prior_treatments_tried": [t.strip() for t in prior_treatments.split(",") if t.strip()],
        }

        with st.spinner("Checking eligibility, then running Compliance + Clinical + Coverage + Synthesis..."):
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

            gates = result["gates"]
            cols = st.columns(len(gates))
            for col, (gate_name, gate_value) in zip(cols, gates.items()):
                col.metric(gate_name.replace("_", " ").title(), gate_value)

            for agent_name, agent_result in result["agent_outputs"].items():
                with st.expander(f"{agent_name.title()} Agent details"):
                    st.json(agent_result)

            if "record_id" in result:
                st.info(f"Saved as record #{result['record_id']} — go to 'Review Queue' tab to Accept/Override.")

# ---------------- Tab 3: Review queue ----------------
with tab3:
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
            st.write(
                f"AI Recommendation: **{req['ai_recommendation']}** "
                f"(confidence: {req['weighted_confidence_score']})"
            )

            if req["reviewer_decision"]:
                st.write(
                    f"✅ Reviewer decision: {req['reviewer_decision']} "
                    f"— notes: {req['reviewer_notes'] or 'none'}"
                )
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
