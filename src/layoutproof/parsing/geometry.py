"""Geometry primitives and unit conversions for the OOXML slide coordinate system."""

from __future__ import annotations

from dataclasses import dataclass

EMU_PER_INCH = 914400
EMU_PER_POINT = 12700
EMU_PER_CM = 360000
EMU_PER_PIXEL_96DPI = 9525


def emu_to_pt(emu: float) -> float:
    return emu / EMU_PER_POINT


def pt_to_emu(pt: float) -> int:
    return round(pt * EMU_PER_POINT)


def emu_to_inch(emu: float) -> float:
    return emu / EMU_PER_INCH


def emu_to_cm(emu: float) -> float:
    return emu / EMU_PER_CM


@dataclass(frozen=True)
class Rect:
    """Axis-aligned rectangle in EMU."""

    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    @property
    def area(self) -> int:
        return max(0, self.width) * max(0, self.height)

    def intersection(self, other: Rect) -> Rect | None:
        x1 = max(self.x, other.x)
        y1 = max(self.y, other.y)
        x2 = min(self.right, other.right)
        y2 = min(self.bottom, other.bottom)
        if x2 <= x1 or y2 <= y1:
            return None
        return Rect(x1, y1, x2 - x1, y2 - y1)

    def intersects(self, other: Rect) -> bool:
        return self.intersection(other) is not None

    def overlap_ratio(self, other: Rect) -> float:
        """Fraction of the smaller rectangle covered by the intersection."""
        inter = self.intersection(other)
        if inter is None:
            return 0.0
        smaller = min(self.area, other.area)
        if smaller <= 0:
            return 0.0
        return inter.area / smaller

    def contains(self, other: Rect) -> bool:
        return (
            other.x >= self.x
            and other.y >= self.y
            and other.right <= self.right
            and other.bottom <= self.bottom
        )

    def fraction_outside(self, bounds: Rect) -> float:
        """Fraction of this rectangle's area lying outside the slide bounds."""
        if self.area <= 0:
            return 0.0
        inside = self.intersection(bounds)
        inside_area = inside.area if inside else 0
        return max(0.0, 1.0 - inside_area / self.area)

    def is_fully_outside(self, bounds: Rect) -> bool:
        return self.intersection(bounds) is None

    def clamp(self, bounds: Rect) -> Rect:
        x = min(max(self.x, bounds.x), max(bounds.x, bounds.right - self.width))
        y = min(max(self.y, bounds.y), max(bounds.y, bounds.bottom - self.height))
        return Rect(x, y, self.width, self.height)
