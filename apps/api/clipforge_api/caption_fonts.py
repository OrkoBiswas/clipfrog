"""Shared caption font catalog and deterministic selection of real font faces."""

import json
from functools import lru_cache
from importlib.resources import files
from typing import Literal, TypedDict

CaptionWeight = Literal[100, 200, 300, 400, 500, 600, 700, 800, 900]


class CaptionFontVariant(TypedDict):
    weight: CaptionWeight
    italic: bool
    file: str
    family: str


class CaptionFontFamily(TypedDict):
    family: str
    category: str
    weights: list[int]
    italic: bool
    variants: list[CaptionFontVariant]


@lru_cache(maxsize=1)
def caption_font_catalog() -> dict[str, CaptionFontFamily]:
    catalog = json.loads(files("clipforge_api").joinpath("caption-fonts.json").read_text("utf-8"))
    return {font["family"]: font for font in catalog}


def caption_family(family: str) -> CaptionFontFamily:
    try:
        return caption_font_catalog()[family]
    except KeyError as exc:
        raise ValueError("Choose a font from the caption font library.") from exc


def caption_variant(family: str, weight: int, italic: bool) -> CaptionFontVariant:
    font = caption_family(family)
    use_italic = italic and font["italic"]
    variants = [variant for variant in font["variants"] if variant["italic"] == use_italic]
    # A tie resolves to the heavier face, identically to the browser selector.
    return min(variants, key=lambda variant: (abs(variant["weight"] - weight), -variant["weight"]))
