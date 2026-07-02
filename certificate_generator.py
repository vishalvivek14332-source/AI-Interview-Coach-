"""
certificate_generator.py — AI Interview Coach
================================================
Generates a professional, landscape-orientation Interview Completion
Certificate as a single-page PDF using ReportLab's low-level canvas API
(more control over precise positioning than platypus flowables, which
suits a fixed decorative layout like a certificate).

Public API
----------
  generate_certificate(candidate_name, job_role, overall_score,
                       completed_at, output_path=None) -> bytes
      Build the certificate PDF and either write it to *output_path*
      and/or return the raw bytes.

  generate_certificate_for_interview(interview_id, output_path=None) -> bytes
      Convenience wrapper that fetches the Interview from the DB and
      calls generate_certificate().  Must be called inside a Flask
      application context.
"""

from __future__ import annotations

import io
import os
from datetime import datetime
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm, mm
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.pdfbase.pdfmetrics import stringWidth

# ---------------------------------------------------------------------------
# Page geometry
# ---------------------------------------------------------------------------
PAGE_SIZE = landscape(A4)
PAGE_W, PAGE_H = PAGE_SIZE   # approx 841.9 x 595.3 pt

# ---------------------------------------------------------------------------
# Palette — mirrors the web app's dark/indigo/cyan theme
# ---------------------------------------------------------------------------
BG_DARK     = colors.HexColor('#0d1b3e')
BG_DARK_2   = colors.HexColor('#1a0d3e')
BG_DARK_3   = colors.HexColor('#0d2e1b')
INDIGO      = colors.HexColor('#6366f1')
CYAN        = colors.HexColor('#06b6d4')
EMERALD     = colors.HexColor('#10b981')
AMBER       = colors.HexColor('#f59e0b')
GOLD        = colors.HexColor('#fbbf24')
WHITE       = colors.white
OFF_WHITE   = colors.HexColor('#e2e8f0')
MUTED       = colors.HexColor('#94a3b8')
MUTED_DARK  = colors.HexColor('#64748b')


# ---------------------------------------------------------------------------
# Score helpers
# ---------------------------------------------------------------------------

def _score_color(score: float) -> colors.Color:
    if score >= 8:
        return EMERALD
    if score >= 6:
        return AMBER
    if score >= 4:
        return colors.HexColor('#f97316')
    return colors.HexColor('#ef4444')


def _performance_label(score: float) -> str:
    if score >= 9:
        return 'Outstanding Performance'
    if score >= 7.5:
        return 'Excellent Performance'
    if score >= 6:
        return 'Good Performance'
    if score >= 4.5:
        return 'Satisfactory Performance'
    return 'Completion Acknowledged'


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def _draw_centered(c: pdfcanvas.Canvas, text: str, y: float,
                   font: str, size: float, color: colors.Color,
                   tracking: float = 0.0) -> None:
    """
    Draw text horizontally centred on the page at height *y*.
    If *tracking* > 0, manually space out characters for a
    letter-spaced "eyebrow" style heading.
    """
    c.setFont(font, size)
    c.setFillColor(color)

    if tracking <= 0:
        c.drawCentredString(PAGE_W / 2, y, text)
        return

    char_widths = [stringWidth(ch, font, size) for ch in text]
    total_w = sum(char_widths) + tracking * (len(text) - 1)
    x = (PAGE_W - total_w) / 2

    for ch, w in zip(text, char_widths):
        c.drawString(x, y, ch)
        x += w + tracking


def _wrap_text(text: str, font: str, size: float, max_width: float) -> list:
    """Greedy word-wrap; returns a list of lines that each fit max_width."""
    words = text.split()
    lines, current = [], ''
    for word in words:
        candidate = (current + ' ' + word).strip()
        if stringWidth(candidate, font, size) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


# ---------------------------------------------------------------------------
# Colour helper
# ---------------------------------------------------------------------------

