"""Heuristic JD section extractor — strips non-R&R wording before scoring.

See docs/superpowers/specs/2026-05-24-jd-scoring-extract-r-and-r-design.md
for the section-classification rules these tests enforce.
"""

from __future__ import annotations

from jd_toolkit.sections import ExtractionResult, extract_relevant_sections
from jd_toolkit.sections import _is_heading, _heading_text
from jd_toolkit.sections import strip_jd_boilerplate


def test_extraction_result_is_a_frozen_dataclass_with_documented_fields():
    """The downstream contract is `text`, `mode`, `extracted_chars`,
    `original_chars`. Lock the field set so the scoring event payload
    keeps a stable shape."""
    r = ExtractionResult(
        text="hi",
        mode="filtered",
        extracted_chars=2,
        original_chars=10,
    )
    assert r.text == "hi"
    assert r.mode == "filtered"
    assert r.extracted_chars == 2
    assert r.original_chars == 10


def test_is_heading_markdown_styles():
    assert _is_heading("# Responsibilities")
    assert _is_heading("## What you'll do")
    assert _is_heading("### Bonus")


def test_is_heading_bold_only_line():
    assert _is_heading("**Responsibilities**")
    assert _is_heading("__Requirements__")
    # Surrounding whitespace is OK.
    assert _is_heading("   **Perks**   ")


def test_is_heading_bold_with_trailing_text_is_not_a_heading():
    # Bolded inline word inside a sentence shouldn't trigger.
    assert not _is_heading("We use **Terraform** heavily.")


def test_is_heading_short_colon_terminated_line():
    assert _is_heading("Responsibilities:")
    assert _is_heading("What you'll do:")
    # Long sentence ending in a colon is NOT a heading.
    assert not _is_heading(
        "We are a fast-growing startup and here is what we'd like you to do:"
    )


def test_is_heading_all_caps_short():
    assert _is_heading("REQUIREMENTS")
    assert _is_heading("WHAT YOU WILL DO")
    # Too long — body paragraph in caps is not a heading.
    assert not _is_heading(
        "THIS IS A VERY LONG ALL CAPS LINE THAT SPANS MANY WORDS AND IS DEFINITELY NOT A HEADING"
    )


def test_is_heading_plain_prose_is_not_a_heading():
    assert not _is_heading("You will own the data platform end-to-end.")
    assert not _is_heading("")
    assert not _is_heading("   ")


def test_heading_text_strips_markdown_and_bold_markers():
    assert _heading_text("# Responsibilities") == "Responsibilities"
    assert _heading_text("## What you'll do") == "What you'll do"
    assert _heading_text("**Requirements**") == "Requirements"
    assert _heading_text("__Bonus__") == "Bonus"
    assert _heading_text("Responsibilities:") == "Responsibilities"
    assert _heading_text("REQUIREMENTS") == "REQUIREMENTS"


from jd_toolkit.sections import _classify_heading


def test_classify_include_headings():
    for h in [
        "Responsibilities",
        "Key Responsibilities",
        "What You'll Do",
        "What you will do",
        "Day-to-Day",
        "The Role",
        "Role Overview",
        "About the Role",
        "In This Role",
        "Your Impact",
        "The Work",
        "Requirements",
        "Qualifications",
        "Required Qualifications",
        "Minimum Qualifications",
        "Basic Qualifications",
        "Must Have",
        "Must-haves",
        "What we're looking for",
        "About You",
        "You Have",
        "You Bring",
        "Preferred Qualifications",
        "Nice to Have",
        "Nice-to-haves",
        "Bonus Points",
        "Bonus Qualifications",
        "Ideal Candidate",
    ]:
        assert _classify_heading(h) == "include", h


