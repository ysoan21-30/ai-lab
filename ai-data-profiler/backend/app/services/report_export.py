"""Report export: JSON, CSV (issues), and PDF."""
from __future__ import annotations

import csv
import io
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)


def export_issues_csv(analysis: dict[str, Any]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["type", "column", "severity", "detail", "recommendation"])
    for issue in (analysis.get("quality_result") or {}).get("issues", []):
        writer.writerow([
            issue.get("type"), issue.get("column") or "", issue.get("severity"),
            issue.get("detail"), issue.get("recommendation", ""),
        ])
    return buffer.getvalue().encode("utf-8")


def export_report_pdf(analysis: dict[str, Any]) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(f"AI Data Profiler Report", styles["Title"]))
    story.append(Paragraph(f"Dataset: {analysis.get('dataset_name', 'Untitled')}", styles["Normal"]))
    story.append(Spacer(1, 12))

    ai = analysis.get("ai_insights") or {}
    if ai.get("executive_summary"):
        story.append(Paragraph("Executive Summary", styles["Heading2"]))
        story.append(Paragraph(ai["executive_summary"], styles["Normal"]))
        story.append(Spacer(1, 12))

    story.append(Paragraph("Scores", styles["Heading2"]))
    score_data = [
        ["Data Quality Score", f"{analysis.get('quality_score', 'N/A')} / 100"],
        ["ML Readiness Score", f"{analysis.get('ml_readiness_score', 'N/A')} / 100"],
        ["Total Issues Detected", str(analysis.get("issue_count", "N/A"))],
    ]
    story.append(_table(score_data))
    story.append(Spacer(1, 12))

    readiness = (analysis.get("ml_readiness_result") or {}).get("breakdown", {})
    if readiness:
        story.append(Paragraph("ML Readiness Breakdown", styles["Heading2"]))
        story.append(_table([[k.replace("_", " ").title(), f"{v}/100"] for k, v in readiness.items()]))
        story.append(Spacer(1, 12))

    issues = (analysis.get("quality_result") or {}).get("issues", [])[:25]
    if issues:
        story.append(Paragraph("Top Data Quality Issues", styles["Heading2"]))
        rows = [["Severity", "Column", "Detail"]]
        for i in issues:
            rows.append([i["severity"], i.get("column") or "-", Paragraph(i["detail"], styles["Normal"])])
        story.append(_table(rows, col_widths=[2.2 * cm, 3.5 * cm, 10.5 * cm]))
        story.append(Spacer(1, 12))

    if ai.get("recommended_next_steps"):
        story.append(Paragraph("Recommended Next Steps", styles["Heading2"]))
        for step in ai["recommended_next_steps"]:
            story.append(Paragraph(f"- {step}", styles["Normal"]))

    doc.build(story)
    return buffer.getvalue()


def _table(data: list[list[Any]], col_widths=None) -> Table:
    table = Table(data, colWidths=col_widths)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
    ]))
    return table
