# Changelog

## [0.1.0] - 2026-08-15

### Added

- Initial extraction from job-stalker: `parse_annual_usd` / `SalaryBand`,
  `extract_relevant_sections` / `ExtractionResult`, `strip_jd_boilerplate`,
  `detect_ats` / `AtsInfo`, `html_to_text`.
- `extract_relevant_sections` and `parse_annual_usd` accept an optional
  `max_chars` budget to cap scanning. This guards against DoS when parsing
  untrusted prose, since internal checks may scale with document length.