def _lerp_color(c1: colors.Color, c2: colors.Color, t: float) -> colors.Color:
    """Linearly interpolate between two ReportLab colours."""
    r = c1.red   + (c2.red   - c1.red)   * t
    g = c1.green + (c2.green - c1.green) * t
    b = c1.blue  + (c2.blue  - c1.blue)  * t
    return colors.Color(r, g, b)


# ---------------------------------------------------------------------------
# Decorative elements
# ---------------------------------------------------------------------------

def _draw_background(c: pdfcanvas.Canvas) -> None:
    """Diagonal three-tone gradient approximation (indigo -> violet -> emerald)."""
    c.setFillColor(BG_DARK)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    band_h = PAGE_H / 24
    for i in range(24):
        t = i / 23.0
        if t < 0.5:
            ratio = t / 0.5
            col = _lerp_color(BG_DARK, BG_DARK_2, ratio)
        else:
            ratio = (t - 0.5) / 0.5
            col = _lerp_color(BG_DARK_2, BG_DARK_3, ratio)
        c.setFillColor(col)
        c.setFillAlpha(0.55)
        c.rect(0, i * band_h, PAGE_W, band_h + 1, fill=1, stroke=0)
    c.setFillAlpha(1)


def _draw_gradient_rect_border(c: pdfcanvas.Canvas, x: float, y: float,
                                w: float, h: float, width: float = 2.0) -> None:
    """Draw a rectangle border whose colour sweeps indigo -> cyan -> emerald."""
    segments = 60

    top    = [(x + w * i / segments, y + h) for i in range(segments + 1)]
    right  = [(x + w, y + h - h * i / segments) for i in range(segments + 1)]
    bottom = [(x + w - w * i / segments, y) for i in range(segments + 1)]
    left   = [(x, y + h * i / segments) for i in range(segments + 1)]
    perimeter_points = top + right + bottom + left
    n = len(perimeter_points)

    c.setLineWidth(width)
    for i in range(n - 1):
        t = i / (n - 1)
        if t < 0.5:
            col = _lerp_color(INDIGO, CYAN, t / 0.5)
        else:
            col = _lerp_color(CYAN, EMERALD, (t - 0.5) / 0.5)
        c.setStrokeColor(col)
        x1, y1 = perimeter_points[i]
        x2, y2 = perimeter_points[i + 1]
        c.line(x1, y1, x2, y2)


def _draw_decorative_border(c: pdfcanvas.Canvas) -> None:
    """Double-line ornate border with corner flourishes, gradient-style."""
    margin_outer = 0.9 * cm
    margin_inner = 1.15 * cm

    _draw_gradient_rect_border(
        c, margin_outer, margin_outer,
        PAGE_W - 2 * margin_outer, PAGE_H - 2 * margin_outer,
        width=2.2,
    )

    c.setStrokeColor(colors.Color(1, 1, 1, alpha=0.25))
    c.setLineWidth(0.6)
    c.rect(margin_inner, margin_inner,
           PAGE_W - 2 * margin_inner, PAGE_H - 2 * margin_inner,
           fill=0, stroke=1)

    flourish_len = 0.6 * cm
    corners = [
        (margin_inner, margin_inner, 1, 1),
        (PAGE_W - margin_inner, margin_inner, -1, 1),
        (margin_inner, PAGE_H - margin_inner, 1, -1),
        (PAGE_W - margin_inner, PAGE_H - margin_inner, -1, -1),
    ]
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.4)
    for cx0, cy0, dx, dy in corners:
        c.line(cx0, cy0, cx0 + dx * flourish_len, cy0)
        c.line(cx0, cy0, cx0, cy0 + dy * flourish_len)