def test_classify_bare_bonus_does_not_pull_in_compensation_headings():
    """The qualifications-cluster sense of "Bonus" is captured by the
    "Bonus Points" / "Bonus Qualifications" phrases — NOT by a naked
    "bonus" substring. Without this guard, comp headings like "Sign-on
    bonus" or "Salary and bonus structure" would be incorrectly sent to
    Claude as if they were R&R content."""
    # "Sign-on bonus" — no INCLUDE match, no EXCLUDE match → unknown
    # (UNKNOWN sections get dropped, which is the right behavior).
    assert _classify_heading("Sign-on bonus") == "unknown"
    # "Salary and bonus structure" — INCLUDE doesn't match; EXCLUDE
    # catches "salary" → exclude.
    assert _classify_heading("Salary and bonus structure") == "exclude"
    # "Bonus and perks" — INCLUDE doesn't match; EXCLUDE catches "perks".
    assert _classify_heading("Bonus and perks") == "exclude"


def test_classify_exclude_headings():
    for h in [
        "Benefits",
        "Perks",
        "What we offer",
        "What you'll get",
        "Compensation",
        "Salary",
        "Pay Range",
        "Equal Opportunity Employer",
        "EEO Statement",
        "Diversity Statement",
        "About Us",
        "About the Company",
        "Who We Are",
        "Our Company",
        "Our Story",
        "Why Join Us",
        "Culture",
        "Mission",
        "Values",
        "Work Environment",
        "How to Apply",
        "Application Process",
        "Next Steps",
    ]:
        assert _classify_heading(h) == "exclude", h


def test_classify_unknown_heading():
    assert _classify_heading("Technologies") == "unknown"
    assert _classify_heading("Reporting Structure") == "unknown"
    assert _classify_heading("Travel") == "unknown"


def test_classify_include_wins_when_both_match():
    """A heading containing both 'about you' and 'about us' tokens
    classifies as INCLUDE — INCLUDE is checked first."""
    assert _classify_heading("About You and About Us") == "include"


def test_extracts_markdown_responsibilities_and_requirements_drops_benefits():
    jd = (
        "Acme is a fast-growing startup.\n"
        "\n"
        "## Responsibilities\n"
        "- Own the data platform\n"
        "- Mentor engineers\n"
        "\n"
        "## Requirements\n"
        "- 5+ years backend\n"
        "- AWS or GCP\n"
        "\n"
        "## Benefits\n"
        "- Free lunch\n"
        "- Unlimited PTO\n"
    )
    r = extract_relevant_sections(jd)
    assert r.mode == "filtered"
    assert "Own the data platform" in r.text
    assert "5+ years backend" in r.text
    assert "Free lunch" not in r.text
    assert "Unlimited PTO" not in r.text
    # The preamble is preserved.
    assert "Acme is a fast-growing startup." in r.text
    assert r.extracted_chars == len(r.text)
    assert r.original_chars == len(jd)


def test_extracts_bold_heading_style():
    jd = (
        "**What you'll do**\n"
        "- Build pipelines\n"
        "\n"
        "**Requirements**\n"
        "- Python experience\n"
        "\n"
        "**Perks**\n"
        "- Free snacks\n"
    )
    r = extract_relevant_sections(jd)
    assert r.mode == "filtered"
    assert "Build pipelines" in r.text
    assert "Python experience" in r.text
    assert "Free snacks" not in r.text


def test_extracts_colon_terminated_heading_style():
    jd = (
        "Responsibilities:\n"
        "- Operate K8s clusters\n"
        "\n"
        "Benefits:\n"
        "- 401k\n"
    )
    r = extract_relevant_sections(jd)
    assert r.mode == "filtered"
    assert "Operate K8s clusters" in r.text
    assert "401k" not in r.text


def test_extracts_all_caps_heading_style():
    jd = (
        "REQUIREMENTS\n"
        "- Terraform\n"
        "\n"
        "BENEFITS\n"
        "- Health insurance\n"
    )
    r = extract_relevant_sections(jd)
    assert r.mode == "filtered"
    assert "Terraform" in r.text
    assert "Health insurance" not in r.text


