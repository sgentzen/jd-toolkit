# Changelog

## Unreleased

- Initial extraction from job-stalker: `parse_annual_usd` / `SalaryBand`,
  `extract_relevant_sections` / `ExtractionResult`, `strip_jd_boilerplate`,
  `detect_ats` / `AtsInfo`, `html_to_text`.
- `extract_relevant_sections` takes an optional `max_chars` budget; the
  default is no truncation.