def _draw_watermark_seal(c: pdfcanvas.Canvas, cx: float, cy: float,
                         radius: float = 2.6 * cm) -> None:
    """Large, faint translucent seal/badge behind the main content."""
    c.saveState()
    c.setFillColor(colors.Color(1, 1, 1, alpha=0.035))
    c.circle(cx, cy, radius, fill=1, stroke=0)
    c.setFont('Helvetica-Bold', radius * 1.1)
    c.setFillColor(colors.Color(1, 1, 1, alpha=0.04))
    c.drawCentredString(cx, cy - radius * 0.35, 'AIC')
    c.restoreState()


def _draw_seal_badge(c: pdfcanvas.Canvas, cx: float, cy: float,
                     radius: float = 1.15 * cm) -> None:
    """Small solid circular seal with a glyph, bottom-right of cert."""
    c.saveState()
    c.setFillColor(colors.Color(INDIGO.red, INDIGO.green, INDIGO.blue, alpha=0.25))
    c.circle(cx, cy, radius * 1.35, fill=1, stroke=0)

    c.setFillColor(INDIGO)
    c.circle(cx, cy, radius, fill=1, stroke=0)
    c.setFillColor(colors.Color(CYAN.red, CYAN.green, CYAN.blue, alpha=0.55))
    c.circle(cx + radius * 0.18, cy - radius * 0.12, radius * 0.85, fill=1, stroke=0)

    c.setStrokeColor(WHITE)
    c.setLineWidth(1.2)
    c.circle(cx, cy, radius, fill=0, stroke=1)

    c.setFont('Helvetica-Bold', radius * 0.78)
    c.setFillColor(WHITE)
    c.drawCentredString(cx, cy - radius * 0.30, 'AI')
    c.restoreState()


def _draw_ribbon(c: pdfcanvas.Canvas, score: float) -> None:
    """Small ribbon badge in the top-right showing the overall score."""
    rw, rh = 3.6 * cm, 1.0 * cm
    rx = PAGE_W - 2.6 * cm - rw
    ry = PAGE_H - 2.3 * cm - rh
    color = _score_color(score)

    c.saveState()
    c.setFillColor(colors.Color(color.red, color.green, color.blue, alpha=0.16))
    c.roundRect(rx, ry, rw, rh, 6, fill=1, stroke=0)
    c.setStrokeColor(color)
    c.setLineWidth(0.8)
    c.roundRect(rx, ry, rw, rh, 6, fill=0, stroke=1)

    c.setFont('Helvetica-Bold', 14)
    c.setFillColor(color)
    c.drawCentredString(rx + rw / 2, ry + rh / 2 - 2, '%.1f / 10' % score)
    c.restoreState()


# ---------------------------------------------------------------------------
# Main certificate drawing
# ---------------------------------------------------------------------------