def test_only_excluded_sections_falls_back_to_full_jd():
    jd = (
        "## Benefits\n"
        "- 401k\n"
        "\n"
        "## About Us\n"
        "- We're a tiny crew.\n"
    )
    r = extract_relevant_sections(jd)
    assert r.mode == "full_fallback"
    assert r.text == jd
    assert r.extracted_chars == len(jd)
    assert r.original_chars == len(jd)


def test_no_headings_at_all_falls_back():
    jd = "Plain text JD with no headings and not enough length to clear the bar."
    r = extract_relevant_sections(jd)
    assert r.mode == "full_fallback"
    assert r.text == jd


def test_long_preamble_alone_clears_the_fallback_gate():
    """A JD with a substantial role intro before any heading — even when
    the only labelled section is Benefits — should keep the preamble and
    return mode=filtered."""
    preamble = (
        "You will own end-to-end data platform engineering for a 40-person "
        "team. The role spans infrastructure, observability, and developer "
        "experience. You will be the first dedicated platform hire, "
        "reporting to the VP of Engineering. Expect heavy hands-on Terraform, "
        "Kubernetes, and AWS work."
    )
    assert len(preamble) >= 200
    jd = preamble + "\n\n## Benefits\n- Free lunch\n"
    r = extract_relevant_sections(jd)
    assert r.mode == "filtered"
    assert preamble in r.text
    assert "Free lunch" not in r.text


def test_unknown_section_between_two_includes_is_dropped():
    jd = (
        "## Responsibilities\n"
        "- Own the platform\n"
        "\n"
        "## Technologies\n"
        "- Kafka, Spark, BigQuery\n"
        "\n"
        "## Requirements\n"
        "- 5+ years backend\n"
    )
    r = extract_relevant_sections(jd)
    assert r.mode == "filtered"
    assert "Own the platform" in r.text
    assert "5+ years backend" in r.text
    assert "Kafka, Spark, BigQuery" not in r.text


def test_empty_body_falls_back_with_zero_chars():
    r = extract_relevant_sections("")
    assert r.mode == "full_fallback"
    assert r.text == ""
    assert r.extracted_chars == 0
    assert r.original_chars == 0


def test_whitespace_only_body_falls_back():
    jd = "   \n\n   \n"
    r = extract_relevant_sections(jd)
    assert r.mode == "full_fallback"
    assert r.text == jd
    assert r.original_chars == len(jd)


def test_heading_matching_both_lists_classifies_as_include():
    jd = (
        "## About You and About Us\n"
        "- You have 5+ years.\n"
    )
    r = extract_relevant_sections(jd)
    assert r.mode == "filtered"
    assert "You have 5+ years." in r.text


_JD = (
    "Intro paragraph long enough to be a preamble. " * 10 + "\n"
    "## Responsibilities\n- ship code\n"
    "## Benefits\n- snacks\n"
    "## About Us\n- we are great\n"
)


def test_excluded_headings_are_reported_on_filtered_path():
    res = extract_relevant_sections(_JD)
    assert res.mode == "filtered"
    assert "Benefits" in res.excluded_headings
    assert "About Us" in res.excluded_headings
    assert "Responsibilities" not in res.excluded_headings


def test_excluded_headings_empty_on_full_fallback():
    res = extract_relevant_sections("short")
    assert res.mode == "full_fallback"
    assert res.excluded_headings == ()


def test_strip_drops_hiringcafe_nav_and_dedupes_loading_lines():
    raw = (
        "HiringCafe Join our community\n"
        "Loading…Remote · Hybrid · Onsite\n"
        "Loading…Remote · Hybrid · Onsite\n"
        "Loading…Remote · Hybrid · Onsite\n"
        "About the role\n"
        "You will build scoring pipelines.\n"
    )
    out = strip_jd_boilerplate(raw)
    assert "Join our community" not in out
    assert out.count("Loading…Remote · Hybrid · Onsite") == 0
    assert "About the role" in out
    assert "You will build scoring pipelines." in out


