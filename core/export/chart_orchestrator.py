"""
Chart orchestration for PDF export.

Coordinates generation of all chart images (muscle heatmap, volume chart,
push/pull pie, body map) used in the training PDF report.
Includes caching with 1h TTL to avoid regenerating unchanged charts.
"""

import hashlib
import json
import logging

from django.core.cache import cache

from core.chart_generator import (
    generate_body_map_with_data,
    generate_muscle_heatmap,
    generate_push_pull_pie,
    generate_volume_chart,
)

logger = logging.getLogger(__name__)

CHART_CACHE_TTL = 3600  # 1 hour


def _data_hash(*args) -> str:
    """Create a stable hash from JSON-serializable data for cache keys."""
    raw = json.dumps(args, sort_keys=True, default=str)
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def _get_or_generate(cache_key: str, generator_fn, *args):
    """Return cached result or generate, cache and return it."""
    cached = cache.get(cache_key)
    if cached is not None:
        logger.debug("Chart cache hit: %s", cache_key)
        return cached
    result = generator_fn(*args)
    cache.set(cache_key, result, CHART_CACHE_TTL)
    return result


def generate_pdf_charts(
    muskelgruppen_stats: list[dict], volumen_wochen: list[dict], push_saetze: int, pull_saetze: int
) -> tuple:
    """Generate chart images for PDF; returns (muscle_heatmap, volume_chart, push_pull_chart, body_map).
    Returns (None, None, None, None) if generation fails."""
    try:
        h = _data_hash(muskelgruppen_stats, volumen_wochen, push_saetze, pull_saetze)

        muscle_heatmap = _get_or_generate(
            f"pdf_chart_heatmap_{h}", generate_muscle_heatmap, muskelgruppen_stats
        )
        volume_chart = _get_or_generate(
            f"pdf_chart_volume_{h}", generate_volume_chart, volumen_wochen[-8:]
        )
        push_pull_chart = _get_or_generate(
            f"pdf_chart_pushpull_{h}", generate_push_pull_pie, push_saetze, pull_saetze
        )
        body_map_image = _get_or_generate(
            f"pdf_chart_bodymap_{h}", generate_body_map_with_data, muskelgruppen_stats
        )

        logger.info("Charts successfully generated (with caching)")
        return muscle_heatmap, volume_chart, push_pull_chart, body_map_image
    except Exception as e:
        logger.warning(f"Chart generation failed: {str(e)}")
        return None, None, None, None
