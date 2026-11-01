"""Shared pytest fixtures and helpers."""

from __future__ import annotations

import pytest
from pptx import Presentation


@pytest.fixture
def blank_layout():
    prs = Presentation()
    return prs.slide_layouts[6]


@pytest.fixture
def presentation():
    return Presentation()


def add_slide(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])
