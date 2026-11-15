"""E1: guided investigations that populate the existing controls without fetching."""
from __future__ import annotations
import streamlit as st
from catalogue import get_variable_meta

REASONS = {
    "Milan": "Explore a temperate European grid cell with a long temperature record.",
    "Po Valley": "Compare a lowland rainfall record across different date windows.",
    "Po Valley 2013": "The view from the 2022 drought: the same rainfall record, read from 2013 to 2022.",
    "Seville": "Explore temperature in a Mediterranean-climate setting.",
    "Niamey": "Explore rainfall at a semi-arid Sahel location.",
    "Fairbanks": "Explore a high-latitude continental temperature record.",
    "Sierra Nevada": "Explore surface soil water in a mountain landscape.",
    "Murray–Darling Basin": "Explore rainfall at a Southern Hemisphere basin point.",
}


def render(bundle: dict) -> None:
    st.subheader("Pick an investigation")
    examples, on_select = bundle["examples"], bundle["on_select"]
    for offset in range(0, len(examples), 3):
        columns = st.columns(3)
        for column, (label, place, variable, start_year, end_year) in zip(columns, examples[offset:offset + 3]):
            with column.container(border=True):
                st.markdown(f"**{place}**")
                st.caption(f"{get_variable_meta(variable)['label']} · {start_year}–{end_year}")
                st.write(REASONS.get(f"{place} {start_year}", REASONS.get(place, "Explore the available record for this grid cell.")))
                st.button(label, key=f"investigation_{place}_{variable}_{start_year}_{end_year}",
                          on_click=on_select, args=(place, variable, start_year, end_year), width="stretch")
