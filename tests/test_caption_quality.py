"""Tests for caption quality assessment."""

from __future__ import annotations

from imagecb.caption.quality import assess_caption
from imagecb.models.vlm import (
    CaptionJSON,
    GroundedCaption,
    InterpretiveCaption,
    SearchTerms,
)


def _caption(**kwargs) -> CaptionJSON:
    grounded = kwargs.pop("grounded", GroundedCaption())
    interpretive = kwargs.pop("interpretive", InterpretiveCaption())
    search = kwargs.pop("search", SearchTerms())
    return CaptionJSON(
        image_name=kwargs.get("image_name", "Q3 Sales Chart"),
        grounded=grounded,
        interpretive=interpretive,
        search=search,
    )


def test_assess_ok_caption():
    cap = _caption(
        interpretive=InterpretiveCaption(
            short_caption="Bar chart comparing quarterly revenue across regions",
            detailed_description="A colorful bar chart with four quarters labeled.",
        ),
        grounded=GroundedCaption(
            objects=["bar chart"],
            scene="business presentation slide",
        ),
        search=SearchTerms(
            tags=["revenue", "chart", "sales"],
            recommended_cases=[
                "quarterly revenue chart",
                "regional sales comparison",
                "bar chart revenue by region",
            ],
            aliases=["sales", "revenue growth", "q3 revenue"],
        ),
    )
    assert assess_caption(cap) == "ok"


def test_assess_failed_caption():
    cap = _caption(
        interpretive=InterpretiveCaption(
            short_caption="[caption failed]",
            detailed_description="VLM error: timeout",
        ),
    )
    assert assess_caption(cap) == "failed"


def test_assess_weak_short_caption():
    cap = _caption(
        interpretive=InterpretiveCaption(short_caption="A photo"),
        grounded=GroundedCaption(),
    )
    assert assess_caption(cap) == "weak"


def test_assess_weak_generic_pattern():
    cap = _caption(
        interpretive=InterpretiveCaption(
            short_caption="An image showing a business scene with people",
            detailed_description="People in an office setting during a meeting.",
        ),
        grounded=GroundedCaption(objects=["people"], scene="office"),
    )
    assert assess_caption(cap) == "weak"


def test_assess_weak_thin_search_fields():
    cap = _caption(
        interpretive=InterpretiveCaption(
            short_caption="Bar chart comparing quarterly revenue across regions",
            detailed_description="A colorful bar chart with four quarters labeled.",
        ),
        grounded=GroundedCaption(objects=["bar chart"], scene="business slide"),
        search=SearchTerms(tags=["revenue"], recommended_cases=["revenue chart"], aliases=[]),
    )
    assert assess_caption(cap) == "weak"
