"""
email_service.py — AI Interview Coach
=======================================
Sends interview report and certificate PDFs to candidates via SMTP.

All connection settings are read from environment variables so no
credentials are hard-coded:

  SMTP_HOST        e.g. "smtp.gmail.com"
  SMTP_PORT        e.g. "587" (TLS) or "465" (SSL).  Defaults to 587.
  SMTP_USERNAME    the account used to authenticate with the SMTP server
  SMTP_PASSWORD    the account password / app-password
  SMTP_USE_TLS     "true" / "false" — STARTTLS on port 587. Defaults to "true".
  SMTP_USE_SSL     "true" / "false" — implicit SSL on port 465. Defaults to "false".
  EMAIL_FROM       sender address shown to the recipient.
                    Falls back to SMTP_USERNAME if not set.
  EMAIL_FROM_NAME  display name for the sender. Defaults to "AI Interview Coach".

Public API
----------
  send_report_email(to_email, candidate_name, job_role, overall_score,
                    pdf_bytes, interview_id=None) -> bool
      Email the interview report PDF as an attachment.

  send_certificate_email(to_email, candidate_name, job_role, overall_score,
                         pdf_bytes, interview_id=None) -> bool
      Email the completion certificate PDF as an attachment.

  send_report_and_certificate_email(to_email, candidate_name, job_role,
                                    overall_score, report_pdf_bytes,
                                    certificate_pdf_bytes,
                                    interview_id=None) -> bool
      Email both PDFs as attachments on a single message.

  send_email_with_attachment(to_email, subject, html_body, attachments,
                             plain_body=None) -> bool
      Low-level helper the functions above are built on; can also be used
      directly for custom emails.

  is_configured() -> bool
      True if the minimum required environment variables are present.

Every public function returns True on success and False on failure;
failures are logged but never raise, so a broken mail server never
breaks the candidate-facing interview flow.
"""

from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Optional

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION (read once at import time, with sane defaults)
# =============================================================================

SMTP_HOST       = os.environ.get('SMTP_HOST', '').strip()
SMTP_PORT       = int(os.environ.get('SMTP_PORT', '587') or '587')
SMTP_USERNAME   = os.environ.get('SMTP_USERNAME', '').strip()
SMTP_PASSWORD   = os.environ.get('SMTP_PASSWORD', '').strip()
SMTP_USE_TLS    = os.environ.get('SMTP_USE_TLS', 'true').strip().lower() == 'true'
SMTP_USE_SSL    = os.environ.get('SMTP_USE_SSL', 'false').strip().lower() == 'true'

EMAIL_FROM      = (os.environ.get('EMAIL_FROM', '') or SMTP_USERNAME).strip()
EMAIL_FROM_NAME = os.environ.get('EMAIL_FROM_NAME', 'AI Interview Coach').strip()

# Network timeout for the SMTP connection, in seconds.
SMTP_TIMEOUT = int(os.environ.get('SMTP_TIMEOUT', '20') or '20')


def is_configured() -> bool:
    """
    Return True if the minimum environment variables required to send
    email are present (host, username, password, and a from-address).
    Callers can use this to skip the "Send Email" UI affordance entirely
    when SMTP has not been set up.
    """
    return bool(SMTP_HOST and SMTP_USERNAME and SMTP_PASSWORD and EMAIL_FROM)


# =============================================================================
# INTERNAL — LOW-LEVEL SMTP SEND
# =============================================================================

def _build_message(
    to_email: str,
    subject: str,
    html_body: str,
    plain_body: Optional[str] = None,
) -> MIMEMultipart:
    """
    Build a multipart/mixed message with an HTML body (and an optional
    plain-text fallback part).  Attachments are added separately by the
    caller via msg.attach(...).
    """
    msg = MIMEMultipart('mixed')
    msg['Subject'] = subject
    msg['From']    = formataddr((EMAIL_FROM_NAME, EMAIL_FROM))
    msg['To']      = to_email

    # multipart/alternative for the text/html body parts
    body_part = MIMEMultipart('alternative')
    if plain_body:
        body_part.attach(MIMEText(plain_body, 'plain', 'utf-8'))
    body_part.attach(MIMEText(html_body, 'html', 'utf-8'))
    msg.attach(body_part)

    return msg


def _attach_pdf(msg: MIMEMultipart, pdf_bytes: bytes, filename: str) -> None:
    """Attach a single PDF file (as bytes) to an email message."""
    part = MIMEApplication(pdf_bytes, _subtype='pdf')
    part.add_header('Content-Disposition', 'attachment', filename=filename)
    part.add_header('Content-Type', 'application/pdf', name=filename)
    msg.attach(part)


