from dataclasses import dataclass, field
from typing import Literal, Optional

import pandas as pd


@dataclass
class Plan:
    place: str
    lat: float
    lon: float
    variables: list[str]
    start: str
    end: str
    kind: Literal["trend", "two_place"] = "trend"
    mode: Literal["main", "farmer"] = "main"
    season: Optional[list[int]] = None
    lat2: Optional[float] = None
    lon2: Optional[float] = None


@dataclass
class Validation:
    status: Literal["supported", "incomplete", "unsupported"]
    reason: str = ""
    alternative: str = ""


@dataclass
class TrendResult:
    slope_per_decade: float
    ci: tuple[float, float]
    p: float
    # "descriptive only": a slope shown without a significance test (seasonal Sen row).
    verdict: Literal["significant increase", "significant decrease", "not enough evidence", "descriptive only"]
    n: int
    n_eff: float
    r1: float
    coverage: float
    years_needed: float
    sen_per_decade: float
    hac_p: float
    settings: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    hac_ci: tuple[float, float] = (float("nan"), float("nan"))  # 95% normal CI from the HAC SE, per decade


@dataclass
class ChallengeRow:
    check: Literal["date", "region", "method", "coverage"]
    label: str
    result: Optional[TrendResult]  # None when the variant could not be computed (see note)
    note: str
