"""Salary extraction from JD prose.

Every string in the "real" cases below was captured live from Workday postings
on 2026-07-30 (see TASKS.md #20), including the traps: a perks blurb offering
"$0 delivery fees", and project budgets in the millions that even carry a
"/year" suffix.
"""
from __future__ import annotations

import pytest

from jd_toolkit.salary import parse_annual_usd

# --- real bands that must be read -------------------------------------------

REAL_BANDS = [
    ("Illinois: $158,500 - $172,000 per year", 158500, 172000),
    ("New York: $176,000 - $191,000 per year", 176000, 191000),
    ("New York Base Salary: $123,000-$130,000", 123000, 130000),
    ("New Jersey & New York Base Salary: $149,000 - $157,000", 149000, 157000),
    ("$210,000 - $220,500 per year", 210000, 220500),
    ("Pennsylvania: $108,500 - $128,500 per year", 108500, 128500),
    ("The targeted base salary range for this role is $102,000-$154,000 per year",
     102000, 154000),
    ("The base pay range is $95,000- $120,000", 95000, 120000),
    ("Salary range: $150K - $200K", 150000, 200000),
    ("Annual salary of $180,000 to $210,000", 180000, 210000),
]


@pytest.mark.parametrize("text, low, high", REAL_BANDS)
def test_reads_real_salary_bands(text, low, high):
    result = parse_annual_usd(text)
    assert result is not None, f"failed to parse: {text}"
    assert (result.min_usd, result.max_usd) == (low, high)


# --- traps that must NOT be read as salary ----------------------------------

TRAPS = [
    # Perks blurb. Appeared in EVERY sampled Wonder posting.
    "Enjoy everything from tacos to Thai with $0 delivery fees, plus dine-in "
    "or pick up at a Wonder location near you",
    # Project budgets. The second one even says "/year".
    "responsible for the planning, budget, schedule, and execution of small to "
    "medium-scale projects with a budget of $20-$100 million",
    "Typically, two plus years experience working as a Project Engineer on "
    "projects in the $5 million-$25 million/year range",
    # Money with no salary context at all.
    "We raised $50,000,000 in Series C funding",
    "Employees receive a $1,500 annual learning stipend",
    # No money at all.
    "We are an equal opportunity employer.",
    "",
]


@pytest.mark.parametrize("text", TRAPS)
def test_rejects_non_salary_money(text):
    assert parse_annual_usd(text) is None, f"wrongly parsed: {text[:60]}"


# --- structure --------------------------------------------------------------

def test_unions_multiple_level_bands():
    """A posting priced per level publishes several bands. Same rule as the
    Greenhouse geo zones: union rather than pick one."""
    text = ("Salary range by level. Level I: $81,314 - $135,524 / "
            "Level II: $88,725 - $147,875 / Level V: $165,000 - $190,000")
    result = parse_annual_usd(text)
    assert (result.min_usd, result.max_usd) == (81314, 190000)


def test_ignores_budget_band_beside_a_real_salary():
    text = ("The base salary range is $120,000 - $150,000 per year. You will "
            "manage projects with a budget of $20-$100 million.")
    result = parse_annual_usd(text)
    assert (result.min_usd, result.max_usd) == (120000, 150000)


def test_hourly_rate_is_not_read_as_annual():
    assert parse_annual_usd("The pay rate is $85.00 - $120.00 per hour") is None


# --- max_chars ---------------------------------------------------------------
# `_vouched_for` runs `finditer` over the full text per candidate band, so cost
# is quadratic in document length. `max_chars` lets a caller bound that before
# handing this parser attacker-controlled prose (a hostile ATS response body).

def test_max_chars_none_by_default_does_not_truncate():
    text = ("filler " * 5000) + "Base salary range: $150,000 - $180,000"
    result = parse_annual_usd(text)
    assert result is not None
    assert (result.min_usd, result.max_usd) == (150000, 180000)


def test_max_chars_drops_a_band_that_falls_past_the_cap():
    prefix = "filler " * 5000
    text = prefix + "Base salary range: $150,000 - $180,000"
    result = parse_annual_usd(text, max_chars=len(prefix) - 10)
    assert result is None


def test_max_chars_still_finds_a_band_within_the_cap():
    text = "Base salary range: $150,000 - $180,000" + (" filler" * 5000)
    result = parse_annual_usd(text, max_chars=1000)
    assert result is not None
    assert (result.min_usd, result.max_usd) == (150000, 180000)


def test_implausibly_large_band_is_rejected():
    """Guards the '$5 million-$25 million/year' class."""
    assert parse_annual_usd("Salary range $5,000,000 - $25,000,000 per year") is None


def test_single_amount_is_not_a_band():
    """One number is an anchor, not a range — too easy to misread a bonus or
    stipend as a salary."""
    assert parse_annual_usd("The base salary is $150,000 per year") is None


def test_strips_html_before_matching():
    html = "<p><span>Illinois: $158,500 - $172,000 per year</span></p>"
    result = parse_annual_usd(html)
    assert (result.min_usd, result.max_usd) == (158500, 172000)


def test_handles_html_entities():
    text = "New Jersey &amp; New York Base Salary: $149,000 - $157,000"
    result = parse_annual_usd(text)
    assert (result.min_usd, result.max_usd) == (149000, 157000)


def test_raw_records_the_matched_text():
    result = parse_annual_usd("Illinois: $158,500 - $172,000 per year")
    assert "158,500" in result.raw
    assert "172,000" in result.raw


def test_inverted_band_is_rejected():
    assert parse_annual_usd("Salary range: $200,000 - $150,000 per year") is None


