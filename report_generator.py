"""
report_generator.py — AI Interview Coach
=========================================
Generates a professional, multi-page PDF interview report using ReportLab.

Public API
----------
  generate_report(report_data: dict, output_path: str | None) -> bytes
      Build the PDF from the report_data dict (same shape as /api/report/<id>)
      and either write it to *output_path* or return the raw bytes.

  generate_report_for_interview(interview_id: int, output_path: str | None)
      Convenience wrapper that fetches the Interview from the DB and calls
      generate_report().

Report pages
------------
  Page 1 – Cover page (candidate info, role, date, overall score ring)
  Page 2 – Score dashboard (five dimension bars + summary narrative)
  Pages 3-N – Per-question breakdown (question → answer → scores → feedback)
  Final page – AI summary, top strengths/improvements, resources, recommendation
"""

from __future__ import annotations

import io
import os
from datetime import datetime
from typing import Optional

# ReportLab imports
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, HRFlowable, KeepTogether,
    PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle,
)
from reportlab.graphics.shapes import Drawing, Rect, String, Circle
from reportlab.graphics import renderPDF

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
INDIGO     = colors.HexColor('#6366f1')
CYAN       = colors.HexColor('#06b6d4')
EMERALD    = colors.HexColor('#10b981')
AMBER      = colors.HexColor('#f59e0b')
ROSE       = colors.HexColor('#ef4444')
VIOLET     = colors.HexColor('#8b5cf6')
DARK_BG    = colors.HexColor('#0f172a')
DARK_CARD  = colors.HexColor('#1e293b')
GREY_800   = colors.HexColor('#1e293b')
GREY_600   = colors.HexColor('#475569')
GREY_400   = colors.HexColor('#94a3b8')
GREY_100   = colors.HexColor('#f1f5f9')
WHITE      = colors.white
BLACK      = colors.black

DIM_COLORS = {
    'technical':     INDIGO,
    'communication': EMERALD,
    'confidence':    AMBER,
    'relevance':     CYAN,
    'completeness':  VIOLET,
}

TYPE_COLORS = {
    'Technical':  INDIGO,
    'HR':         EMERALD,
    'Behavioral': AMBER,
}

PAGE_W, PAGE_H = A4  # 595.28 x 841.89 pt


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

def _build_styles() -> dict:
    base = getSampleStyleSheet()

    def S(name, **kwargs) -> ParagraphStyle:
        return ParagraphStyle(name, parent=base['Normal'], **kwargs)

    return {
        'cover_title': S('cover_title',
            fontSize=34, textColor=WHITE, fontName='Helvetica-Bold',
            alignment=TA_CENTER, leading=40, spaceAfter=6),
        'cover_subtitle': S('cover_subtitle',
            fontSize=15, textColor=GREY_400, fontName='Helvetica',
            alignment=TA_CENTER, leading=20, spaceAfter=4),
        'cover_name': S('cover_name',
            fontSize=26, textColor=WHITE, fontName='Helvetica-Bold',
            alignment=TA_CENTER, leading=32, spaceBefore=12, spaceAfter=4),
        'cover_meta': S('cover_meta',
            fontSize=12, textColor=GREY_400, fontName='Helvetica',
            alignment=TA_CENTER, leading=18),
        'section_heading': S('section_heading',
            fontSize=15, textColor=INDIGO, fontName='Helvetica-Bold',
            spaceBefore=14, spaceAfter=6, leading=20),
        'sub_heading': S('sub_heading',
            fontSize=11, textColor=GREY_800, fontName='Helvetica-Bold',
            spaceBefore=8, spaceAfter=4, leading=14),
        'body': S('body',
            fontSize=10, textColor=GREY_800, fontName='Helvetica',
            leading=15, spaceAfter=4, alignment=TA_JUSTIFY),
        'body_muted': S('body_muted',
            fontSize=9, textColor=GREY_600, fontName='Helvetica',
            leading=14, spaceAfter=3),
        'answer_text': S('answer_text',
            fontSize=10, textColor=GREY_800, fontName='Helvetica',
            leading=15, spaceAfter=4, leftIndent=8, alignment=TA_JUSTIFY),
        'tag': S('tag',
            fontSize=9, fontName='Helvetica-Bold', leading=12),
        'score_label': S('score_label',
            fontSize=9, textColor=GREY_600, fontName='Helvetica',
            alignment=TA_CENTER, leading=12),
        'score_value': S('score_value',
            fontSize=18, fontName='Helvetica-Bold',
            alignment=TA_CENTER, leading=22),
        'footer': S('footer',
            fontSize=8, textColor=GREY_400, fontName='Helvetica',
            alignment=TA_CENTER),
        'q_number': S('q_number',
            fontSize=10, textColor=WHITE, fontName='Helvetica-Bold',
            alignment=TA_CENTER, leading=13),
        'q_text': S('q_text',
            fontSize=11, textColor=GREY_800, fontName='Helvetica-Bold',
            leading=16, spaceAfter=6),
        'summary_body': S('summary_body',
            fontSize=10, textColor=GREY_800, fontName='Helvetica',
            leading=16, spaceAfter=5, alignment=TA_JUSTIFY),
        'rec_label': S('rec_label',
            fontSize=13, fontName='Helvetica-Bold',
            alignment=TA_CENTER, leading=16),
    }


