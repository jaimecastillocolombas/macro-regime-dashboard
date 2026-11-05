"""Catalogue of derived series, computed on read from the stored ones.

US 10Y-2Y and 10Y-3M spreads are not derived here: FRED publishes them (T10Y2Y, T10Y3M).
"""

from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd

from src.transform.series import spread, yoy


@dataclass(frozen=True)
class DerivedSpec:
    name: str
    inputs: tuple[str, ...]  # stored series it is built from
    build: Callable[..., pd.DataFrame]  # receives the inputs, in order
    unit: str


CATALOGUE: tuple[DerivedSpec, ...] = (
    DerivedSpec("US_CPI_YOY", ("CPIAUCNS",), yoy, "percent y/y"),
    DerivedSpec("US_CPI_CORE_YOY", ("CPILFENS",), yoy, "percent y/y"),
    DerivedSpec("EA_SLOPE_10Y2Y", ("EA_YC_10Y", "EA_YC_2Y"), spread, "percentage points"),
    DerivedSpec("EA_SLOPE_10Y3M", ("EA_YC_10Y", "EA_YC_3M"), spread, "percentage points"),
    DerivedSpec("ES_DE_SPREAD", ("ES_LTR_10Y", "DE_LTR_10Y"), spread, "percentage points"),
)
DERIVED = {spec.name: spec for spec in CATALOGUE}


def required_inputs(names: list[str] | None = None) -> set[str]:
    """Stored series needed to build ``names`` (every derived series by default)."""
    return {i for name in names or DERIVED for i in DERIVED[name].inputs}


def build(
    stored: dict[str, pd.DataFrame], names: list[str] | None = None
) -> dict[str, pd.DataFrame]:
    """Build the requested derived series from already-loaded stored series."""
    return {
        name: DERIVED[name].build(*(stored[i] for i in DERIVED[name].inputs))
        for name in names or DERIVED
    }
