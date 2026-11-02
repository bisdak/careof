"""careof — find and parse postal addresses in text."""

import re2 as _re2

# pyre2-updated can fall back to Python's backtracking ``re`` engine for
# unsupported syntax. Keep patterns strictly on RE2, which is important when
# processing untrusted HTML.
if hasattr(_re2, "set_fallback_notification"):
    _re2.set_fallback_notification(_re2.FALLBACK_EXCEPTION)

from ._version import __version__
from .pipeline import extract, extract_file
from .schema import Address, Block, Candidate, Span, StructuredAddress

__all__ = [
    "Address",
    "Block",
    "Candidate",
    "Span",
    "StructuredAddress",
    "__version__",
    "extract",
    "extract_file",
]