# ---------------------------------------------------------------------------
# Score → colour helper
# ---------------------------------------------------------------------------

def _score_color(score: float) -> colors.Color:
    if score >= 8:  return EMERALD
    if score >= 6:  return AMBER
    if score >= 4:  return colors.HexColor('#f97316')
    return ROSE


def _score_label(score: float) -> str:
    if score >= 9:   return 'Outstanding'
    if score >= 7.5: return 'Excellent'
    if score >= 6:   return 'Good'
    if score >= 4.5: return 'Average'
    return 'Needs Work'


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

def _score_ring(score: float, size: float = 90) -> Drawing:
    """Draw a circular score ring (conic gradient approximated as arc segments)."""
    d     = Drawing(size, size)
    cx    = size / 2
    cy    = size / 2
    r_out = size * 0.42
    r_in  = size * 0.28
    track_color = colors.HexColor('#e2e8f0')
    fill_color  = _score_color(score)

    # Track (full circle)
    from reportlab.graphics.shapes import Wedge
    d.add(Wedge(cx, cy, r_out, 0, 360, fillColor=track_color,
                strokeColor=None, strokeWidth=0, radius2=r_in))

    # Fill (proportional to score)
    if score > 0:
        angle = (score / 10.0) * 360
        d.add(Wedge(cx, cy, r_out, 90, 90 - angle, fillColor=fill_color,
                    strokeColor=None, strokeWidth=0, radius2=r_in))

    # Centre circle (white background)
    d.add(Circle(cx, cy, r_in - 2, fillColor=WHITE, strokeColor=None))

    # Score text
    d.add(String(cx, cy - 6, f'{score:.1f}',
                 textAnchor='middle', fontSize=size * 0.20,
                 fontName='Helvetica-Bold', fillColor=GREY_800))

    return d


