# Changelog

All notable changes to `careof` are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
- Deduplication, confidence scoring, provenance, and ranked output.
- `careof` CLI and `python -m careof` entry points.
- Philippine landmark and barangay signals.
