"""Parsing layer: safe package loading and presentation object model."""

from .geometry import Rect, emu_to_cm, emu_to_inch, emu_to_pt, pt_to_emu
from .package import PackageError, SafePackage
from .presentation import (
    Paragraph,
    PresentationModel,
    Relationship,
    ShapeModel,
    SlideModel,
    TextRun,
    build_model,
)

__all__ = [
    "PackageError",
    "Paragraph",
    "PresentationModel",
    "Rect",
    "Relationship",
    "SafePackage",
    "ShapeModel",
    "SlideModel",
    "TextRun",
    "build_model",
    "emu_to_cm",
    "emu_to_inch",
    "emu_to_pt",
    "pt_to_emu",
]