def test_strip_is_idempotent_and_preserves_clean_bodies():
    clean = "About the role\nYou will build scoring pipelines.\n"
    assert strip_jd_boilerplate(clean) == strip_jd_boilerplate(strip_jd_boilerplate(clean))
    assert "About the role" in strip_jd_boilerplate(clean)


# ---------------------------------------------------------------------------
# max_chars budget. The library has no default cap — truncation happens only
# when the caller passes a budget.

_BUDGET = 1_000  # arbitrary test budget


def test_oversized_full_fallback_body_is_truncated():
    """A JD with no INCLUDE section and no preamble takes the full_fallback
    path; with a budget the raw body must still be clamped, not returned
    verbatim."""
    raw_jd = "## Random Heading\n" + "x" * (_BUDGET + 500)
    r = extract_relevant_sections(raw_jd, max_chars=_BUDGET)
    assert r.mode == "full_fallback"  # sanity-check the fixture
    assert r.truncated is True
    assert len(r.text) == _BUDGET
    assert r.extracted_chars == _BUDGET
    assert r.original_chars == len(raw_jd)


def test_oversized_filtered_body_is_truncated():
    """An oversized INCLUDE section on the filtered path is clamped the same
    way — the budget applies to whatever text is returned, regardless of
    extraction mode."""
    huge_body = "Own the platform. " * ((_BUDGET // 19) + 50)
    raw_jd = f"## Responsibilities\n{huge_body}\n"
    assert len(raw_jd) > _BUDGET
    r = extract_relevant_sections(raw_jd, max_chars=_BUDGET)
    assert r.mode == "filtered"
    assert r.truncated is True
    assert len(r.text) == _BUDGET
    assert r.extracted_chars == _BUDGET
    assert r.original_chars == len(raw_jd)


def test_no_budget_means_no_truncation():
    """Without max_chars nothing is ever cut, however large the input."""
    raw_jd = "## Responsibilities\n" + "ship code. " * 10_000
    r = extract_relevant_sections(raw_jd)
    assert r.truncated is False
    assert r.extracted_chars == len(r.text)


def test_body_under_budget_is_not_truncated():
    raw_jd = "## Responsibilities\n- ship code\n"
    r = extract_relevant_sections(raw_jd, max_chars=_BUDGET)
    assert r.truncated is False
    assert r.text == "## Responsibilities\n- ship code"


def test_apply_budget_exact_boundary_is_not_truncated():
    """Text exactly max_chars long must pass through untouched — the clamp
    is `>`, not `>=`."""
    from jd_toolkit.sections import _apply_budget

    text = "y" * _BUDGET
    out, truncated = _apply_budget(text, _BUDGET)
    assert truncated is False
    assert out == text


def test_apply_budget_one_char_over_is_truncated():
    """One char past the budget is the smallest input that must clamp."""
    from jd_toolkit.sections import _apply_budget

    text = "y" * (_BUDGET + 1)
    out, truncated = _apply_budget(text, _BUDGET)
    assert truncated is True
    assert len(out) == _BUDGET
    assert out == "y" * _BUDGET


def test_apply_budget_none_is_a_no_op():
    from jd_toolkit.sections import _apply_budget

    text = "y" * 50_000
    out, truncated = _apply_budget(text, None)
    assert truncated is False
    assert out == text


def test_excluded_headings_and_truncation_coexist_on_filtered_path():
    """Both `excluded_headings` and `truncated` must be populated together
    rather than one silently overriding the other."""
    huge_body = "Own the platform. " * ((_BUDGET // 19) + 50)
    raw_jd = (
        "## Compensation\n"
        "- $150k-$180k base plus bonus\n"
        "\n"
        f"## Responsibilities\n{huge_body}\n"
    )
    r = extract_relevant_sections(raw_jd, max_chars=_BUDGET)
    assert r.mode == "filtered"
    assert r.truncated is True
    assert "Compensation" in r.excluded_headings
    assert len(r.text) == _BUDGET
