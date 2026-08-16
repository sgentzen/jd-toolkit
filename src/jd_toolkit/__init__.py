"""jd-toolkit: zero-dependency helpers for job-description text."""

from jd_toolkit.ats import AtsInfo, detect_ats
from jd_toolkit.salary import (
    MAX_PLAUSIBLE_ANNUAL_USD,
    MIN_PLAUSIBLE_ANNUAL_USD,
    SalaryBand,
    html_to_text,
    parse_annual_usd,
)

__all__ = [
    "AtsInfo",
    "detect_ats",
    "SalaryBand",
    "parse_annual_usd",
    "html_to_text",
    "MIN_PLAUSIBLE_ANNUAL_USD",
    "MAX_PLAUSIBLE_ANNUAL_USD",
]
