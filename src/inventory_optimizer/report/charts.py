"""Inline SVG charts."""

from __future__ import annotations

from html import escape

PALETTE = {"A": "#2563eb", "B": "#f59e0b", "C": "#94a3b8"}


def bar_chart(
    labels: list[str], values: list[float], title: str, colors: list[str] | None = None, unit: str = ""
) -> str:
    """Draw a horizontal bar chart as an SVG string.

    Args:
        labels: Bar labels.
        values: Non-negative bar values.
        title: Chart title.
        colors: Optional bar colours (defaults to one blue).
        unit: Suffix printed after each value, such as ``%``.

    Returns:
        An ``<svg>`` element with no external references.
    """
    width, row, left, right = 560, 26, 120, 90
    height = 40 + row * max(len(labels), 1)
    top = max(values, default=0.0) or 1.0
    shapes = [f'<text x="0" y="20" font-size="14" font-weight="600" fill="#0f172a">{escape(title)}</text>']
    for i, (label, value) in enumerate(zip(labels, values, strict=True)):
        y = 36 + i * row
        bar = (width - left - right) * value / top
        color = colors[i] if colors else "#2563eb"
        shapes.append(f'<text x="0" y="{y + 13}" font-size="12" fill="#334155">{escape(label)}</text>')
        shapes.append(f'<rect x="{left}" y="{y}" width="{bar:.1f}" height="16" rx="3" fill="{color}"/>')
        shapes.append(f'<text x="{left + bar + 6:.1f}" y="{y + 13}" font-size="12" fill="#334155">{value:,.1f}{escape(unit)}</text>')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="100%" role="img" aria-label="{escape(title)}">' + "".join(shapes) + "</svg>"
    )
