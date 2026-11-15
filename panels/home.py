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

HERO = (
    "<div style='padding:28px 30px;border-radius:14px;margin-bottom:8px;"
    "background:linear-gradient(135deg,#0F172A 0%,#1E3A8A 60%,#C2410C 140%);color:#F8FAFC;'>"
    "<p style='letter-spacing:.14em;text-transform:uppercase;font-size:.8rem;margin:0 0 6px;opacity:.8;'>"
    "Trend Detective · NASA Earth data</p>"
    "<p style='font-size:2.3rem;line-height:1.15;font-weight:700;margin:0;'>"
    "Can the same NASA data tell opposite stories?</p>"
    "<p style='font-size:1.1rem;margin:12px 0 0;opacity:.92;max-width:52rem;'>"
    "Claims about climate often rest on one chart and one choice of years. "
    "Here you check such a claim yourself, using NASA satellite and model data for one grid cell. "
    "We don't tell you what's true. We show you how to check.</p></div>"
)
STEPS = (
    "**1. Pick a question.** Start with the featured case, choose another below, or build your own.",
    "**2. Make a guess.** Say whether you expect the values to rise, fall or show no clear trend.",
    "**3. Check the evidence.** See the trend, then whether the answer changes when you pick different years.",
)
FEATURED = "Po Valley"
FEATURED_TEXT = ("Italy's main farming plain, and one rainfall record. Stop it at the 2022 drought and it can "
                 "look like a drying trend. Use other years and the story changes. Try both and compare.")


def _button(label: str, place: str, variable: str, start_year: int, end_year: int, on_select, primary=False) -> None:
    st.button(label, key=f"investigation_{place}_{variable}_{start_year}_{end_year}",
              on_click=on_select, args=(place, variable, start_year, end_year), width="stretch",
              type="primary" if primary else "secondary")


def render(bundle: dict) -> None:
    st.markdown(HERO, unsafe_allow_html=True)
    for column, step in zip(st.columns(3), STEPS):
        column.markdown(step)
    examples, on_select = bundle["examples"], bundle["on_select"]
    featured = [e for e in examples if e[1] == FEATURED]
    others = [e for e in examples if e[1] != FEATURED]
    if featured:
        st.subheader("Featured investigation: the Po Valley")
        with st.container(border=True):
            st.write(FEATURED_TEXT)
            for column, (label, place, variable, start_year, end_year) in zip(st.columns(len(featured)), featured):
                with column:
                    st.caption(f"{get_variable_meta(variable)['label']} · {start_year}–{end_year}")
                    _button(label, place, variable, start_year, end_year, on_select, primary=True)
    st.subheader("More investigations")
    for offset in range(0, len(others), 3):
        columns = st.columns(3)
        for column, (label, place, variable, start_year, end_year) in zip(columns, others[offset:offset + 3]):
            with column.container(border=True):
                st.markdown(f"**{place}**")
                st.caption(f"{get_variable_meta(variable)['label']} · {start_year}–{end_year}")
                st.write(REASONS.get(f"{place} {start_year}", REASONS.get(place, "Explore the available record for this grid cell.")))
                _button(label, place, variable, start_year, end_year, on_select)