def _send_smtp(msg: MIMEMultipart, to_email: str) -> bool:
    """
    Open an SMTP connection using the configured environment settings,
    authenticate, and send *msg*.  Returns True on success, False on any
    failure (connection error, auth error, etc.) — never raises.
    """
    if not is_configured():
        logger.error(
            '[email_service] SMTP is not configured. '
            'Set SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, and EMAIL_FROM.'
        )
        return False

    try:
        if SMTP_USE_SSL:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(
                SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT, context=context
            ) as server:
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.sendmail(EMAIL_FROM, [to_email], msg.as_string())
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT) as server:
                server.ehlo()
                if SMTP_USE_TLS:
                    context = ssl.create_default_context()
                    server.starttls(context=context)
                    server.ehlo()
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.sendmail(EMAIL_FROM, [to_email], msg.as_string())

        logger.info('[email_service] Email sent to %s: %s', to_email, msg['Subject'])
        return True

    except smtplib.SMTPAuthenticationError as exc:
        logger.error('[email_service] SMTP authentication failed: %s', exc)
        return False
    except smtplib.SMTPRecipientsRefused as exc:
        logger.error('[email_service] Recipient refused (%s): %s', to_email, exc)
        return False
    except smtplib.SMTPConnectError as exc:
        logger.error('[email_service] Could not connect to %s:%s -- %s',
                     SMTP_HOST, SMTP_PORT, exc)
        return False
    except (smtplib.SMTPException, OSError, TimeoutError) as exc:
        logger.error('[email_service] Failed to send email to %s: %s', to_email, exc)
        return False
    except Exception:
        logger.exception('[email_service] Unexpected error sending email to %s', to_email)
        return False


# =============================================================================
# PUBLIC: GENERIC SEND-WITH-ATTACHMENTS
# =============================================================================

def send_email_with_attachment(
    to_email: str,
    subject: str,
    html_body: str,
    attachments: list,
    plain_body: Optional[str] = None,
) -> bool:
    """
    Send an email with one or more PDF attachments.

    Parameters
    ----------
    to_email    : recipient email address
    subject     : email subject line
    html_body   : HTML content for the email body
    attachments : list of (pdf_bytes, filename) tuples to attach
    plain_body  : optional plain-text fallback body

    Returns
    -------
    bool — True if the email was sent successfully, False otherwise.
    """
    to_email = (to_email or '').strip()
    if not to_email or '@' not in to_email:
        logger.error('[email_service] Invalid recipient email: %r', to_email)
        return False

    if not attachments:
        logger.warning('[email_service] send_email_with_attachment called with no attachments.')

    msg = _build_message(to_email, subject, html_body, plain_body)

    for pdf_bytes, filename in attachments:
        if pdf_bytes:
            _attach_pdf(msg, pdf_bytes, filename)

    return _send_smtp(msg, to_email)


# =============================================================================
# HTML EMAIL TEMPLATES
# =============================================================================

def _email_wrapper(inner_html: str) -> str:
    """Wrap inner content in a consistent, dark-themed HTML email shell."""
    return (
        '<!DOCTYPE html>'
        '<html><body style="margin:0;padding:0;background-color:#0a0e1a;'
        'font-family:Arial,Helvetica,sans-serif;">'
        '<table width="100%" cellpadding="0" cellspacing="0" '
        'style="background-color:#0a0e1a;padding:32px 16px;">'
        '<tr><td align="center">'
        '<table width="100%" cellpadding="0" cellspacing="0" '
        'style="max-width:560px;background-color:#141d2e;border:1px solid #1e2d45;'
        'border-radius:14px;overflow:hidden;">'
        '<tr><td style="background:linear-gradient(135deg,#6366f1,#06b6d4);padding:22px 28px;">'
        '<span style="color:#ffffff;font-size:18px;font-weight:700;letter-spacing:-0.02em;">'
        '&#129302; AI Interview Coach</span>'
        '</td></tr>'
        '<tr><td style="padding:28px;color:#e2e8f0;font-size:14px;line-height:1.6;">'
        + inner_html +
        '</td></tr>'
        '<tr><td style="padding:18px 28px;border-top:1px solid #1e2d45;'
        'color:#64748b;font-size:12px;text-align:center;">'
        'This is an automated message from AI Interview Coach. '
        'Please do not reply directly to this email.'
        '</td></tr>'
        '</table></td></tr></table></body></html>'
    )