def _draw_certificate(
    c: pdfcanvas.Canvas,
    candidate_name: str,
    job_role: str,
    overall_score: float,
    completed_at: str,
    certificate_id: Optional[str] = None,
) -> None:
    """Render every element of the certificate onto the given canvas."""

    cx = PAGE_W / 2

    # Background + border
    _draw_background(c)
    _draw_decorative_border(c)
    _draw_watermark_seal(c, cx, PAGE_H / 2)

    # Score ribbon (top-right)
    _draw_ribbon(c, overall_score)

    # Eyebrow
    y = PAGE_H - 3.4 * cm
    _draw_centered(c, 'CERTIFICATE OF COMPLETION', y,
                   'Helvetica', 11.5, CYAN, tracking=3.4)

    # Brand title
    y -= 1.05 * cm
    _draw_centered(c, 'AI Interview Coach', y, 'Helvetica-Bold', 30, WHITE)

    # Subtitle
    y -= 0.7 * cm
    _draw_centered(c, 'Interview Performance Certificate', y,
                   'Helvetica', 12, MUTED)

    # Decorative divider
    y -= 0.65 * cm
    div_w = 5.2 * cm
    c.saveState()
    grad_steps = 30
    for i in range(grad_steps):
        t = i / (grad_steps - 1)
        if t <= 0.5:
            col = _lerp_color(INDIGO, CYAN, t / 0.5 if t > 0 else 0)
        else:
            col = _lerp_color(CYAN, EMERALD, (t - 0.5) / 0.5)
        c.setStrokeColor(col)
        c.setLineWidth(1.4)
        seg_x1 = cx - div_w / 2 + (div_w / grad_steps) * i
        seg_x2 = seg_x1 + div_w / grad_steps
        c.line(seg_x1, y, seg_x2, y)
    c.restoreState()

    # "This certifies that"
    y -= 0.85 * cm
    _draw_centered(c, 'THIS CERTIFIES THAT', y, 'Helvetica', 9.5, MUTED, tracking=2.2)

    # Candidate name (hero text)
    y -= 1.15 * cm
    _draw_centered(c, candidate_name, y, 'Helvetica-Bold', 27, GOLD)

    name_w = stringWidth(candidate_name, 'Helvetica-Bold', 27)
    underline_w = max(name_w * 0.5, 3.5 * cm)
    c.setStrokeColor(colors.Color(GOLD.red, GOLD.green, GOLD.blue, alpha=0.45))
    c.setLineWidth(0.8)
    c.line(cx - underline_w / 2, y - 0.28 * cm, cx + underline_w / 2, y - 0.28 * cm)

    # "successfully completed..."
    y -= 0.95 * cm
    _draw_centered(
        c,
        'has successfully completed an AI-powered mock interview for the position of',
        y, 'Helvetica', 10.5, OFF_WHITE,
    )

    # Job role badge
    y -= 0.95 * cm
    role_font, role_size = 'Helvetica-Bold', 15
    role_w = stringWidth(job_role, role_font, role_size) + 1.6 * cm
    role_h = 0.85 * cm
    c.saveState()
    c.setFillColor(colors.Color(INDIGO.red, INDIGO.green, INDIGO.blue, alpha=0.18))
    c.roundRect(cx - role_w / 2, y - role_h * 0.62, role_w, role_h, role_h / 2,
               fill=1, stroke=0)
    c.setStrokeColor(INDIGO)
    c.setLineWidth(0.9)
    c.roundRect(cx - role_w / 2, y - role_h * 0.62, role_w, role_h, role_h / 2,
               fill=0, stroke=1)
    c.restoreState()
    _draw_centered(c, job_role, y - 0.18 * cm, role_font, role_size,
                   colors.HexColor('#a5b4fc'))

    # Performance label
    y -= 1.35 * cm
    perf_label = _performance_label(overall_score)
    _draw_centered(c, perf_label, y, 'Helvetica-Bold', 12,
                   _score_color(overall_score))

    # Score row
    y -= 1.25 * cm
    _draw_score_row(c, cx, y, overall_score)

    # Date + Certificate ID row
    y -= 1.55 * cm
    try:
        dt = datetime.fromisoformat(completed_at) if completed_at else datetime.utcnow()
    except (TypeError, ValueError):
        dt = datetime.utcnow()
    date_str = dt.strftime('%d %B %Y')
    _draw_centered(c, 'Issued on ' + date_str, y, 'Helvetica', 9.5, MUTED)

    if certificate_id:
        y -= 0.42 * cm
        _draw_centered(c, 'Certificate ID: ' + certificate_id, y,
                       'Helvetica', 8, MUTED_DARK)

    # Signature line + seal
    _draw_signature_block(c)
    _draw_seal_badge(c, PAGE_W - 3.0 * cm, 2.55 * cm)


def _draw_score_row(c: pdfcanvas.Canvas, cx: float, y: float,
                    overall_score: float) -> None:
    """Centred overall-score stat block."""
    c.setFont('Helvetica-Bold', 22)
    c.setFillColor(_score_color(overall_score))
    c.drawCentredString(cx, y, '%.1f' % overall_score)

    c.setFont('Helvetica', 8.5)
    c.setFillColor(MUTED)
    c.drawCentredString(cx, y - 0.38 * cm, 'OVERALL SCORE OUT OF 10')


