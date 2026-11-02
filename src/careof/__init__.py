"""careof — find and parse postal addresses in text."""

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
