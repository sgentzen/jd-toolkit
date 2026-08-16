"""ATS detection — pure host-suffix matcher."""

from __future__ import annotations

import pytest

from jd_toolkit.ats import detect_ats


@pytest.mark.parametrize(
    ("url", "expected_slug"),
    [
        # Greenhouse — multiple known subdomains
        ("https://boards.greenhouse.io/acme/jobs/12345", "greenhouse"),
        ("https://job-boards.greenhouse.io/acme/jobs/12345", "greenhouse"),
        # Lever
        ("https://jobs.lever.co/acme/abc-123", "lever"),
        # Workday — tenant subdomain
        ("https://acme.wd5.myworkdayjobs.com/External/job/X", "workday"),
        ("https://acme.myworkday.com/job/12345", "workday"),
        # Ashby
        ("https://jobs.ashbyhq.com/acme/abc-123", "ashby"),
        # Workable
        ("https://apply.workable.com/acme/j/ABC123", "workable"),
        # SmartRecruiters / iCIMS / Jobvite / Taleo / BambooHR
        ("https://careers.smartrecruiters.com/Acme/abc", "smartrecruiters"),
        ("https://careers-acme.icims.com/jobs/123", "icims"),
        ("https://jobs.jobvite.com/acme/job/abc", "jobvite"),
        ("https://acme.taleo.net/careersection/x/jobsearch.ftl", "taleo"),
        ("https://acme.bamboohr.com/jobs/view.php?id=1", "bamboohr"),
        # Enterprise HCM suites
        ("https://career5.successfactors.com/sfcareer/jobreqcareer?jobId=1", "successfactors"),
        ("https://acme.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/job/1", "oracle"),
        ("https://workforcenow.adp.com/mascsr/default/mdf/recruitment/recruitment.html", "adp"),
        ("https://recruiting.ultipro.com/ACM1000/JobBoard/abc/Opportunity/1", "ukg"),
        ("https://recruiting.paylocity.com/Recruiting/Jobs/Details/12345", "paylocity"),
        ("https://acme.dayforcehcm.com/CandidatePortal/en-US/acme/Posting/View/1", "dayforce"),
        ("https://acme.applytojob.com/apply/abc123", "jazzhr"),
        # Aggregators
        ("https://hiring.cafe/job/abc123", "hiringcafe"),
        ("https://www.linkedin.com/jobs/view/12345", "linkedin"),
        ("https://www.indeed.com/viewjob?jk=abc", "indeed"),
        # Unknown — direct careers pages and malformed inputs
        ("https://careers.example.com/jobs/123", "unknown"),
        ("https://example.com/jobs", "unknown"),
        ("", "unknown"),
        ("not a url", "unknown"),
    ],
)
def test_detect_ats(url: str, expected_slug: str) -> None:
    assert detect_ats(url).slug == expected_slug


def test_detect_ats_none() -> None:
    assert detect_ats(None).slug == "unknown"


def test_detect_ats_name_populated() -> None:
    info = detect_ats("https://boards.greenhouse.io/acme/jobs/12345")
    assert info.name == "Greenhouse"
    assert detect_ats(None).name  # always non-empty