def test_none_and_non_string_are_safe():
    assert parse_annual_usd(None) is None
    assert parse_annual_usd(12345) is None


# --- regressions from code review -------------------------------------------

# Money that sits INSIDE a compensation section, beside real salary wording.
# These are the dangerous ones: asserted in isolation they'd pass for the wrong
# reason, so each keeps the salary word that made the parser accept it.
COMP_SECTION_TRAPS = [
    # Read wrongly this stores max_usd=40000 and bins a $180k job.
    "Base salary for this role is $180,000. Annual bonus target of $20,000 - $40,000.",
    "Compensation includes an equity grant valued at $200,000 - $400,000 over four years.",
    "Base salary commensurate with experience. Relocation assistance of "
    "$15,000 - $30,000 is available.",
    "We offer tuition reimbursement of $20,000 - $25,000 per year toward a degree.",
    "Salary continuation severance of $50,000 - $90,000 depending on tenure.",
    "You will own an annual quota of $800,000 - $950,000 in new business. "
    "Base salary is competitive.",
    "Base salary is market competitive. 401(k) match of $16,000 - $20,000 annually.",
    "Managing accounts with contract sizes of $100,000 - $500,000 per year; "
    "base pay is competitive.",
    "Drive cost savings of $250,000 - $400,000 annually across the vendor portfolio.",
    # "base" alone must not vouch — it is a noun in plenty of other sentences.
    "Our customer base grew fast. Deals of $100,000 - $200,000 closed this year.",
]


@pytest.mark.parametrize("text", COMP_SECTION_TRAPS)
def test_rejects_non_salary_money_beside_salary_wording(text):
    assert parse_annual_usd(text) is None, f"wrongly parsed: {text[:70]}"


def test_real_salary_survives_a_bonus_mentioned_after_it():
    """The mirror of the traps: a genuine band must not be vetoed just because
    a bonus is mentioned later in the same paragraph."""
    result = parse_annual_usd(
        "The base salary range is $190,000 - $240,000 per year. "
        "Signing bonus of $25,000 - $50,000."
    )
    assert (result.min_usd, result.max_usd) == (190000, 240000)


def test_state_name_after_a_band_does_not_void_it():
    """Regression: an unanchored [KkMm] suffix ate the K of "Kentucky", turned
    172,000 into 172,000 million, and silently dropped the Illinois band — so
    the union came out LOWER than the truth and binned a $172k job."""
    result = parse_annual_usd(
        "Base salary range by state. Illinois: $158,500 - $172,000 "
        "Kentucky: $120,000 - $135,000"
    )
    assert (result.min_usd, result.max_usd) == (120000, 172000)


def test_word_starting_with_m_after_a_band_does_not_void_it():
    result = parse_annual_usd("Base salary range $120,000 - $150,000 Massachusetts residents only")
    assert (result.min_usd, result.max_usd) == (120000, 150000)


@pytest.mark.parametrize("text", [
    "budget $100,000 - $150,000 salary",
    "salary $100,000 - $150,000 budget",
])
def test_veto_verdict_is_symmetric(text):
    """Regression: the band regex consumed trailing whitespace, so a signal
    after the band measured closer than the same signal before it, and these
    two returned opposite verdicts."""
    assert parse_annual_usd(text) is None


@pytest.mark.parametrize("text", [
    "Salary range: $120,000 - $150,000 CAD per year",
    "Base salary range: CA$120,000 - CA$150,000",
    "Salary range: $120,000 - $150,000 AUD",
])
def test_foreign_currency_band_is_rejected(text):
    """min_usd/max_usd are USD by contract and Workday has heavy Canadian and
    Australian tenancy."""
    assert parse_annual_usd(text) is None


@pytest.mark.parametrize("dash", ["-", "‐", "‑", "–", "—", "―", "−"])
def test_unicode_dashes_are_accepted(dash):
    result = parse_annual_usd(f"Base salary range $120,000 {dash} $150,000")
    assert result is not None, f"dash U+{ord(dash):04X} not handled"
    assert (result.min_usd, result.max_usd) == (120000, 150000)


def test_raw_is_capped():
    """raw is meant for verbatim display."""
    bands = " / ".join(
        f"Level {i}: ${100 + i},000 - ${150 + i},000" for i in range(1, 12)
    )
    result = parse_annual_usd("Base salary range by level. " + bands)
    assert len(result.raw) < 200
    assert "more)" in result.raw


def test_module_imports_standalone():
    """Regression guard: salary.py must import cleanly on its own, without
    relying on another module in the package having been imported first."""
    import subprocess
    import sys
    proc = subprocess.run(
        [sys.executable, "-c",
         "import jd_toolkit.salary as m; print(m.parse_annual_usd('') is None)"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr[-400:]
    assert "True" in proc.stdout


# --- "between X and Y" (iCIMS listings phrase it this way) -------------------

def test_reads_between_x_and_y():
    """Observed live on iCIMS: "The salary range for this position is typically
    between $125,000 and $150,000 base salary plus commision." """
    result = parse_annual_usd(
        "The salary range for this position is typically between $125,000 and "
        "$150,000 base salary plus commision."
    )
    assert (result.min_usd, result.max_usd) == (125000, 150000)


def test_bare_and_is_not_a_range_separator():
    """Without "between", `and` joins unrelated amounts far more often than it
    joins a band — and both of these should be vetoed anyway."""
    assert parse_annual_usd(
        "Base salary is competitive. A $20,000 bonus and $30,000 relocation are offered."
    ) is None
    assert parse_annual_usd(
        "Salary is competitive; we manage budgets of $50,000 and $90,000 per project."
    ) is None
