"""LayoutProof — local-first automated quality assurance for AI-generated PPTX."""

from .config import QualityConfig
from .engine import scan_file
from .models import (
    SCHEMA_VERSION,
    TOOL_VERSION,
    Issue,
    ScanResult,
    Severity,
)

__version__ = TOOL_VERSION

__all__ = [
    "QualityConfig",
    "scan_file",
    "SCHEMA_VERSION",
    "TOOL_VERSION",
    "Issue",
    "ScanResult",
    "Severity",
    "__version__",
]
