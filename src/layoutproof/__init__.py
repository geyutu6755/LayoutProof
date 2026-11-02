"""LayoutProof — local-first automated quality assurance for AI-generated PPTX."""

from .config import QualityConfig
from .engine import scan_file
from .fix.engine import fix_file
from .models import (
    SCHEMA_VERSION,
    TOOL_VERSION,
    FixReport,
    Issue,
    ScanResult,
    Severity,
)

__version__ = TOOL_VERSION

__all__ = [
    "SCHEMA_VERSION",
    "TOOL_VERSION",
    "FixReport",
    "Issue",
    "QualityConfig",
    "ScanResult",
    "Severity",
    "__version__",
    "fix_file",
    "scan_file",
]
