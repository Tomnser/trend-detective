"""Supported variables: Giovanni identifiers, units and display metadata.

`source_unit` is the exact `unit` line of the Giovanni CSV (checked on every load);
`converter` names a function in processing.CONVERTERS that maps it to `display_unit`.
"""

SUPPORTED_VARIABLES = {
    "MERRA2_T2M": {
        "api_id": "M2IMNXASM_5_12_4_T2M",
        "api_version": "5.12.4",
        "source_unit": "K",
        "converter": "kelvin_to_celsius",
        "display_unit": "°C",
        "first_year": 1981,
        "label": "MERRA-2 temperature at 2 m",
        "theme": "temperature",
        "definition": "Monthly mean air temperature 2 m above the ground, from the MERRA-2 atmospheric "
                      "reanalysis. One grid cell (about 50 × 50 km), not a city weather station.",
    },
    "GPM_PRECIP": {
        "api_id": "GPM_3IMERGM_07_precipitation",
        "api_version": None,
        "source_unit": "mm/hr",
        "converter": "mm_per_hour_to_mm_per_month",
        "display_unit": "mm/month",
        "first_year": 2001,
        "label": "GPM IMERG precipitation",
        "theme": "precipitation",
        "definition": "Total rain and snow per month, from the GPM IMERG satellite-gauge product (Final Run). "
                      "One grid cell of about 10 × 10 km.",
    },
    "GLDAS_SSM": {
        "api_id": "GLDAS_NOAH025_M_2_1_SoilMoi0_10cm_inst",
        "api_version": None,
        "source_unit": "kg m-2",
        "converter": "identity",
        "display_unit": "mm water (top 10 cm)",
        "first_year": 2001,
        "label": "GLDAS soil moisture (0–10 cm)",
        "theme": "soil moisture",
        "definition": "Water held in the top 10 cm of soil, from the GLDAS Noah land-surface model "
                      "(1 kg/m² = 1 mm of water). One grid cell of about 25 × 25 km.",
    },
}
LAST_YEAR = 2025
# Preset places (query points; the data come from the grid cell containing each point).
PLACES = {
    "Milan": (45.4642, 9.19),
    "Po Valley": (45.0, 10.0),
    "Seville": (37.39, -5.99),
    "Niamey": (13.51, 2.11),
    "Fairbanks": (64.84, -147.72),
    "Sierra Nevada": (37.87, -119.35),
    "Murray–Darling Basin": (-34.29, 146.05),
}
DEFAULT_VARIABLES = {
    "temperature": ["MERRA2_T2M"],
    "precipitation": ["GPM_PRECIP"],
    "soil moisture": ["GLDAS_SSM"],
}


def get_variable_meta(variable_name: str):
    return SUPPORTED_VARIABLES.get(variable_name)


def meta_for_api_id(api_id: str) -> dict | None:
    return next((m for m in SUPPORTED_VARIABLES.values() if m["api_id"] == api_id), None)


def supported_theme(theme_name: str) -> bool:
    return theme_name.lower() in DEFAULT_VARIABLES
