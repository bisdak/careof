# careof

[![CI](https://github.com/bisdak/careof/actions/workflows/ci.yml/badge.svg)](https://github.com/bisdak/careof/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/careof.svg)](https://pypi.org/project/careof/)

**Find and parse postal addresses in HTML, Markdown, and plain text.**

`careof` turns a document into a ranked list of addresses with components, confidence, and provenance. It is built for contact pages, footers, business listings, and pages where the address is buried in prose.

Named after the postal convention: care of.

```python
import careof

for address in careof.extract(html, "text/html", country="ph"):
    print(address.raw)
    print(address.components)
```

```console
$ careof examples/contact.html --country ph --language en
[
  {
    "raw": "123 Mabini Street, Makati City, Metro Manila 1223, PH",
    "components": {
      "house_number": "123",
      "road": "Mabini Street",
      "city": "Makati City",
      "state": "Metro Manila",
      "postcode": "1223",
      "country": "PH"
    },
    "confidence": 0.99,
    "key": "123 mabini street makati city metro manila 1223 ph",
    "sources": [{ "kind": "json-ld", "score": 0.99 }]
  }
]
```

(The populated `components` come from libpostal; without it the same address is returned with `"components": {}`.)

## Status

Alpha. The pipeline, adapters, structured-data path, deduplication, and CLI are implemented and tested. GLiNER and libpostal are optional: without them you still get structured matches and regex-backed extraction, just with empty component dicts.

## Install

```console
pip install careof
```

Optional model:

```console
pip install "careof[model]"    # gliner + torch
```

Optional parser:

```console
pip install "careof[postal]"   # ctypes bindings...
```

...and the system library it binds to, which pip cannot install:

```console
git clone https://github.com/openvenues/libpostal
cd libpostal
./bootstrap.sh
./configure --datadir=/usr/local/share/libpostal
make -j"$(nproc)"
sudo make install
sudo ldconfig
```

Without libpostal, `careof` still returns `raw` addresses and works as an extractor; it just cannot split them into components. This is checked at import time, not at call time.

### Python version

Core supports Python 3.10–3.13. `pyre2-updated` currently provides wheels through Python 3.13; Python 3.14 is not supported yet. For the model extra, prefer 3.12 or 3.13. `careof` does **not** depend on spaCy.

## Usage

### Python

```python
import careof

addresses = careof.extract(
    source,                 # str or bytes
    content_type=None,      # detected from the source, URL, or suffix
    url=None,
    language="en",
    country="ph",
    threshold=0.4,          # GLiNER span threshold
    extractor="auto",       # "auto" | "gliner" | "heuristic" | None
    parser=None,            # defaults to libpostal, or NullParser()
    structured=True,        # use JSON-LD, microdata, <address>, og:*, maps links
)
```

`extractor=None` returns only structured matches. That is the cheapest mode and a good default for crawling at scale.

```python
from careof.parse import NullParser

addresses = careof.extract(html, "text/html", parser=NullParser())
```

### CLI

```console
careof page.html
careof contact.md --country ph
cat page.html | careof - --content-type text/html
careof page.html --extractor heuristic --ndjson
```

`--extractor none` keeps only structured matches. JSON is pretty-printed by default; `--ndjson` emits one object per line.

## Output

`Address.to_dict()` returns:

| Field | Meaning |
|---|---|
| `raw` | The address string as found, whitespace-normalised |
| `components` | libpostal-style labels (`house_number`, `road`, `unit`, `city`, `state`, `postcode`, `country`, ...) |
| `confidence` | Heuristic 0–0.99 score; structured sources rank highest |
| `key` | Normalised dedupe key (libpostal expansion when available) |
| `sources` | Every place the address was seen: kind, document offsets, block index, model score |

HTML offsets refer to `careof`'s normalised text, not the original HTML byte stream. Markdown masking preserves offsets exactly, so those line up with the source file.

## How it works

1. **Adapters** — `lxml` parses HTML; a block-aware serializer puts newlines at block boundaries so `<br>` and `<div>` do not glue street and city together. Markdown and plain text are split into paragraphs. Code fences and inline code are masked with spaces, preserving offsets.
2. **Structured signals** — JSON-LD `PostalAddress`, microdata, `<address>`, `og:street-address` & friends, and Google/Apple Maps links are collected first. These are cheap and more reliable than any model.
3. **Candidates** — `re2` finds house-number + street-suffix patterns, PO boxes, barangay/sitio markers, and landmark phrases, then keeps a few hundred characters of context. Same regexes score whole blocks for contact-page signals.
4. **Extraction** — GLiNER runs only on those windows, chunked with overlap. The no-model fallback uses the same patterns to return line-level spans.
5. **Parsing** — libpostal parses each candidate and `expand_address` supplies the dedupe key.
6. **Merge** — exact keys, then conservative token-subset matching; components and provenance are combined and results are ranked.

`auto` uses GLiNER when the model extra is installed. The first call downloads the checkpoint (about 500 MB); pass `extractor="heuristic"` or `extractor=None` if you do not want that.

## Design notes

- **`lxml`, not BeautifulSoup.** Real parsing, real error recovery, and no extra layer between the document and the offsets.
- **`pyre2-updated` (`re2`), not `re`.** Untrusted pages cannot cause catastrophic backtracking. Fallback to Python's `re` engine is disabled. The trade-off is no backreferences or lookaround, which the patterns avoid.
- **GLiNER directly, not `gliner_spacy`.** No spaCy dependency, no stale wrapper, and spans come back as character offsets.
- **libpostal is a parser, not an extractor.** It expects an address, so it runs after candidate extraction, never on a whole page.
- **Structured data wins ties.** A JSON-LD `PostalAddress` outranks anything the model produces.

## Limitations

- No geocoding. This extracts text, it does not resolve coordinates.
- libpostal's coverage and component quality vary by country. Pass `country` and `language` hints when you know them.
- Duplicate detection is text-based. Two genuinely different addresses can share a key, and two spellings of the same address can stay separate when libpostal is absent.
- The HTML serializer normalises text; use `sources` for the derived offsets, not as byte offsets into the original response.

## Releasing

The version lives in one place: `src/careof/_version.py`.

```console
# 1. Update _version.py and CHANGELOG.md, then:
python -m build
twine check dist/*

# 2. Tag the release; CI publishes to PyPI via Trusted Publishing.
git tag v0.1.0
git push origin v0.1.0
```

One-time setup on PyPI: add a trusted publisher at
`https://pypi.org/manage/account/publishing/` with:

- project: `careof`
- owner/repository: your GitHub account and repo
- workflow: `publish.yml`
- environment: `pypi`

No API token is stored in GitHub. To rehearse first, upload manually to
TestPyPI:

```console
python -m twine upload --repository testpypi dist/*
```

## Development

```console
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
.venv/bin/ruff check src tests
```

## License

MIT