def _dimension_bar(label: str, score: float, bar_w: float = 320,
                   bar_h: float = 10) -> Table:
    """Return a Table row: label | progress bar | score value."""
    dim_color = DIM_COLORS.get(label.lower(), INDIGO)
    fill_w    = max(1.0, bar_w * score / 10.0)

    bar_drawing = Drawing(bar_w, bar_h)
    # Track
    bar_drawing.add(Rect(0, 0, bar_w, bar_h, rx=bar_h / 2, ry=bar_h / 2,
                         fillColor=GREY_100, strokeColor=None))
    # Fill
    bar_drawing.add(Rect(0, 0, fill_w, bar_h, rx=bar_h / 2, ry=bar_h / 2,
                         fillColor=dim_color, strokeColor=None))

    sty = getSampleStyleSheet()['Normal']
    label_p = Paragraph(
        f'<font name="Helvetica" size="9" color="#{GREY_600.hexval()[2:]}">'
        f'{label.capitalize()}</font>', sty)
    score_p = Paragraph(
        f'<font name="Helvetica-Bold" size="9">{score:.1f}</font>', sty)

    tbl = Table(
        [[label_p, bar_drawing, score_p]],
        colWidths=[90, bar_w, 36],
        rowHeights=[max(bar_h + 4, 16)],
    )
    tbl.setStyle(TableStyle([
        ('VALIGN',  (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING',  (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING',   (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 2),
    ]))
    return tbl


def _bullet_list(items: list, color: colors.Color,
                 icon: str = '●', styles: dict = None) -> list:
    """Return a list of Paragraph flowables for a bullet list."""
    if styles is None:
        styles = _build_styles()
    out = []
    for item in items:
        hex_c = color.hexval()[2:]  # strip '0x' prefix
        p = Paragraph(
            f'<font color="#{hex_c}">{icon}</font>  {item}',
            styles['body'],
        )
        out.append(p)
    return out


# ---------------------------------------------------------------------------
# Page templates (header/footer canvases)
# ---------------------------------------------------------------------------

class _ReportCanvas:
    """Mixin methods drawn on every non-cover page."""

    HEADER_H = 36

    @staticmethod
    def draw_header(canvas, doc, interview: dict):
        canvas.saveState()
        canvas.setFillColor(DARK_BG)
        canvas.rect(0, PAGE_H - _ReportCanvas.HEADER_H,
                    PAGE_W, _ReportCanvas.HEADER_H, fill=1, stroke=0)
        canvas.setFont('Helvetica-Bold', 9)
        canvas.setFillColor(WHITE)
        canvas.drawString(1.5 * cm,
                          PAGE_H - _ReportCanvas.HEADER_H + 12,
                          'AI Interview Coach  |  Confidential Report')
        canvas.setFont('Helvetica', 9)
        canvas.setFillColor(GREY_400)
        canvas.drawRightString(PAGE_W - 1.5 * cm,
                               PAGE_H - _ReportCanvas.HEADER_H + 12,
                               interview.get('name', ''))
        canvas.restoreState()

    @staticmethod
    def draw_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(GREY_400)
        y = 0.7 * cm
        canvas.drawCentredString(PAGE_W / 2, y,
                                 f'Page {doc.page}  |  Generated {datetime.now().strftime("%d %b %Y")}')
        canvas.setStrokeColor(GREY_100)
        canvas.setLineWidth(0.5)
        canvas.line(1.5 * cm, y + 10, PAGE_W - 1.5 * cm, y + 10)
        canvas.restoreState()


def _make_doc_template(buffer: io.BytesIO, interview: dict) -> BaseDocTemplate:
    """Build the BaseDocTemplate with cover and inner page templates."""
    doc = BaseDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=f"Interview Report – {interview.get('name', '')}",
        author='AI Interview Coach',
    )

    # Cover page — full bleed, no header/footer
    cover_frame = Frame(0, 0, PAGE_W, PAGE_H, id='cover')

    def cover_bg(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(DARK_BG)
        canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
        # Decorative gradient band at top
        canvas.setFillColor(INDIGO)
        canvas.rect(0, PAGE_H - 5, PAGE_W, 5, fill=1, stroke=0)
        canvas.setFillColor(CYAN)
        canvas.rect(0, PAGE_H - 8, PAGE_W, 3, fill=1, stroke=0)
        canvas.restoreState()

    cover_template = PageTemplate(id='Cover', frames=[cover_frame],
                                  onPage=cover_bg)

    # Inner pages — with header/footer, proper margins
    inner_frame = Frame(
        1.5 * cm,
        1.5 * cm,
        PAGE_W - 3 * cm,
        PAGE_H - 3 * cm - _ReportCanvas.HEADER_H,
        id='inner',
        topPadding=_ReportCanvas.HEADER_H + 6,
    )

    def inner_page(canvas, d):
        _ReportCanvas.draw_header(canvas, d, interview)
        _ReportCanvas.draw_footer(canvas, d)

    inner_template = PageTemplate(id='Inner', frames=[inner_frame],
                                  onPage=inner_page)

    doc.addPageTemplates([cover_template, inner_template])
    return doc


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _build_cover(interview: dict, overall_score: float,
                 styles: dict) -> list:
    """Return flowables for the cover page."""
    story = []

    story.append(Spacer(1, 3.5 * cm))

    # Logo / Brand
    story.append(Paragraph('🤖', ParagraphStyle('emoji',
        fontSize=52, alignment=TA_CENTER, leading=60)))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph('AI Interview Coach', styles['cover_title']))
    story.append(Paragraph('Interview Performance Report',
                            styles['cover_subtitle']))

    # Divider
    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width='60%', thickness=1,
                             color=INDIGO, hAlign='CENTER'))
    story.append(Spacer(1, 0.5 * cm))

    # Candidate name
    story.append(Paragraph(interview.get('name', '—'),
                            styles['cover_name']))
    story.append(Paragraph(interview.get('email', ''),
                            styles['cover_meta']))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(interview.get('job_role', '—'),
                            ParagraphStyle('role', parent=styles['cover_meta'],
                                           textColor=CYAN, fontSize=14,
                                           fontName='Helvetica-Bold')))
    story.append(Paragraph(interview.get('experience_level', ''),
                            styles['cover_meta']))

    # Score ring
    story.append(Spacer(1, 1.2 * cm))
    ring = _score_ring(overall_score, size=140)
    story.append(Table([[ring]], colWidths=[PAGE_W - 3 * cm]))

    score_lbl = _score_label(overall_score)
    story.append(Paragraph(score_lbl,
                            ParagraphStyle('slbl',
                                parent=styles['cover_meta'],
                                textColor=_score_color(overall_score),
                                fontSize=13, fontName='Helvetica-Bold',
                                spaceBefore=6)))
    story.append(Paragraph('Overall Score',
                            ParagraphStyle('slbl2', parent=styles['cover_meta'],
                                           fontSize=11)))

    # Date
    story.append(Spacer(1, 1 * cm))
    completed = interview.get('completed_at') or datetime.utcnow().isoformat()
    try:
        dt_str = datetime.fromisoformat(completed).strftime('%d %B %Y, %H:%M UTC')
    except Exception:
        dt_str = completed
    story.append(Paragraph(f'Completed: {dt_str}',
                            styles['cover_meta']))

    story.append(PageBreak())
    return story


