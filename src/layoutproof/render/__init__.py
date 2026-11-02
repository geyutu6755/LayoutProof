"""Optional real rendering chain (PPTX -> PDF -> images) with static fallback."""

from .backend import RendererInfo, detect_renderer
from .engine import (
    RENDER_STATUS_RENDERED,
    RENDER_STATUS_STATIC,
    RenderResult,
    render_presentation,
)
from .images import SlideImage, is_available

__all__ = [
    "RendererInfo",
    "detect_renderer",
    "RenderResult",
    "render_presentation",
    "RENDER_STATUS_RENDERED",
    "RENDER_STATUS_STATIC",
    "SlideImage",
    "is_available",
]
