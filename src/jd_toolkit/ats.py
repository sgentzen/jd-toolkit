"""Detect the Applicant Tracking System (ATS) behind a job posting URL.

Pure, deterministic host-suffix match. No network. No caching. Cheap enough
to call on every posting. Unknown / non-ATS hosts (company careers pages,
aggregator listings whose downstream ATS is opaque) return the `unknown`
slug rather than guessing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class AtsInfo:
    slug: str
    name: str


_UNKNOWN: Final = AtsInfo(slug="unknown", name="Unknown / direct careers page")


# Host-suffix → (slug, display name). First match wins. Ordering matters
# only for overlapping suffixes (e.g. a future `jobs.lever.co` subdomain
# would still match the broader `.lever.co` rule below).
_HOST_RULES: Final[tuple[tuple[str, AtsInfo], ...]] = (
    ("boards.greenhouse.io", AtsInfo("greenhouse", "Greenhouse")),
    ("job-boards.greenhouse.io", AtsInfo("greenhouse", "Greenhouse")),
    ("greenhouse.io", AtsInfo("greenhouse", "Greenhouse")),
    ("jobs.lever.co", AtsInfo("lever", "Lever")),
    ("lever.co", AtsInfo("lever", "Lever")),
    ("myworkdayjobs.com", AtsInfo("workday", "Workday")),
    ("myworkday.com", AtsInfo("workday", "Workday")),
    ("jobs.ashbyhq.com", AtsInfo("ashby", "Ashby")),
    ("ashbyhq.com", AtsInfo("ashby", "Ashby")),
    ("apply.workable.com", AtsInfo("workable", "Workable")),
    ("workable.com", AtsInfo("workable", "Workable")),
    ("smartrecruiters.com", AtsInfo("smartrecruiters", "SmartRecruiters")),
    ("icims.com", AtsInfo("icims", "iCIMS")),
    ("jobvite.com", AtsInfo("jobvite", "Jobvite")),
    ("taleo.net", AtsInfo("taleo", "Taleo")),
    ("bamboohr.com", AtsInfo("bamboohr", "BambooHR")),
    ("recruitee.com", AtsInfo("recruitee", "Recruitee")),
    ("breezy.hr", AtsInfo("breezy", "Breezy HR")),
    ("rippling.com", AtsInfo("rippling", "Rippling")),
    # Enterprise HCM suites — common among federal contractors, healthcare,
    # and finance employers.
    ("successfactors.com", AtsInfo("successfactors", "SAP SuccessFactors")),
    ("successfactors.eu", AtsInfo("successfactors", "SAP SuccessFactors")),
    ("oraclecloud.com", AtsInfo("oracle", "Oracle Recruiting Cloud")),
    ("adp.com", AtsInfo("adp", "ADP Workforce Now")),
    ("ultipro.com", AtsInfo("ukg", "UKG Pro Recruiting (UltiPro)")),
    ("ukg.net", AtsInfo("ukg", "UKG Pro Recruiting (UltiPro)")),
    ("paylocity.com", AtsInfo("paylocity", "Paylocity Recruiting")),
    ("dayforcehcm.com", AtsInfo("dayforce", "Dayforce (Ceridian)")),
    ("applytojob.com", AtsInfo("jazzhr", "JazzHR")),
    # Aggregators — downstream ATS is hidden, so we mark them out separately.
    ("hiring.cafe", AtsInfo("hiringcafe", "hiring.cafe (aggregator)")),
    ("linkedin.com", AtsInfo("linkedin", "LinkedIn (aggregator)")),
    ("indeed.com", AtsInfo("indeed", "Indeed (aggregator)")),
    ("glassdoor.com", AtsInfo("glassdoor", "Glassdoor (aggregator)")),
    ("ziprecruiter.com", AtsInfo("ziprecruiter", "ZipRecruiter (aggregator)")),
)


def detect_ats(source_url: str | None) -> AtsInfo:
    """Map a posting URL to its ATS. Returns `unknown` for empty / unmatched
    inputs. Never raises — the caller can pass `None`, a raw string, or even
    a malformed URL."""
    if not source_url:
        return _UNKNOWN
    try:
        host = (urlparse(source_url).hostname or "").lower()
    except (ValueError, AttributeError):
        return _UNKNOWN
    if not host:
        return _UNKNOWN
    for suffix, info in _HOST_RULES:
        if host == suffix or host.endswith("." + suffix):
            return info
    return _UNKNOWN
