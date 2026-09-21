"""Streamlit report form mockup (SPEC §7.1). Matching results come later."""

from __future__ import annotations

from datetime import date

import streamlit as st

st.set_page_config(page_title="Stolen Bike Matcher", layout="wide")
st.title("Stolen Bike Matcher")
st.caption("This tool creates a matching between reported stolen bikes in second-hand marketplaces for police review.")
with st.form("report_form"):
    st.subheader("Report a stolen bike")
    photos = st.file_uploader(
        "Photos (1–5, required)",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
    )
    col_a, col_b = st.columns(2)
    with col_a:
        serial = st.text_input("Serial / frame number (strongly encouraged)")
        brand = st.text_input("Brand (optional)")
        color = st.text_input("Colour (optional)")
    with col_b:
        stolen_on = st.date_input("Theft date (required)", value=date.today())
        location = st.text_input("Theft location (required)", placeholder="Maastricht")
        police_nr = st.text_input("Police report number (optional)")
    notes = st.text_area("Notes", placeholder="Any additional information...")
    submitted = st.form_submit_button("Find candidate listings")

if submitted:
    errors: list[str] = []
    if not photos:
        errors.append("Add at least one photo.")
    elif len(photos) > 5:
        errors.append("Use at most five photos.")
    if not location.strip():
        errors.append("Theft location is required.")
    if errors:
        for err in errors:
            st.error(err)
    else:
        st.success("Form looks valid. Matching is not wired yet.")
        st.json(
            {
                "photos": [p.name for p in photos],
                "serial": serial or None,
                "brand": brand or None,
                "color": color or None,
                "stolen_at": stolen_on.isoformat(),
                "location": location,
                "police_report_nr": police_nr or None,
                "notes": notes or None,
            }
        )

st.divider()