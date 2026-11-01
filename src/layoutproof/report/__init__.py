"""HTML and JSON report rendering for LayoutProof."""

from .html import render_html
from .json_out import validate_output, write_json

__all__ = ["render_html", "write_json", "validate_output"]
