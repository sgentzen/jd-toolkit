"""jd-toolkit: zero-dependency helpers for job-description text.

- `parse_annual_usd` — conservative annual-USD salary band from JD prose.
- `extract_relevant_sections` — responsibilities/requirements-only extraction.
- `detect_ats` — applicant-tracking-system detection from a posting URL.
"""

from jd_toolkit.ats import AtsInfo, detect_ats
from jd_toolkit.salary import (
    MAX_PLAUSIBLE_ANNUAL_USD,
    MIN_PLAUSIBLE_ANNUAL_USD,
    SalaryBand,
    html_to_text,
    parse_annual_usd,
)
from jd_toolkit.sections import (
    ExtractionResult,
    extract_relevant_sections,
    strip_jd_boilerplate,
)

__all__ = [
    "AtsInfo",
    "ExtractionResult",
    "MAX_PLAUSIBLE_ANNUAL_USD",
    "MIN_PLAUSIBLE_ANNUAL_USD",
    "SalaryBand",
    "detect_ats",
    "extract_relevant_sections",
    "html_to_text",
    "parse_annual_usd",
    "strip_jd_boilerplate",
]
