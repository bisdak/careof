# Changelog

All notable changes to `careof` are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] - 2026-11-02

### Added

- Added UK postcode and street-type recognition, plus premise/floor-line context,
  with an Ardent IFA fixture test.
- Added a US address fixture and prevent four-digit house numbers from being
  mistaken for complete postal codes during span expansion.
- Added the corrected Tucson business address fixture and regression test.
- Added the AutomotiveFineArt fixture and trim `<address>` contents after the
  postal line to avoid retaining unrelated notices.

### Fixed

- Stop structured `<address>` extraction at the postal line, excluding trailing notices and other non-address text.

## [0.1.0] - 2026-11-02

### Added

- HTML adapter built on lxml with block-aware text serialization.
- Markdown adapter that masks code and preserves character offsets.
- Plain-text adapter.
- Structured address extraction from JSON-LD, microdata, `<address>` tags,
  `og:*` meta tags, and Google/Apple Maps links.
- re2 candidate selection and block scoring.
- GLiNER extractor with chunking and offset translation.
- Heuristic extractor for machines without the model extra.
- Optional libpostal parsing and address expansion.
- HTTP client for libpostal REST services, including Docker-hosted deployments.
- Optional `fetch` extra and `careof-url` command for extracting from HTTP(S) pages.
- Deduplication, confidence scoring, provenance, and ranked output.
- `careof` CLI and `python -m careof` entry points.
- Country-name signals from the `pycountry` ISO catalog.
- International street/postal-code heuristics, including German and Canadian formats.
- Country-specific regression fixtures for real HTML pages.

### Changed

- Supported Python versions are 3.10–3.13, matching `pyre2-updated` wheel availability.
- Regex fallback to Python's backtracking engine is disabled.
- Address spans stop at complete postal lines and avoid absorbing nearby business hours.
