"""E1: guided investigations that populate the existing controls without fetching."""
from __future__ import annotations
import streamlit as st
from catalogue import get_variable_meta

REASONS = {
    "Milan": "A long temperature record from a densely built plain in northern Italy. "
             "Long records make slow, steady changes easier to tell apart from year-to-year noise.",
    "Po Valley": "Italy's main farming plain. Rainfall swings a lot from year to year, "
                 "so the choice of years can change the answer.",
    "Po Valley 2013": "The same rainfall record, but the window stops at the 2022 drought. "
                      "Compare it with the full record to see how the end year changes the conclusion.",
    "Seville": "Southern Spain, with hot, dry summers. Compare its temperature record with Milan's.",
    "Niamey": "The Sahel, at the southern edge of the Sahara. Almost all rain falls in a few summer months, "
              "so a few very wet or very dry seasons can sway the record.",
    "Fairbanks": "Interior Alaska, far north. Winters vary strongly from year to year, "
                 "which makes a slow trend harder to pin down.",
    "Sierra Nevada": "Water in the top 10 cm of soil in California's mountains. It comes from a land-surface "
                     "model driven by observations, not from a direct measurement.",
    "Murray–Darling Basin": "Australia's largest river basin and a major farming region, where long droughts "
                            "and wet spells alternate. This is one point in a very large basin.",
}

INTRO = ("Claims about climate often rest on one chart and one choice of years. "
         "Here you check such a claim yourself, using NASA satellite and model data for one grid cell.")
STEPS = (
    "**1. Pick a question.** Choose an investigation below, or build your own.",
    "**2. Make a guess.** Say whether you expect the values to rise, fall or show no clear trend.",
    "**3. Check the evidence.** See the trend, how sure the data let us be, "
    "and whether the answer changes when you pick different years.",
)


def render(bundle: dict) -> None:
    st.write(INTRO)
    for column, step in zip(st.columns(3), STEPS):
        column.markdown(step)
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
