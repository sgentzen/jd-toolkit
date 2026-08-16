"""Extract an annual USD salary band from job-description prose.

Board APIs that publish structured pay (Lever's `salaryRange`, Greenhouse's
`pay_input_ranges`) are better read directly. This module is the fallback for
boards that publish nothing structured — Workday chief among them, whose CXS
detail endpoint returns the pay only as prose inside `jobDescription`.

The output is an annual-base-USD band. A wrong number is worse than no number:
consumers typically gate or rank on it, and a bad parse can bury a well-paid
role. So this parser is deliberately conservative and returns None whenever it
cannot be confident.

Grounded in a live survey of 40 Workday postings (2026-07-30). What that showed:

- Real bands are almost always two amounts joined by a dash or "to", with a
  salary word nearby: "Illinois: $158,500 - $172,000 per year".
- Money in a JD is usually NOT salary. Every sampled Wonder posting carried a
  perks line offering "$0 delivery fees"; engineering postings quote project
  budgets like "$20-$100 million" and even "$5 million-$25 million/year".

Hence the rules: a band needs two amounts and a plausible annual magnitude, and
it must be vouched for by nearby wording. Vouching is deliberately asymmetric —
only a phrase that NAMES the base salary can out-argue a disqualifier, and only
by sitting closer. A bare "per year" cannot, because it sits just as happily
beside a tuition reimbursement. See `_vouched_for`.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass

# Below this, a "salary" is not a plausible annual US figure — full-time at the
# federal minimum wage is about $15,080/yr. Boards publish hourly rates under
# annual-looking labels, and a structured cadence field often doesn't exist.
#
# Public so callers can apply the same plausibility floor when gating
# structured feeds that this module never sees.
MIN_PLAUSIBLE_ANNUAL_USD = 15_000

# A salary above this is not a salary — it is a budget, a valuation, or a
# funding round. "$5 million-$25 million/year" was observed live, carrying a
# per-year suffix that would otherwise read as annual.
MAX_PLAUSIBLE_ANNUAL_USD = 1_000_000

# How far away a salary word may sit and still vouch for a band. Generous,
# because the deciding rule is proximity rather than presence: a disqualifier
# only vetoes when it is CLOSER to the band than the salary word is. A fixed
# window alone got both cases wrong — a budget mentioned after a real salary
# vetoed it, and the last of several per-level bands fell outside the window.
_CONTEXT_CHARS = 200

# `raw` is meant for verbatim display; a per-level table can carry a dozen bands.
_MAX_RAW_BANDS = 4

# STRONG phrases name the base salary itself. Only these may out-argue a
# disqualifier, and only by sitting closer to the band.
_STRONG_SALARY = re.compile(
    r"\b(?:base\s+(?:salary|pay|compensation)|salary\s+range|pay\s+range"
    r"|pay\s+scale|salary\s+for\s+this|compensation\s+range|annual\s+salary"
    r"|target(?:ed)?\s+base|starting\s+salary)\b",
    re.IGNORECASE,
)

# WEAK signals are consistent with a salary but name nothing — "per year" sits
# just as happily beside a tuition reimbursement. They can vouch for a band on
# their own, but they can NEVER override a disqualifier.
_WEAK_SALARY = re.compile(
    r"\b(?:salary|salaries|compensation|per\s+year|per\s+annum|annually"
    r"|annualized|annualised)\b|/\s*yr\b",
    re.IGNORECASE,
)

# Money that sits inside a compensation section but is NOT base salary. This
# list can never be complete, which is why it is paired with the rule above:
# an unrecognised veto still loses only if a STRONG phrase is nearer.
_DISQUALIFIERS = re.compile(
    r"\b(?:budget|revenue|funding|raised|valuation|portfolio|assets"
    r"|stipend|bonus(?:es)?|equity|RSUs?|stock|grant|relocation|tuition"
    r"|reimbursement|severance|401\s*\(?k\)?|match(?:ing)?|quota|commissions?"
    r"|OTE|savings|contract\s+(?:value|size)s?|deals?\s+sizes?|deals?"
    r"|award|sign(?:-|\s)?on|delivery\s+fees?|per\s+(?:online\s+)?assignment"
    r"|scholarship|discount)\b",
    re.IGNORECASE,
)

# A trailing or leading non-USD currency code voids the band: the output is
# USD by contract, and Workday has heavy Canadian and Australian tenancy.
_FOREIGN_CURRENCY = re.compile(
    r"\b(?:CAD|AUD|NZD|SGD|GBP|EUR|INR|MXN)\b|\b(?:CA|A|NZ|S)\$",
    re.IGNORECASE,
)

# Sub-annual cadence anywhere near the band rules it out — the band is annual.
_SUB_ANNUAL = re.compile(
    r"\b(?:per\s+hour|hourly|an\s+hour|/\s*hr\b|per\s+week|weekly"
    r"|per\s+month|monthly|per\s+day|daily)\b",
    re.IGNORECASE,
)

# The magnitude suffix is \b-anchored. Unanchored, `[KkMm]` swallowed the first
# letter of the next word — "$172,000 Kentucky: ..." became 172,000 million,
# blew past the plausibility ceiling, and silently voided a real band.
_SUFFIX = r"(?:(million|billion|[KkMm])\b)?"
_DASH = r"[-‐‑–—―−]"
_AMOUNT = rf"\$\s?(\d[\d,]*(?:\.\d+)?)\s*{_SUFFIX}"
_BAND = re.compile(
    rf"{_AMOUNT}\s*(?:{_DASH}|to|through)\s*\$?\s?(\d[\d,]*(?:\.\d+)?)\s*{_SUFFIX}",
    re.IGNORECASE,
)

# "between X and Y" is a range; a bare "and" is not. iCIMS listings phrase pay
# this way ("typically between $125,000 and $150,000 base salary"), but `and`
# joins unrelated amounts far more often than it joins a band — "a $20,000
# bonus and $30,000 relocation" — so the idiom is required, not just the word.
_BETWEEN_BAND = re.compile(
    rf"between\s+{_AMOUNT}\s*and\s*\$?\s?(\d[\d,]*(?:\.\d+)?)\s*{_SUFFIX}",
    re.IGNORECASE,
)

_MULTIPLIERS = {
    "k": 1_000, "m": 1_000_000,
    "million": 1_000_000, "billion": 1_000_000_000,
}


@dataclass(frozen=True, slots=True)
class SalaryBand:
    min_usd: int | None
    max_usd: int | None
    raw: str


def _to_amount(digits: str, suffix: str | None) -> int | None:
    try:
        value = float(digits.replace(",", ""))
    except ValueError:
        return None
    if suffix:
        value *= _MULTIPLIERS.get(suffix.lower(), 1)
    return int(value)


def _plausible(low: int, high: int) -> bool:
    return (
        low <= high
        and low >= MIN_PLAUSIBLE_ANNUAL_USD
        and high <= MAX_PLAUSIBLE_ANNUAL_USD
    )


def html_to_text(raw: object) -> str:
    """HTML/entities -> collapsed plain text. Public: callers storing a JD
    body reuse it so the stored text is never markup."""
    if not isinstance(raw, str) or not raw.strip():
        return ""
    text = html.unescape(html.unescape(raw))       # entities survive one round
    text = re.sub(r"<[^>]+>", " ", text)           # strip tags
    return re.sub(r"\s+", " ", text)


def _nearest(pattern: re.Pattern[str], text: str, start: int, end: int) -> int | None:
    """Distance in characters from the span to the closest match, or None."""
    best: int | None = None
    for m in pattern.finditer(text):
        gap = start - m.end() if m.end() <= start else m.start() - end
        gap = max(gap, 0)
        if best is None or gap < best:
            best = gap
    return best


def _vouched_for(text: str, start: int, end: int) -> bool:
    """True when this band is a base-salary band.

    Two rules, and the second is the important one:

    1. Some salary signal (strong or weak) must be within `_CONTEXT_CHARS`.
    2. If anything disqualifying is in range, the band survives ONLY when a
       STRONG phrase sits strictly nearer than the disqualifier.

    Rule 2 is deliberately asymmetric. An earlier version let any salary word
    out-argue a veto by proximity, which meant "tuition reimbursement of
    $20,000 - $25,000 per year" parsed as a salary — "per year" was closer to
    the band than "reimbursement" was. A weak word must never be able to do
    that, because the veto list can never be complete and weak words are
    everywhere. "Base salary for this role is $180,000. Annual bonus target of
    $20,000 - $40,000." is the case that matters: read wrongly it stores
    max_usd=40000 and bins a $180k job.
    """
    strong = _nearest(_STRONG_SALARY, text, start, end)
    weak = _nearest(_WEAK_SALARY, text, start, end)
    nearest_salary = min(
        (d for d in (strong, weak) if d is not None), default=None
    )
    if nearest_salary is None or nearest_salary > _CONTEXT_CHARS:
        return False

    for veto in (_DISQUALIFIERS, _SUB_ANNUAL, _FOREIGN_CURRENCY):
        near = _nearest(veto, text, start, end)
        if near is None or near > _CONTEXT_CHARS:
            continue
        if strong is None or strong > near:
            return False
    return True


def parse_annual_usd(raw: object) -> SalaryBand | None:
    """Best-effort annual USD band from JD prose, or None when unsure.

    Every candidate band must clear three independent checks: two amounts, a
    salary word nearer to it than any disqualifier or sub-annual cadence, and a
    plausible annual magnitude. Surviving bands are unioned, mirroring the
    Greenhouse geo-zone rule — we can't know which band applies, so the honest
    answer is the span the employer published.
    """
    text = html_to_text(raw)
    if not text:
        return None

    lows: list[int] = []
    highs: list[int] = []
    matched: list[str] = []
    seen_spans: set[tuple[int, int]] = set()
    candidates = sorted(
        [*_BAND.finditer(text), *_BETWEEN_BAND.finditer(text)],
        key=lambda mm: mm.start(),
    )
    for m in candidates:
        # The two patterns can cover the same digits; count a band once.
        digits = (m.start(1), m.end(3))
        if digits in seen_spans:
            continue
        seen_spans.add(digits)
        low = _to_amount(m.group(1), m.group(2))
        high = _to_amount(m.group(3), m.group(4))
        if low is None or high is None:
            continue
        if not _plausible(low, high):
            continue
        # Measure from the numeric content only. `_BAND` can consume trailing
        # whitespace via its optional suffix, which pushed `m.end()` past the
        # digits and made every signal AFTER the band measure one char closer
        # than one before it — so ties resolved by which side the veto sat on.
        span_end = m.start() + len(m.group(0).rstrip())
        if not _vouched_for(text, m.start(), span_end):
            continue

        lows.append(low)
        highs.append(high)
        matched.append(m.group(0).strip())

    if not lows:
        return None
    # `raw` is meant for verbatim display, so cap it rather than pasting
    # every band from a long per-level table.
    shown = matched[:_MAX_RAW_BANDS]
    raw = "; ".join(shown)
    if len(matched) > _MAX_RAW_BANDS:
        raw += f"; (+{len(matched) - _MAX_RAW_BANDS} more)"
    return SalaryBand(min(lows), max(highs), raw)
