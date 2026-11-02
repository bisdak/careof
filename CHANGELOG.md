# Changelog

All notable changes to `careof` are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

- Added UK postcode and street-type recognition, plus premise/floor-line context,
  with an Ardent IFA fixture test.

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