def _report_email_html(candidate_name: str, job_role: str,
                       overall_score: float) -> str:
    score_color = '#10b981' if overall_score >= 7 else '#f59e0b' if overall_score >= 5 else '#ef4444'
    inner = (
        '<p style="margin:0 0 16px;">Hi ' + candidate_name + ',</p>'
        '<p style="margin:0 0 16px;">'
        'Thank you for completing your AI-powered mock interview for the '
        '<strong style="color:#a5b4fc;">' + job_role + '</strong> role. '
        'Your detailed performance report is attached as a PDF.</p>'
        '<table cellpadding="0" cellspacing="0" style="margin:20px 0;"><tr>'
        '<td style="background-color:#1a2235;border:1px solid #1e2d45;'
        'border-radius:10px;padding:16px 24px;text-align:center;">'
        '<div style="font-size:32px;font-weight:800;color:' + score_color + ';">'
        '%.1f<span style="font-size:16px;color:#64748b;">/10</span></div>'
        '<div style="font-size:11px;color:#64748b;text-transform:uppercase;'
        'letter-spacing:0.05em;margin-top:4px;">Overall Score</div>'
        '</td></tr></table>'
        '<p style="margin:0 0 16px;">'
        'The attached report includes a full breakdown of your technical, '
        'communication, and confidence scores, question-by-question feedback, '
        'and an AI-generated summary with suggestions for improvement.</p>'
        '<p style="margin:0;">Best of luck with your real interviews!</p>'
        '<p style="margin:16px 0 0;color:#94a3b8;">'
        '&mdash; The AI Interview Coach Team</p>'
    ) % overall_score
    return _email_wrapper(inner)


def _certificate_email_html(candidate_name: str, job_role: str,
                            overall_score: float) -> str:
    inner = (
        '<p style="margin:0 0 16px;">Hi ' + candidate_name + ',</p>'
        '<p style="margin:0 0 16px;">'
        '&#127881; Congratulations on completing your AI-powered mock interview '
        'for the <strong style="color:#a5b4fc;">' + job_role + '</strong> role!</p>'
        '<p style="margin:0 0 16px;">'
        'Your official Certificate of Completion is attached, recognising an '
        'overall performance score of <strong style="color:#10b981;">'
        '%.1f/10</strong>. Feel free to share it on LinkedIn or add it to your '
        'portfolio.</p>'
        '<p style="margin:0;">Keep practising and good luck with your job search!</p>'
        '<p style="margin:16px 0 0;color:#94a3b8;">'
        '&mdash; The AI Interview Coach Team</p>'
    ) % overall_score
    return _email_wrapper(inner)


def _combined_email_html(candidate_name: str, job_role: str,
                         overall_score: float) -> str:
    inner = (
        '<p style="margin:0 0 16px;">Hi ' + candidate_name + ',</p>'
        '<p style="margin:0 0 16px;">'
        'Thank you for completing your AI-powered mock interview for the '
        '<strong style="color:#a5b4fc;">' + job_role + '</strong> role. '
        'Attached you will find both your detailed performance report and '
        'your official Certificate of Completion.</p>'
        '<p style="margin:0 0 16px;">Overall score: '
        '<strong style="color:#10b981;">%.1f/10</strong></p>'
        '<p style="margin:0;">Best of luck with your real interviews!</p>'
        '<p style="margin:16px 0 0;color:#94a3b8;">'
        '&mdash; The AI Interview Coach Team</p>'
    ) % overall_score
    return _email_wrapper(inner)


# =============================================================================
# PUBLIC: SEND INTERVIEW REPORT
# =============================================================================

def send_report_email(
    to_email: str,
    candidate_name: str,
    job_role: str,
    overall_score: float,
    pdf_bytes: bytes,
    interview_id: Optional[int] = None,
) -> bool:
    """
    Email the interview report PDF to the candidate.

    Parameters
    ----------
    to_email       : candidate's email address
    candidate_name : candidate's full name (used in the greeting)
    job_role        : job role the interview was conducted for
    overall_score   : final overall score (0.0-10.0), shown in the email body
    pdf_bytes       : the report PDF, as produced by
                      report_generator.generate_report()
    interview_id    : optional, used to build a descriptive filename

    Returns
    -------
    bool — True if the email was sent successfully, False otherwise.
    """
    if not pdf_bytes:
        logger.error('[email_service] send_report_email called with empty pdf_bytes.')
        return False

    filename = (
        'Interview_Report_%s.pdf' % interview_id
        if interview_id else 'Interview_Report.pdf'
    )

    subject = 'Your AI Interview Coach Report - ' + job_role
    html    = _report_email_html(candidate_name, job_role, overall_score)
    plain   = (
        'Hi %s,\n\n'
        'Thank you for completing your AI-powered mock interview for the '
        '%s role. Your overall score was %.1f/10. '
        'Please find your detailed report attached as a PDF.\n\n'
        '-- The AI Interview Coach Team'
    ) % (candidate_name, job_role, overall_score)

    return send_email_with_attachment(
        to_email=to_email,
        subject=subject,
        html_body=html,
        attachments=[(pdf_bytes, filename)],
        plain_body=plain,
    )