def _draw_signature_block(c: pdfcanvas.Canvas) -> None:
    """Signature line + 'AI Interview Coach' authority label, bottom-left."""
    line_y   = 2.7 * cm
    line_x1  = 2.7 * cm
    line_x2  = line_x1 + 5.4 * cm

    c.setFont('Helvetica-Oblique', 18)
    c.setFillColor(WHITE)
    c.drawString(line_x1 + 0.3 * cm, line_y + 0.25 * cm, 'AI Interview Coach')

    c.setStrokeColor(colors.Color(1, 1, 1, alpha=0.35))
    c.setLineWidth(0.8)
    c.line(line_x1, line_y, line_x2, line_y)

    c.setFont('Helvetica', 8.5)
    c.setFillColor(MUTED)
    c.drawString(line_x1, line_y - 0.42 * cm, 'Authorised Digital Signature')


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_certificate(
    candidate_name: str,
    job_role: str,
    overall_score: float,
    completed_at: Optional[str] = None,
    interview_id: Optional[int] = None,
    output_path: Optional[str] = None,
) -> bytes:
    """
    Build a landscape Interview Completion Certificate PDF.

    Parameters
    ----------
    candidate_name : full name of the candidate
    job_role        : role the interview was conducted for
    overall_score   : final overall score (0.0-10.0)
    completed_at    : ISO-8601 timestamp string; defaults to "now" if omitted
    interview_id    : optional, used to build a human-readable Certificate ID
                      (e.g. "AIC-000042"); omitted from the PDF if not given
    output_path     : if given, also write the PDF bytes to this file path

    Returns
    -------
    Raw PDF bytes (1 page, A4 landscape).
    """
    candidate_name = (candidate_name or 'Candidate').strip()
    job_role        = (job_role or 'the role applied for').strip()
    overall_score   = max(0.0, min(10.0, float(overall_score or 0)))
    completed_at    = completed_at or datetime.utcnow().isoformat()

    certificate_id = ('AIC-%06d' % interview_id) if interview_id else None

    buffer = io.BytesIO()
    c = pdfcanvas.Canvas(buffer, pagesize=PAGE_SIZE)
    c.setTitle('Certificate of Completion - ' + candidate_name)
    c.setAuthor('AI Interview Coach')
    c.setSubject('Interview Completion Certificate for ' + job_role)

    _draw_certificate(
        c,
        candidate_name=candidate_name,
        job_role=job_role,
        overall_score=overall_score,
        completed_at=completed_at,
        certificate_id=certificate_id,
    )

    c.showPage()
    c.save()

    pdf_bytes = buffer.getvalue()

    if output_path:
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'wb') as f:
            f.write(pdf_bytes)

    return pdf_bytes


def generate_certificate_for_interview(
    interview_id: int,
    output_path: Optional[str] = None,
) -> bytes:
    """
    Convenience wrapper: fetch the Interview (and its Candidate) from the
    database and build the certificate PDF.  Must be called inside a Flask
    application context.

    Raises
    ------
    ValueError if the interview does not exist or has not been completed.
    """
    from models import get_interview

    iv = get_interview(interview_id)
    if iv is None:
        raise ValueError('Interview %s not found.' % interview_id)

    if iv.status != 'completed':
        raise ValueError(
            'Interview %s is not yet completed (status=%r); '
            'certificate is not available.' % (interview_id, iv.status)
        )

    candidate_name = iv.candidate.name if iv.candidate else 'Candidate'

    return generate_certificate(
        candidate_name=candidate_name,
        job_role=iv.job_role,
        overall_score=iv.overall_score,
        completed_at=iv.completed_at,
        interview_id=iv.id,
        output_path=output_path,
    )
