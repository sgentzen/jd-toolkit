"""Heuristic JD section extractor.

Walks a JD body line-by-line, detects section headings, classifies each
section as INCLUDE / EXCLUDE / UNKNOWN, and returns the concatenation of
INCLUDE-section bodies (plus any preamble before the first heading) — the
responsibilities-and-requirements core of the posting, with benefits, EEO
and company boilerplate dropped. Falls back to the full body when no
INCLUDE section is found and the preamble is too short to stand alone.

Pure functions — no I/O, no logging.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ExtractionResult:
    """What `extract_relevant_sections` returns.

    `text` is the extracted body. On the `filtered` path it's the
    concatenated INCLUDE sections (plus preamble). On the `full_fallback`
    path it's `raw_jd` verbatim — the caller can detect the fallback via
    `mode`. Either path is subject to the caller-supplied `max_chars`
    budget, so `text` is always the final, possibly-truncated string.

    `extracted_chars` is `len(text)` either way (so it always describes
    what's actually being sent — post-truncation). `original_chars` is
    `len(raw_jd)`, unaffected by truncation."""

    text: str
    mode: Literal["filtered", "full_fallback"]
    extracted_chars: int
    original_chars: int
    # Headings of sections dropped on the filtered path (EXCLUDE + UNKNOWN
    # classifications with a non-empty body). Empty on full_fallback. Lets
    # callers acknowledge what was dropped.
    excluded_headings: tuple[str, ...] = ()
    # True when `text` was cut short by the caller-supplied `max_chars`.
    # Lets callers surface the cutoff (e.g. to an LLM consumer) instead of
    # quietly treating a mid-sentence cutoff as the whole JD.
    truncated: bool = False


# A heading line is short. Six words covers "Preferred Qualifications / Bonus Points"
# style headings without admitting sentence fragments.
_MAX_HEADING_WORDS = 6

# Markdown ATX heading: one to six leading `#` chars then whitespace.
_MD_HEADING_RE = re.compile(r"^#{1,6}\s+\S")
# Whole line is **…** or __…__ with nothing else (whitespace allowed at edges).
_BOLD_LINE_RE = re.compile(r"^\s*(?:\*\*[^*]+\*\*|__[^_]+__)\s*$")


def _is_heading(line: str) -> bool:
    """True if `line` looks like a section heading.

    Four styles recognised (see module docstring): Markdown ATX, bold-only,
    short colon-terminated, short ALL-CAPS. Order of checks is cheapest-first.
    """
    stripped = line.strip()
    if not stripped:
        return False

    # 1. Markdown ATX heading.
    if _MD_HEADING_RE.match(stripped):
        return True

    # 2. Bold-only line.
    if _BOLD_LINE_RE.match(line):
        return True

    words = stripped.split()
    if len(words) > _MAX_HEADING_WORDS:
        return False

    # 3. Short colon-terminated line. Reject sentences that happen to end
    #    in a colon by requiring no internal sentence punctuation.
    if stripped.endswith(":") and not any(ch in stripped[:-1] for ch in ".!?,;"):
        return True

    # 4. Short ALL-CAPS line. At least one alphabetic char, all uppercase.
    letters = [c for c in stripped if c.isalpha()]
    if letters and all(c.isupper() for c in letters):
        return True

    return False


def _heading_text(line: str) -> str:
    """Strip heading markers and return the bare heading text.

    Used by the classifier so substring matching ('responsibilities')
    works the same regardless of which heading style the JD uses.
    """
    stripped = line.strip()
    # Markdown ATX: drop leading `#`s and the following whitespace.
    if _MD_HEADING_RE.match(stripped):
        return stripped.lstrip("#").strip()
    # Bold-only: drop the markers.
    if _BOLD_LINE_RE.match(line):
        return stripped.strip("*_").strip()
    # Colon-terminated: drop the trailing colon.
    if stripped.endswith(":"):
        return stripped[:-1].strip()
    # ALL-CAPS or anything else: return as-is.
    return stripped


# Substring patterns matched (case-insensitively) against the heading text.
# Longer / more specific phrases first inside each list so partial matches
# don't preempt them. Each phrase is matched as a plain substring — no regex
# escaping needed because none of these contain regex metacharacters.
_INCLUDE_PHRASES: tuple[str, ...] = (
    # Responsibilities cluster
    "key responsibilities",
    "responsibilities",
    "what you'll do",
    "what you will do",
    "what you'll be doing",
    "what you will be doing",
    "day-to-day",
    "day to day",
    "the role",
    "role overview",
    "about the role",
    "the position",
    "the opportunity",
    "in this role",
    "your role",
    "your impact",
    "your day",
    "the work",
    # Requirements cluster
    "required qualifications",
    "minimum qualifications",
    "basic qualifications",
    "preferred qualifications",
    "qualifications",
    "requirements",
    "must-haves",
    "must haves",
    "must have",
    "what we're looking for",
    "what we are looking for",
    "about you",
    "you have",
    "you bring",
    "you'll need",
    "you will need",
    "nice-to-haves",
    "nice to have",
    "nice to haves",
    "ideal candidate",
    # "bonus" is intentionally NOT bare here. A naked substring match would
    # pull in compensation headings like "Sign-on bonus" and "Salary and
    # bonus structure" — content the spec wants EXCLUDED. The intent is the
    # qualifications-cluster sense ("Bonus Points / Bonus Qualifications").
    "bonus points",
    "bonus qualifications",
)

_EXCLUDE_PHRASES: tuple[str, ...] = (
    "what we offer",
    "what you'll get",
    "what you will get",
    "benefits",
    "perks",
    "compensation",
    "salary",
    "pay range",
    "equal opportunity",
    "eeo",
    "diversity statement",
    "diversity",
    "about us",
    "about the company",
    "who we are",
    "our company",
    "our story",
    "why join",
    "culture",
    "mission",
    "values",
    "work environment",
    "how to apply",
    "application process",
    "next steps",
)


def _classify_heading(text: str) -> Literal["include", "exclude", "unknown"]:
    """Classify a heading by substring match against the include/exclude lists.

    INCLUDE is checked first — a heading that contains tokens from both
    lists (rare, e.g. "About You and About Us") gets INCLUDE."""
    lc = text.lower()
    for phrase in _INCLUDE_PHRASES:
        if phrase in lc:
            return "include"
    for phrase in _EXCLUDE_PHRASES:
        if phrase in lc:
            return "exclude"
    return "unknown"


# Below this many characters, a preamble alone is too thin to stand alone
# as the extraction — we fall back to the full JD instead. Tuned to cover
# the common 1–2 paragraph "About the role" intros without admitting
# one-liners.
_PREAMBLE_MIN_CHARS_FOR_FILTERED = 200

def _apply_budget(text: str, max_chars: int | None) -> tuple[str, bool]:
    """Clamp `text` to `max_chars`, returning `(text, truncated)`.

    `None` means no budget: the text passes through untouched."""
    if max_chars is None or len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


def _split_into_sections(lines: list[str]) -> list[tuple[str | None, list[str]]]:
    """Walk lines, splitting into (heading_line, body_lines) tuples.
    The preamble (text before the first heading) lives in a sentinel
    section with heading_line=None."""
    sections: list[tuple[str | None, list[str]]] = [(None, [])]
    for line in lines:
        if _is_heading(line):
            sections.append((line, []))
        else:
            sections[-1][1].append(line)
    return sections


def _collect_include_sections(
    sections: list[tuple[str | None, list[str]]],
) -> tuple[list[str], bool, tuple[str, ...]]:
    """Build the filtered body parts (one entry per kept section), flag
    whether any INCLUDE section was found, and report the headings of
    sections dropped (EXCLUDE/UNKNOWN with a non-empty body)."""
    kept_parts: list[str] = []
    excluded: list[str] = []
    found_include = False
    for heading_line, body_lines in sections:
        if heading_line is None:
            continue  # preamble handled by the caller
        heading_text = _heading_text(heading_line)
        kind = _classify_heading(heading_text)
        if kind != "include":
            if "\n".join(body_lines).strip():
                excluded.append(heading_text)
            continue
        found_include = True
        body_text = "\n".join(body_lines).rstrip()
        kept_parts.append(f"{heading_line.strip()}\n{body_text}".rstrip())
    return kept_parts, found_include, tuple(excluded)


def _full_fallback(raw_jd: str, max_chars: int | None) -> ExtractionResult:
    text, truncated = _apply_budget(raw_jd, max_chars)
    return ExtractionResult(
        text=text,
        mode="full_fallback",
        extracted_chars=len(text),
        original_chars=len(raw_jd),
        truncated=truncated,
    )


# Lines that are pure site chrome, never JD content. Matched case-insensitively
# as substrings against a stripped line.
_BOILERPLATE_MARKERS = (
    "join our community",
    "loading…",
    "loading...",
)


def strip_jd_boilerplate(text: str) -> str:
    """Drop scraper nav/boilerplate lines and collapse consecutive duplicates.

    Pure and idempotent. Conservative: only removes lines matching known
    chrome markers or exact repeats of the immediately preceding kept line."""
    out: list[str] = []
    prev = None
    for line in (text or "").splitlines():
        stripped = line.strip()
        low = stripped.lower()
        if any(marker in low for marker in _BOILERPLATE_MARKERS):
            continue
        if stripped and stripped == prev:
            continue
        out.append(line)
        if stripped:
            prev = stripped
    return "\n".join(out)


def extract_relevant_sections(
    raw_jd: str, *, max_chars: int | None = None
) -> ExtractionResult:
    """Return either the filtered R&R-only text or a full-body fallback.

    `max_chars` is an optional hard ceiling on the returned text, applied
    on both paths; the default is no truncation. See the module docstring
    for the extraction rules. This function is pure: no I/O, no logging,
    deterministic on input.
    """
    if not raw_jd or not raw_jd.strip():
        return _full_fallback(raw_jd, max_chars)

    sections = _split_into_sections(raw_jd.splitlines())
    preamble_text = "\n".join(sections[0][1]).strip()

    section_parts, found_include, excluded = _collect_include_sections(sections)
    kept_parts = ([preamble_text] if preamble_text else []) + section_parts

    if not found_include and len(preamble_text) < _PREAMBLE_MIN_CHARS_FOR_FILTERED:
        return _full_fallback(raw_jd, max_chars)

    text = "\n\n".join(kept_parts).strip()
    text, truncated = _apply_budget(text, max_chars)
    return ExtractionResult(
        text=text,
        mode="filtered",
        extracted_chars=len(text),
        original_chars=len(raw_jd),
        excluded_headings=excluded,
        truncated=truncated,
    )