# =============================================================================
# PUBLIC: SEND CERTIFICATE
# =============================================================================

def send_certificate_email(
    to_email: str,
    candidate_name: str,
    job_role: str,
    overall_score: float,
    pdf_bytes: bytes,
    interview_id: Optional[int] = None,
) -> bool:
    """
    Email the completion certificate PDF to the candidate.

    Parameters
    ----------
    to_email       : candidate's email address
    candidate_name : candidate's full name (used in the greeting)
    job_role        : job role the interview was conducted for
    overall_score   : final overall score (0.0-10.0), shown in the email body
    pdf_bytes       : the certificate PDF, as produced by
                      certificate_generator.generate_certificate()
    interview_id    : optional, used to build a descriptive filename

    Returns
    -------
    bool — True if the email was sent successfully, False otherwise.
    """
    if not pdf_bytes:
        logger.error('[email_service] send_certificate_email called with empty pdf_bytes.')
        return False

    filename = (
        'Certificate_%s.pdf' % interview_id
        if interview_id else 'Certificate_of_Completion.pdf'
    )

    subject = 'Your Certificate of Completion - ' + job_role
    html    = _certificate_email_html(candidate_name, job_role, overall_score)
    plain   = (
        'Hi %s,\n\n'
        'Congratulations on completing your AI-powered mock interview for the '
        '%s role! Your overall score was %.1f/10. '
        'Your certificate of completion is attached.\n\n'
        '-- The AI Interview Coach Team'
    ) % (candidate_name, job_role, overall_score)

    return send_email_with_attachment(
        to_email=to_email,
        subject=subject,
        html_body=html,
        attachments=[(pdf_bytes, filename)],
        plain_body=plain,
    )


# =============================================================================
# PUBLIC: SEND BOTH REPORT + CERTIFICATE IN ONE EMAIL
# =============================================================================

def send_report_and_certificate_email(
    to_email: str,
    candidate_name: str,
    job_role: str,
    overall_score: float,
    report_pdf_bytes: bytes,
    certificate_pdf_bytes: bytes,
    interview_id: Optional[int] = None,
) -> bool:
    """
    Send both the report and certificate PDFs as attachments on a single
    email, rather than two separate emails.

    Parameters mirror send_report_email / send_certificate_email; either
    PDF may be omitted (passed as None or empty bytes) to send just one
    attachment -- though in that case prefer calling the dedicated
    send_report_email() / send_certificate_email() function instead.

    Returns
    -------
    bool — True if the email was sent successfully, False otherwise.
    """
    attachments = []

    report_filename = (
        'Interview_Report_%s.pdf' % interview_id
        if interview_id else 'Interview_Report.pdf'
    )
    cert_filename = (
        'Certificate_%s.pdf' % interview_id
        if interview_id else 'Certificate_of_Completion.pdf'
    )

    if report_pdf_bytes:
        attachments.append((report_pdf_bytes, report_filename))
    if certificate_pdf_bytes:
        attachments.append((certificate_pdf_bytes, cert_filename))

    if not attachments:
        logger.error(
            '[email_service] send_report_and_certificate_email called '
            'with no PDF bytes for either attachment.'
        )
        return False

    subject = 'Your AI Interview Coach Results - ' + job_role
    html    = _combined_email_html(candidate_name, job_role, overall_score)
    plain   = (
        'Hi %s,\n\n'
        'Thank you for completing your AI-powered mock interview for the '
        '%s role. Your overall score was %.1f/10. '
        'Please find your report and/or certificate attached.\n\n'
        '-- The AI Interview Coach Team'
    ) % (candidate_name, job_role, overall_score)

    return send_email_with_attachment(
        to_email=to_email,
        subject=subject,
        html_body=html,
        attachments=attachments,
        plain_body=plain,
    )