def _build_score_dashboard(interview: dict, responses: list,
                            styles: dict) -> list:
    """Score overview page: four summary cards + five dimension bars."""
    story = []
    story.append(Paragraph('Score Dashboard', styles['section_heading']))
    story.append(HRFlowable(width='100%', thickness=0.5,
                             color=GREY_100, spaceAfter=10))

    # Four summary cards
    overall = interview.get('overall_score', 0)
    tech    = interview.get('technical_score', 0)
    comm    = interview.get('communication_score', 0)
    conf    = interview.get('confidence_score', 0)

    def card(label, value):
        c = _score_color(float(value))
        return [
            Paragraph(f'<font name="Helvetica-Bold" size="18"'
                      f' color="#{c.hexval()[2:]}">{float(value):.1f}</font>',
                      ParagraphStyle('cv', alignment=TA_CENTER, leading=22)),
            Paragraph(label,
                      ParagraphStyle('cl', fontSize=9, textColor=GREY_600,
                                     alignment=TA_CENTER, leading=12,
                                     fontName='Helvetica')),
        ]

    cards_data = [[
        card('Overall', overall),
        card('Technical', tech),
        card('Communication', comm),
        card('Confidence', conf),
    ]]
    card_tbl = Table(cards_data,
                     colWidths=[(PAGE_W - 3 * cm) / 4] * 4,
                     rowHeights=[60])
    card_tbl.setStyle(TableStyle([
        ('BOX',         (0, 0), (0, 0), 0.5, GREY_100),
        ('BOX',         (1, 0), (1, 0), 0.5, GREY_100),
        ('BOX',         (2, 0), (2, 0), 0.5, GREY_100),
        ('BOX',         (3, 0), (3, 0), 0.5, GREY_100),
        ('BACKGROUND',  (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('VALIGN',      (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',(0, 0), (-1, -1), 6),
        ('TOPPADDING',  (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 10),
        ('ROUNDEDCORNERS', [5]),
    ]))
    story.append(card_tbl)
    story.append(Spacer(1, 0.6 * cm))

    # Compute per-dimension averages from responses
    story.append(Paragraph('Dimension Breakdown', styles['sub_heading']))

    dims = ['technical', 'communication', 'confidence', 'relevance', 'completeness']
    scored = [r for r in responses if r.get('scores')]
    n = len(scored)

    for dim in dims:
        avg = (sum(r['scores'].get(dim, 0) for r in scored) / n) if n else 0.0
        story.append(_dimension_bar(dim, round(avg, 1)))
        story.append(Spacer(1, 4))

    story.append(Spacer(1, 0.4 * cm))

    # Quick stats
    answered = sum(1 for r in responses if r.get('answer_text'))
    story.append(Paragraph('Session Statistics', styles['sub_heading']))

    stats = [
        ['Questions Asked', str(len(responses))],
        ['Questions Answered', str(answered)],
        ['Questions Skipped',  str(len(responses) - answered)],
        ['Job Role',          interview.get('job_role', '—')],
        ['Experience Level',  interview.get('experience_level', '—')],
    ]
    stat_tbl = Table(stats, colWidths=[160, PAGE_W - 3 * cm - 160])
    stat_tbl.setStyle(TableStyle([
        ('FONT',        (0, 0), (0, -1), 'Helvetica-Bold', 9),
        ('FONT',        (1, 0), (1, -1), 'Helvetica',      9),
        ('TEXTCOLOR',   (0, 0), (0, -1), GREY_600),
        ('TEXTCOLOR',   (1, 0), (1, -1), GREY_800),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1),
         [colors.HexColor('#f8fafc'), WHITE]),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING',   (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.3, GREY_100),
    ]))
    story.append(stat_tbl)
    story.append(PageBreak())
    return story


def _build_response_pages(responses: list, styles: dict) -> list:
    """One section per question: question → answer → dimension bars → feedback tags."""
    story = []
    story.append(Paragraph('Question-by-Question Breakdown',
                            styles['section_heading']))
    story.append(HRFlowable(width='100%', thickness=0.5,
                             color=GREY_100, spaceAfter=10))

    type_tag_style = ParagraphStyle('type_tag',
        fontSize=8, fontName='Helvetica-Bold',
        textColor=WHITE, alignment=TA_CENTER, leading=11)

    for resp in responses:
        q_num  = resp.get('question_number', '?')
        q_text = resp.get('question_text', '(no question)')
        q_type = resp.get('question_type', 'General')
        a_text = resp.get('answer_text') or '(no answer recorded)'
        scores = resp.get('scores', {})
        strengths   = resp.get('strengths',   [])
        weaknesses  = resp.get('weaknesses',  [])
        suggestions = resp.get('suggestions', [])

        # Compute per-answer average
        score_vals = [v for v in scores.values() if isinstance(v, (int, float))]
        avg = round(sum(score_vals) / len(score_vals), 1) if score_vals else 0.0
        avg_color = _score_color(avg)

        # Question header row
        type_color = TYPE_COLORS.get(q_type, INDIGO)

        num_cell = Table(
            [[Paragraph(str(q_num), styles['q_number'])]],
            colWidths=[22], rowHeights=[22],
        )
        num_cell.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), INDIGO),
            ('ROUNDEDCORNERS', [11]),
            ('VALIGN', (0, 0), (0, 0), 'MIDDLE'),
            ('TOPPADDING',    (0, 0), (0, 0), 5),
            ('BOTTOMPADDING', (0, 0), (0, 0), 5),
        ]))

        type_cell = Table(
            [[Paragraph(q_type, type_tag_style)]],
            colWidths=[62], rowHeights=[18],
        )
        type_cell.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), type_color),
            ('ROUNDEDCORNERS', [9]),
            ('VALIGN', (0, 0), (0, 0), 'MIDDLE'),
        ]))

        avg_cell = Paragraph(
            f'<font name="Helvetica-Bold" size="12"'
            f' color="#{avg_color.hexval()[2:]}">{avg:.1f}/10</font>',
            ParagraphStyle('avg', alignment=TA_RIGHT, leading=14))

        header_tbl = Table(
            [[num_cell, Paragraph(q_text, styles['q_text']), type_cell, avg_cell]],
            colWidths=[30, PAGE_W - 3 * cm - 30 - 70 - 60, 70, 60],
        )
        header_tbl.setStyle(TableStyle([
            ('VALIGN',      (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING',(0, 0), (-1, -1), 3),
            ('TOPPADDING',  (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING',(0,0), (-1,-1),  0),
        ]))

        # Answer block
        answer_block = Table(
            [[Paragraph(
                f'<font name="Helvetica-Bold" size="8"'
                f' color="#{GREY_400.hexval()[2:]}">CANDIDATE ANSWER</font>',
                styles['body_muted'])],
             [Paragraph(a_text, styles['answer_text'])]],
            colWidths=[PAGE_W - 3 * cm - 8],
        )
        answer_block.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
            ('BOX',           (0, 0), (-1, -1), 0.5, GREY_100),
            ('LEFTPADDING',   (0, 0), (-1, -1), 8),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 8),
            ('TOPPADDING',    (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('ROUNDEDCORNERS', [4]),
        ]))

        # Mini dimension bars
        bar_rows = []
        for dim in ['technical', 'communication', 'confidence',
                    'relevance', 'completeness']:
            val = scores.get(dim, 0.0)
            bar_rows.append(_dimension_bar(dim, val,
                                           bar_w=PAGE_W - 3 * cm - 140,
                                           bar_h=7))

        # Feedback chips
        chip_rows = []
        sty_base = getSampleStyleSheet()['Normal']
        for item in strengths[:3]:
            chip_rows.append(Table(
                [[Paragraph(f'✅ {item}',
                            ParagraphStyle('chip_s', parent=sty_base,
                                           fontSize=8, textColor=EMERALD,
                                           leading=11))]],
                colWidths=[PAGE_W - 3 * cm - 8],
            ))
        for item in weaknesses[:2]:
            chip_rows.append(Table(
                [[Paragraph(f'❌ {item}',
                            ParagraphStyle('chip_w', parent=sty_base,
                                           fontSize=8, textColor=ROSE,
                                           leading=11))]],
                colWidths=[PAGE_W - 3 * cm - 8],
            ))
        for item in suggestions[:2]:
            chip_rows.append(Table(
                [[Paragraph(f'💡 {item}',
                            ParagraphStyle('chip_g', parent=sty_base,
                                           fontSize=8, textColor=AMBER,
                                           leading=11))]],
                colWidths=[PAGE_W - 3 * cm - 8],
            ))

        block = KeepTogether([
            header_tbl,
            Spacer(1, 5),
            answer_block,
            Spacer(1, 6),
            *bar_rows,
            Spacer(1, 4),
            *chip_rows,
            HRFlowable(width='100%', thickness=0.4,
                       color=GREY_100, spaceBefore=10, spaceAfter=8),
        ])
        story.append(block)

    story.append(PageBreak())
    return story


def _build_summary_page(interview: dict, summary: Optional[dict],
                        styles: dict) -> list:
    """Final AI summary page."""
    story = []
    story.append(Paragraph('AI Final Summary', styles['section_heading']))
    story.append(HRFlowable(width='100%', thickness=0.5,
                             color=GREY_100, spaceAfter=10))

    if summary:
        # Executive summary
        exec_text = summary.get('executive_summary', '')
        if exec_text:
            story.append(Paragraph('Executive Summary', styles['sub_heading']))
            story.append(Paragraph(exec_text, styles['summary_body']))
            story.append(Spacer(1, 0.4 * cm))

        # Top strengths
        top_s = summary.get('top_strengths', [])
        if top_s:
            story.append(Paragraph('Top Strengths', styles['sub_heading']))
            story.extend(_bullet_list(top_s, EMERALD, '✓', styles))
            story.append(Spacer(1, 0.3 * cm))

        # Top improvements
        top_i = summary.get('top_improvements', [])
        if top_i:
            story.append(Paragraph('Key Improvement Areas', styles['sub_heading']))
            story.extend(_bullet_list(top_i, ROSE, '→', styles))
            story.append(Spacer(1, 0.3 * cm))

        # Resources
        resources = summary.get('recommended_resources', [])
        if resources:
            story.append(Paragraph('Recommended Resources', styles['sub_heading']))
            story.extend(_bullet_list(resources, INDIGO, '📚', styles))
            story.append(Spacer(1, 0.4 * cm))

        # Hire recommendation
        rec = summary.get('hire_recommendation', '')
        if rec:
            rec_colors = {
                'Strong Yes': EMERALD,
                'Yes':        INDIGO,
                'Maybe':      AMBER,
                'No':         ROSE,
            }
            rec_c = rec_colors.get(rec, INDIGO)
            rec_tbl = Table(
                [[Paragraph(
                    f'<font color="#{rec_c.hexval()[2:]}"'
                    f' name="Helvetica-Bold">{rec}</font>',
                    ParagraphStyle('rec', fontSize=16, fontName='Helvetica-Bold',
                                   alignment=TA_CENTER, leading=20)),
                  Paragraph('Hire Recommendation',
                             ParagraphStyle('rl', fontSize=10, textColor=GREY_600,
                                            fontName='Helvetica',
                                            alignment=TA_CENTER, leading=13))]],
                colWidths=[(PAGE_W - 3 * cm) / 2, (PAGE_W - 3 * cm) / 2],
                rowHeights=[55],
            )
            rec_tbl.setStyle(TableStyle([
                ('BOX',         (0, 0), (-1, -1), 0.5, rec_c),
                ('BACKGROUND',  (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
                ('VALIGN',      (0, 0), (-1, -1), 'MIDDLE'),
                ('ROUNDEDCORNERS', [6]),
            ]))
            story.append(rec_tbl)

    else:
        # Fallback: derive a basic summary from scores
        overall = interview.get('overall_score', 0)
        story.append(Paragraph(
            f'This candidate achieved an overall score of {overall:.1f}/10. '
            f'Please refer to the per-question breakdown for detailed feedback.',
            styles['summary_body']))

    # Footer note
    story.append(Spacer(1, 0.8 * cm))
    story.append(HRFlowable(width='100%', thickness=0.4, color=GREY_100))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(
        'This report was generated automatically by AI Interview Coach. '
        'Scores are based on AI analysis and should be used as one of many signals '
        'in a hiring decision.',
        ParagraphStyle('disclaimer', fontSize=8, textColor=GREY_400,
                       fontName='Helvetica', alignment=TA_CENTER, leading=12)))

    return story


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_report(
    report_data: dict,
    output_path: Optional[str] = None,
    summary: Optional[dict] = None,
) -> bytes:
    """
    Build a professional PDF interview report.

    Parameters
    ----------
    report_data  : dict with 'interview' and 'responses' keys
                   (same shape as /api/report/<id> response)
    output_path  : if given, write the PDF to this path as well as returning bytes
    summary      : optional SummaryResult.to_dict() for the final page

    Returns
    -------
    Raw PDF bytes.
    """
    interview = report_data.get('interview', {})
    responses = report_data.get('responses', [])
    overall   = float(interview.get('overall_score', 0))

    styles  = _build_styles()
    buffer  = io.BytesIO()
    doc     = _make_doc_template(buffer, interview)

    # Build the story
    story = []

    # 1. Cover page (uses 'Cover' page template)
    story += _build_cover(interview, overall, styles)

    # Switch to inner template for all subsequent pages
    from reportlab.platypus import NextPageTemplate
    story.append(NextPageTemplate('Inner'))

    # 2. Score dashboard
    story += _build_score_dashboard(interview, responses, styles)

    # 3. Per-question breakdown
    if responses:
        story += _build_response_pages(responses, styles)

    # 4. AI summary
    story += _build_summary_page(interview, summary, styles)

    doc.build(story)

    pdf_bytes = buffer.getvalue()

    if output_path:
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'wb') as f:
            f.write(pdf_bytes)

    return pdf_bytes


def generate_report_for_interview(
    interview_id: int,
    output_path: Optional[str] = None,
    summary: Optional[dict] = None,
) -> bytes:
    """
    Convenience wrapper: fetch Interview from DB, build and return PDF bytes.
    Must be called inside a Flask application context.
    """
    from models import get_interview, build_report_dict

    iv = get_interview(interview_id)
    if iv is None:
        raise ValueError(f'Interview {interview_id} not found.')

    report_data = build_report_dict(iv)
    return generate_report(report_data, output_path=output_path, summary=summary)
