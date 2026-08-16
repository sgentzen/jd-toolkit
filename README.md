# jd-toolkit

Zero-dependency Python toolkit for job-description text. Three small, pure,
deterministic tools extracted from a production job-search pipeline:

- **`parse_annual_usd`** — pull an annual base-salary band (USD) out of JD
  prose, conservatively.
- **`extract_relevant_sections`** — keep the responsibilities/requirements
  core of a JD, drop benefits, EEO statements and company boilerplate. Built
  for trimming JDs before sending them to an LLM.
- **`detect_ats`** — identify the applicant tracking system behind a posting
  URL (Greenhouse, Lever, Workday, Ashby, iCIMS, SuccessFactors, …).

No runtime dependencies. No network calls. No I/O. Every function is total:
bad input returns `None` or a fallback result, never an exception.

## Install

```bash
pip install jd-toolkit
```

Requires Python 3.11+.

## Salary parsing

```python
from jd_toolkit import parse_annual_usd

band = parse_annual_usd("Illinois: base salary range $158,500 - $172,000 per year")
# SalaryBand(min_usd=158500, max_usd=172000, raw='$158,500 - $172,000')

parse_annual_usd("Project budgets of $20-$100 million")   # None
parse_annual_usd("Tuition reimbursement of $20,000 - $25,000 per year")  # None
```

A wrong number is worse than no number, so the parser is deliberately
conservative and returns `None` whenever it cannot be confident. The rules are
grounded in a live survey of 40 Workday postings: most money in a JD is *not*
salary (perks, project budgets, funding rounds), so a band must be two amounts
of plausible annual magnitude, vouched for by nearby salary wording, with an
asymmetric veto rule — only a phrase that names the base salary can out-argue
a disqualifier like "reimbursement" or "bonus", and only by sitting closer.
Multiple surviving bands (per-state pay tables) are unioned. HTML input is
fine; it is flattened first (`html_to_text` is also exported).

## Section extraction

```python
from jd_toolkit import extract_relevant_sections

result = extract_relevant_sections(raw_jd, max_chars=16_000)
result.text               # responsibilities + requirements sections only
result.mode               # "filtered", or "full_fallback" when unsure
result.excluded_headings  # what was dropped, e.g. ("Benefits", "About Us")
result.truncated          # True only if max_chars cut the text short
```

Heading detection covers Markdown ATX, bold-only lines, short colon-terminated
lines and short ALL-CAPS lines. Section headings are classified by curated
include/exclude phrase lists; when no include section is found and the preamble
is too thin, the full body is returned (`mode="full_fallback"`) rather than
guessing. `max_chars` is optional — without it nothing is ever truncated.

`strip_jd_boilerplate` is a companion cleaner that drops known scraper chrome
lines and collapses consecutive duplicate lines.

## ATS detection

```python
from jd_toolkit import detect_ats

detect_ats("https://boards.greenhouse.io/acme/jobs/12345")
# AtsInfo(slug='greenhouse', name='Greenhouse')

detect_ats("https://careers.example.com/jobs/1")
# AtsInfo(slug='unknown', name='Unknown / direct careers page')
```

Pure host-suffix matching, no network. Aggregators (LinkedIn, Indeed,
hiring.cafe, …) get their own slugs since the downstream ATS is opaque.

## License

Apache-2.0.
