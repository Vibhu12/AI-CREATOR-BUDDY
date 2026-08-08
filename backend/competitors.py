"""Competitors (curated top-1% creators benchmarking).

Curated archetypal personas — not real handles, so no IP/legal exposure. Each
captures the kind of profile a creator in Maya's niche compares themselves to.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

# Maya's normalized stats (composite across her assets)
MAYA = {
    "name": "You (Maya)",
    "niche": "Build-in-public + creator economy",
    "subscribers": 184_500,
    "avg_views": 142_000,
    "monthly_uploads": 5,
    "revenue_mtd": 56_660,
    "engagement_rate": 6.4,
    "consistency": 78,
    "content_quality": 88,
    "monetization": 82,
    "brand_strength": 79,
}

COMPETITORS = [
    {
        "id": "c1",
        "name": "The Velocity Founder",
        "niche": "SaaS build-in-public",
        "tier": "top_1",
        "subscribers": 1_240_000,
        "avg_views": 612_000,
        "monthly_uploads": 8,
        "revenue_mtd": 412_000,
        "engagement_rate": 7.8,
        "consistency": 96,
        "content_quality": 94,
        "monetization": 95,
        "brand_strength": 92,
    },
    {
        "id": "c2",
        "name": "Indie Operator",
        "niche": "Solopreneur education",
        "tier": "top_1",
        "subscribers": 920_000,
        "avg_views": 318_000,
        "monthly_uploads": 6,
        "revenue_mtd": 218_000,
        "engagement_rate": 9.1,
        "consistency": 92,
        "content_quality": 91,
        "monetization": 88,
        "brand_strength": 89,
    },
    {
        "id": "c3",
        "name": "Cohort Capital",
        "niche": "Course operator",
        "tier": "top_10",
        "subscribers": 480_000,
        "avg_views": 184_000,
        "monthly_uploads": 4,
        "revenue_mtd": 184_000,
        "engagement_rate": 5.9,
        "consistency": 84,
        "content_quality": 86,
        "monetization": 93,
        "brand_strength": 78,
    },
]

INDUSTRY_AVG = {
    "subscribers": 92_400,
    "avg_views": 38_200,
    "monthly_uploads": 3.2,
    "revenue_mtd": 18_400,
    "engagement_rate": 4.1,
    "consistency": 62,
    "content_quality": 71,
    "monetization": 58,
    "brand_strength": 64,
}

TOP_1_PCT = COMPETITORS[0]  # synthetic top-1%
TOP_10_PCT = COMPETITORS[2]  # synthetic top-10%

DIMENSIONS = [
    ("subscribers", "Audience"),
    ("avg_views", "Reach"),
    ("monthly_uploads", "Cadence"),
    ("revenue_mtd", "Revenue"),
    ("engagement_rate", "Engagement"),
    ("consistency", "Consistency"),
    ("content_quality", "Content"),
    ("monetization", "Monetization"),
    ("brand_strength", "Brand"),
]


def _norm(value: float, max_value: float) -> float:
    if max_value <= 0:
        return 0
    return round(min(100, (value / max_value) * 100), 1)


def make_competitors_router(current_user=None):
    router = APIRouter(prefix="/competitors", tags=["competitors"])
    # SEC hardening: gate all competitor endpoints behind auth.
    auth_dep = [Depends(current_user)] if current_user else []

    @router.get("", dependencies=auth_dep)
    async def list_competitors() -> dict[str, Any]:
        return {
            "you": MAYA,
            "industry_avg": INDUSTRY_AVG,
            "top_10": TOP_10_PCT,
            "top_1": TOP_1_PCT,
            "competitors": COMPETITORS,
        }

    @router.get("/radar", dependencies=auth_dep)
    async def radar() -> dict[str, Any]:
        """Normalized 0-100 radar values across 6 qualitative dimensions."""
        keys = ["consistency", "content_quality", "monetization", "brand_strength", "engagement_rate"]
        labels = {"engagement_rate": "Engagement"}
        # Engagement rate maxes around 12% — normalize separately
        def norm_dim(value: float, key: str) -> float:
            if key == "engagement_rate":
                return round(min(100, (value / 12.0) * 100), 1)
            return value
        rows = []
        for key in keys:
            rows.append({
                "key": key,
                "label": labels.get(key, key.replace("_", " ").title()),
                "you": norm_dim(MAYA[key], key),
                "top_1": norm_dim(TOP_1_PCT[key], key),
                "industry_avg": norm_dim(INDUSTRY_AVG[key], key),
            })
        return {"dimensions": rows}

    @router.get("/gaps", dependencies=auth_dep)
    async def gaps() -> dict[str, Any]:
        """Where Maya trails the top-1% — biggest opportunity gaps first."""
        out = []
        for key, label in DIMENSIONS:
            you_val = MAYA[key]
            top_val = TOP_1_PCT[key]
            if top_val <= 0:
                continue
            gap_pct = round(((top_val - you_val) / top_val) * 100, 1)
            out.append({
                "key": key,
                "label": label,
                "you": you_val,
                "top_1": top_val,
                "industry_avg": INDUSTRY_AVG.get(key, 0),
                "gap_pct": gap_pct,
            })
        out.sort(key=lambda r: r["gap_pct"], reverse=True)
        return {"items": out}

    return router
