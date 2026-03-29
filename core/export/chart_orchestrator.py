"""
Chart orchestration for PDF export.

Coordinates generation of all chart images (muscle heatmap, volume chart,
push/pull pie, body map) used in the training PDF report.
"""

import logging

from core.chart_generator import (
    generate_body_map_with_data,
    generate_muscle_heatmap,
    generate_push_pull_pie,
    generate_volume_chart,
)

logger = logging.getLogger(__name__)


def generate_pdf_charts(
    muskelgruppen_stats: list[dict], volumen_wochen: list[dict], push_saetze: int, pull_saetze: int
) -> tuple:
    """Generate chart images for PDF; returns (muscle_heatmap, volume_chart, push_pull_chart, body_map).
    Returns (None, None, None, None) if generation fails."""
    try:
        muscle_heatmap = generate_muscle_heatmap(muskelgruppen_stats)
        volume_chart = generate_volume_chart(volumen_wochen[-8:])
        push_pull_chart = generate_push_pull_pie(push_saetze, pull_saetze)
        body_map_image = generate_body_map_with_data(muskelgruppen_stats)
        logger.info("Charts successfully generated")
        return muscle_heatmap, volume_chart, push_pull_chart, body_map_image
    except Exception as e:
        logger.warning(f"Chart generation failed: {str(e)}")
        return None, None, None, None
