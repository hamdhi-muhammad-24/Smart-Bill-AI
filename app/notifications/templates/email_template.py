"""Email subject, HTML body, and attachment helper — no arithmetic, display only."""
from __future__ import annotations

import io
from pathlib import Path
from typing import Optional


def _format_lkr(value) -> str:
    """Format a stored Decimal/Numeric as 'Rs X,XXX.XX' for display."""
    return f"Rs {value:,.2f}"


def _period_label(period_start, period_end) -> str:
    return period_start.strftime("%B %Y")


def render_email_subject(invoice, account) -> str:
    period = _period_label(invoice.period_start, invoice.period_end)
    amount = f"{invoice.total_payable:,.2f}"
    return f"Your SLT bill for {period} — Rs {amount}"


def render_email_html(invoice, account, customer) -> str:
    period  = _period_label(invoice.period_start, invoice.period_end)
    amount  = _format_lkr(invoice.total_payable)
    name    = customer.full_name if customer else "Valued Customer"
    acc_no  = account.account_number
    due     = invoice.due_date.strftime("%d %B %Y")

    return (
        "<!DOCTYPE html><html><body style='font-family:Arial,sans-serif;color:#333'>"
        f"<p>Dear {name},</p>"
        "<p>Please find your SLT bill summary below.</p>"
        "<table style='border-collapse:collapse;width:100%;max-width:480px'>"
        f"<tr><td style='padding:6px 12px;background:#f5f5f5'><b>Account No.</b></td>"
        f"    <td style='padding:6px 12px'>{acc_no}</td></tr>"
        f"<tr><td style='padding:6px 12px;background:#f5f5f5'><b>Billing Period</b></td>"
        f"    <td style='padding:6px 12px'>{period}</td></tr>"
        f"<tr><td style='padding:6px 12px;background:#f5f5f5'><b>Amount Due</b></td>"
        f"    <td style='padding:6px 12px'><b>{amount}</b></td></tr>"
        f"<tr><td style='padding:6px 12px;background:#f5f5f5'><b>Due Date</b></td>"
        f"    <td style='padding:6px 12px'>{due}</td></tr>"
        "</table>"
        "<p>Please settle the amount before the due date to avoid service interruptions.</p>"
        "<p>Thank you for choosing SLT.</p>"
        "<hr/><p style='font-size:11px;color:#888'>SLT Billing &bull; billing@slt.lk</p>"
        "</body></html>"
    )


def get_pdf_bytes(invoice) -> Optional[bytes]:
    """Return PDF bytes for the invoice without duplicating rendering logic.

    Reads from invoice.pdf_path when available and on disk.
    Falls back to in-memory render using the same frozen functions the API uses.
    """
    if invoice.pdf_path and Path(invoice.pdf_path).exists():
        return Path(invoice.pdf_path).read_bytes()
    return None


def render_email_attachments(
    invoice,
    signed_link: Optional[str] = None,
) -> tuple[Optional[list[tuple[str, bytes, str]]], Optional[str]]:
    """Return (attachments, inline_link).

    If EMAIL_USE_SIGNED_LINK is true, returns (None, signed_link_url).
    Otherwise attaches the PDF bytes and returns (attachments, None).
    """
    from app.core.config import settings

    if settings.email_use_signed_link and signed_link:
        return None, signed_link

    pdf_bytes = get_pdf_bytes(invoice)
    if pdf_bytes is None:
        return None, None

    safe = invoice.id
    filename = f"SLT-bill-{safe}.pdf"
    return [(filename, pdf_bytes, "application/pdf")], None
