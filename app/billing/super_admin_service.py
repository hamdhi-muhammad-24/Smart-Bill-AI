"""
Super Admin GMF Test Validation Engine.
Reconciles GMF raw line items against GMF $CHARGES tag, and verifies
against generated PDF details and Total Charges for the Period.
Follows the official SLT Rule Set (Full Rule Set V7.02_03072026.xlsx).
"""
import os
import re
import sys
import json
import random
import logging
import tempfile
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

import pypdf
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import GmfUpload, GmfTestRun, GmfTestRunStatus

# SmartAI_Bill imports
_smartai_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../Models/SmartAI_Bill")
)
if _smartai_path not in sys.path:
    sys.path.insert(0, _smartai_path)

from core.template_identifier import identify_template
from core.gmf_splitter import split_gmf_documents
from templates.registry import get_parser, get_renderer

# ReportLab imports for PDF generation
from reportlab.lib.pagesizes import letter, landscape, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

logger = logging.getLogger(__name__)

# Excluded non-invoice template IDs and tokens per rule set & user instruction
EXCLUDED_TEMPLATES = {
    "lod",
    "vat_confirmation",
    "final_notice",
    "customer_letter_logo_v1print",
    "customer_migration_letter",
    "customer_letter",
}

EXCLUDED_FILENAME_TOKENS = [
    "lod", "letter of demand",
    "vat confirm", "vat customer",
    "final notice", "notice",
    "migration", "customer letter"
]


def is_eligible_invoice_file(filename: str, template_id: Optional[str] = None) -> bool:
    """Check if the GMF file is an invoice document (excluding LOD, letters, notices)."""
    fn_lower = filename.lower()
    if any(token in fn_lower for token in EXCLUDED_FILENAME_TOKENS):
        return False
    if template_id and template_id.lower() in EXCLUDED_TEMPLATES:
        return False
    return True


def to_decimal(val: Any) -> Optional[Decimal]:
    """Convert any number or string representation to Decimal with 2 decimal places."""
    if val is None or val == "":
        return None
    try:
        cleaned = str(val).replace(",", "").replace("- ", "-").replace(" ", "").strip()
        return Decimal(cleaned).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return None


def extract_gmf_line_items(data: Dict[str, Any], template_id: str) -> Tuple[List[Dict[str, Any]], Decimal, Optional[Decimal]]:
    """
    Calculates line items from the parsed GMF data structure according to the template rule set.
    Returns: (list_of_line_items, calculated_line_total, charges_tag_value)
    """
    items = []

    # 1. Product charges (Rentals, Initiation, Feature charges, Usage)
    def collect_prod_charges(prod_list):
        for prod in prod_list:
            prod_label = prod.get("label") or "Product"
            for charge in prod.get("charges", []):
                amt = to_decimal(charge.get("amount"))
                if amt is not None:
                    desc = charge.get("description") or prod_label
                    items.append({
                        "section": "Charges",
                        "description": f"{prod_label} - {desc}".strip(" -"),
                        "amount": amt,
                    })
            if prod.get("children"):
                collect_prod_charges(prod["children"])

    collect_prod_charges(data.get("product_labels", []))

    # For subscription_refs (e.g. Sheet 23 Subscription Ref Level Grouping)
    for sref in data.get("subscription_refs", []):
        ref_name = sref.get("ref") or sref.get("detail_name") or "Sub"
        detail_name = sref.get("detail_name") or ref_name
        has_subtotals = False
        if sref.get("recurring_subtotal"):
            items.append({
                "section": "Subscription Charges",
                "description": f"{detail_name} Recurring Subtotal",
                "amount": to_decimal(sref["recurring_subtotal"]),
            })
            has_subtotals = True
        if sref.get("oneoff_subtotal"):
            items.append({
                "section": "Subscription Charges",
                "description": f"{detail_name} One-off Subtotal",
                "amount": to_decimal(sref["oneoff_subtotal"]),
            })
            has_subtotals = True

        if not has_subtotals:
            for prod in sref.get("products", []):
                plabel = prod.get("label") or ref_name
                for charge in prod.get("charges", []):
                    amt = to_decimal(charge.get("amount"))
                    if amt is not None and amt != Decimal("0.00"):
                        items.append({
                            "section": "Subscription Charges",
                            "description": f"{plabel} - {charge.get('description', '')}".strip(" -"),
                            "amount": amt,
                        })

    # For charge_blocks (e.g. USD Open Item)
    for b in data.get("charge_blocks", []):
        blabel = b.get("label") or "Block"
        for c in b.get("charges", []):
            amt = to_decimal(c.get("amount"))
            if amt is not None:
                items.append({
                    "section": "Charges",
                    "description": f"{blabel} - {c.get('description', '')}".strip(" -"),
                    "amount": amt,
                })
        for prod in b.get("product_labels", []):
            plabel = prod.get("label") or blabel
            for c in prod.get("charges", []):
                amt = to_decimal(c.get("amount"))
                if amt is not None:
                    items.append({
                        "section": "Charges",
                        "description": f"{plabel} - {c.get('description', '')}".strip(" -"),
                        "amount": amt,
                    })
        for sub in b.get("sub_blocks", []):
            slabel = sub.get("label") or blabel
            for c in sub.get("charges", []):
                amt = to_decimal(c.get("amount"))
                if amt is not None:
                    items.append({
                        "section": "Charges",
                        "description": f"{slabel} - {c.get('description', '')}".strip(" -"),
                        "amount": amt,
                    })

    # For charge_groups (when not invoice_of_summary)
    if template_id != "invoice_of_summary":
        for cg in data.get("charge_groups", []):
            ref_name = cg.get("ref") or "Group"
            for prod in cg.get("products", []):
                plabel = prod.get("label") or ref_name
                for c in prod.get("charges", []):
                    amt = to_decimal(c.get("amount"))
                    if amt is not None:
                        items.append({
                            "section": "Charges",
                            "description": f"{plabel} - {c.get('description', '')}".strip(" -"),
                            "amount": amt,
                        })

    # For unlabeled_charges
    for c in data.get("unlabeled_charges", []):
        amt = to_decimal(c.get("amount"))
        if amt is not None:
            items.append({
                "section": "Charges",
                "description": c.get("description") or "Unlabeled Charge",
                "amount": amt,
            })

    # For subscription ref grouping or custom groupings
    for sub in data.get("subscriptions", []):
        sub_ref = sub.get("subscription_ref") or "Sub"
        for charge in sub.get("charges", []):
            amt = to_decimal(charge.get("amount"))
            if amt is not None:
                items.append({
                    "section": "Subscription Charges",
                    "description": f"{sub_ref} - {charge.get('description', '')}".strip(" -"),
                    "amount": amt,
                })

    # For summary statement accounts
    for a in data.get("accounts", []):
        amt = to_decimal(a.get("gross_total") or a.get("net_amount") or a.get("amount") or a.get("total") or a.get("charges"))
        if amt is not None:
            items.append({
                "section": "Account Total",
                "description": a.get("account_no") or "Account",
                "amount": amt,
            })

    if template_id == "invoice_of_summary":
        rental = to_decimal(data.get("rental_subtotal", 0))
        usage = to_decimal(data.get("usage_subtotal", 0))
        if rental:
            items.append({"section": "Rental Subtotal", "description": "Subtotal Rental and Other Charges", "amount": rental})
        if usage:
            items.append({"section": "Usage Subtotal", "description": "Subtotal Usage charges", "amount": usage})
        for d in (data.get("discounts") or data.get("top_level_discounts") or []):
            amt = to_decimal(d.get("amount"))
            if amt:
                items.append({"section": "Discounts", "description": d.get("description") or "Discount", "amount": amt if amt < 0 else -amt})
        adj = to_decimal(data.get("adjustments_subtotal", 0))
        if adj:
            items.append({"section": "Adjustments", "description": "Subtotal Adjustment charges", "amount": adj})
    else:
        # For USD Open Item / Credit Notes / Other template lines
        for line in data.get("lines", []) or data.get("charges", []) or data.get("open_items", []):
            if isinstance(line, dict):
                amt = to_decimal(line.get("amount") or line.get("charge"))
                if amt is not None:
                    items.append({
                        "section": "Charges",
                        "description": line.get("description") or line.get("item_name") or "Charge Item",
                        "amount": amt,
                    })

        # 2. Adjustments (positive or negative)
        for adj in data.get("adjustments", []):
            amt = to_decimal(adj.get("amount"))
            if amt is not None:
                items.append({
                    "section": "Adjustments",
                    "description": adj.get("description") or "Adjustment",
                    "amount": amt,
                })

        # 3. Top level discounts (discounts reduce total -> negative amount)
        all_discs = data.get("top_level_discounts") or data.get("discounts") or []
        for disc in all_discs:
            amt = to_decimal(disc.get("amount"))
            if amt is not None:
                disc_amt = -abs(amt) if amt > 0 else amt
                items.append({
                    "section": "Discounts",
                    "description": disc.get("description") or "Discount",
                    "amount": disc_amt,
                })

    # 4. Taxes & Levies
    # Per Rule Set Sheet 18 & 19: Non-VAT customers print consolidated "Taxes & Levies".
    # VAT customers (show_vat_lines=True or Credit Note) print itemized tax components.
    show_vat = data.get("show_vat_lines", False)
    taxes = (
        data.get("taxes")
        or data.get("tax_items")
        or data.get("tax_rows")
        or data.get("taxes_levies")
        or []
    )
    if (show_vat or "creditnote" in template_id.lower()) and taxes:
        for tax in taxes:
            amt = to_decimal(tax.get("amount"))
            if amt is not None and amt != Decimal("0.00"):
                items.append({
                    "section": "Taxes",
                    "description": tax.get("name") or tax.get("description") or "Tax / Levy",
                    "amount": amt,
                })
    elif taxes and not data.get("taxes_total") and not data.get("inv_total_tax"):
        for tax in taxes:
            amt = to_decimal(tax.get("amount"))
            if amt is not None and amt != Decimal("0.00"):
                items.append({
                    "section": "Taxes",
                    "description": tax.get("name") or tax.get("description") or "Tax / Levy",
                    "amount": amt,
                })
    else:
        tax_tot = to_decimal(data.get("taxes_total") or data.get("inv_total_tax"))
        if tax_tot is not None and tax_tot != Decimal("0.00"):
            items.append({
                "section": "Taxes",
                "description": "Taxes & Levies",
                "amount": tax_tot,
            })

    # Sum all extracted line items
    calculated_total = sum((item["amount"] for item in items), Decimal("0.00")).quantize(Decimal("0.01"))

    # Read official GMF charges tag accurately preserving 0.00 values
    candidate_tag_keys = [
        "charges_period", "total_charges", "charge_for_period",
        "total_gross", "charges", "total_amount", "credit_amount", "inv_total_payable"
    ]
    charges_tag = None
    for k in candidate_tag_keys:
        if k in data and data[k] is not None and str(data[k]).strip() != "":
            parsed = to_decimal(data[k])
            if parsed is not None:
                charges_tag = parsed
                break

    return items, calculated_total, charges_tag


def extract_pdf_data(pdf_path: str) -> Tuple[Optional[Decimal], List[Dict[str, Any]], Decimal]:
    """
    Extracts Total Charges for the Period and individual Details of Charges line items from the rendered PDF
    using high-precision PDF coordinate analysis and regex fallback.
    Returns: (pdf_total_charges, pdf_details_items, pdf_details_total)
    """
    if not os.path.exists(pdf_path):
        return None, [], Decimal("0.00")

    reader = pypdf.PdfReader(pdf_path)
    if not reader.pages:
        return None, [], Decimal("0.00")

    all_elements = []
    def visitor(text, cm, tm, fontDict, fontSize):
        t = text.strip()
        if t:
            all_elements.append((tm[4], tm[5], t))

    # Inspect Page 1 elements with coordinates
    reader.pages[0].extract_text(visitor_text=visitor)

    tc_y = None
    pdf_total_charges = None

    # 1. Locate the total charges label Y coordinate
    for x, y, t in all_elements:
        t_low = t.lower()
        if "total charges for the period" in t_low or "charge of the period" in t_low:
            tc_y = y
            break

    pdf_details_items = []
    if tc_y is not None:
        # The Total Charges amount is rendered on the same horizontal line (+- 8pt) in the amount column (x > 430)
        for x, y, t in all_elements:
            if abs(y - tc_y) <= 8 and x > 430:
                val = to_decimal(t)
                if val is not None:
                    pdf_total_charges = val
                    break

        # The individual charge items are rendered strictly in the amount column (x > 440) above tc_y
        for x, y, t in all_elements:
            if y > tc_y and y <= 500 and x > 440:
                val = to_decimal(t)
                if val is not None:
                    # Find description rendered near the same Y
                    desc = "Charge Item"
                    for dx, dy, dt in all_elements:
                        if abs(dy - y) <= 5 and dx < 320:
                            desc = dt
                            break
                    pdf_details_items.append({
                        "description": desc,
                        "amount": val,
                    })

    # Fallback to full-text regex if coordinate check didn't catch it
    full_text = None
    if pdf_total_charges is None:
        full_text = "\n".join([page.extract_text() or "" for page in reader.pages])
        tc_match = re.search(r"Total\s+Charges\s+for\s+the\s+Period\s*\n\s*(-?[0-9,]+\.\d{2})", full_text, re.IGNORECASE)
        if not tc_match:
            tc_match = re.search(r"Total\s+Charges\s+for\s+the\s+Period[^\d\n\-]*(-?[0-9,]+\.\d{2})", full_text, re.IGNORECASE)
        if not tc_match:
            tc_match = re.search(r"Charge\s+of\s+the\s+period\s*\n?\s*(-?[0-9,]+\.\d{2})", full_text, re.IGNORECASE)
        if not tc_match:
            # Summary Statement total row on last page
            tc_match = re.search(r"Total\s*\n\s*[\d,.]+\s*\n\s*[\d,.]+\s*\n\s*([\d,]+\.\d{2})", full_text, re.IGNORECASE)
        if not tc_match:
            tc_match = re.search(r"Total\s+Payable\s*\n\s*(-?[0-9,]+\.\d{2})", full_text, re.IGNORECASE)
        pdf_total_charges = to_decimal(tc_match.group(1)) if tc_match else None

    # Fallback extraction of details lines for templates with different table columns (e.g. Credit Notes)
    if not pdf_details_items and tc_y is not None:
        for x, y, t in all_elements:
            if y > tc_y and y <= 500 and x > 380:
                val = to_decimal(t)
                if val is not None and val != pdf_total_charges:
                    pdf_details_items.append({"description": "Credit / Adjustment Line", "amount": val})

    pdf_details_total = sum((item["amount"] for item in pdf_details_items), Decimal("0.00")).quantize(Decimal("0.01"))
    if not pdf_details_items and pdf_total_charges is not None:
        pdf_details_total = pdf_total_charges

    return pdf_total_charges, pdf_details_items, pdf_details_total


def validate_single_document(
    doc_path: str,
    source_filename: str,
    doc_index: int = 1,
) -> Dict[str, Any]:
    """
    Performs full 4-point validation on an individual invoice document:
    1. GMF calculated line total (from raw tags per rule set)
    2. GMF $CHARGES tag
    3. PDF rendered Total Charges for the Period
    4. PDF rendered Details of Charges line items sum
    """
    ident = identify_template(doc_path, original_filename=source_filename)
    template_id = ident.template_id or "unknown"

    result: Dict[str, Any] = {
        "filename": source_filename,
        "doc_index": doc_index,
        "template_id": template_id,
        "account_number": "N/A",
        "invoice_number": "N/A",
        "gmf_calculated_total": Decimal("0.00"),
        "gmf_charges_tag": None,
        "pdf_total_charges": None,
        "pdf_details_total": Decimal("0.00"),
        "gmf_line_items_count": 0,
        "pdf_line_items_count": 0,
        "status": "FAIL",
        "mismatch_details": "",
        "details_summary": [],
    }

    if not ident.is_supported or template_id in EXCLUDED_TEMPLATES:
        result["mismatch_details"] = f"Unsupported or excluded non-invoice template ({template_id})"
        return result

    try:
        parser = get_parser(template_id)
        RendererClass = get_renderer(template_id)
    except Exception as e:
        result["mismatch_details"] = f"Failed loading template parser/renderer: {str(e)}"
        return result

    try:
        data = parser(doc_path)
        if isinstance(data, list):
            data = data[0] if data else {}
    except Exception as e:
        result["mismatch_details"] = f"GMF parse error: {str(e)}"
        return result

    result["account_number"] = str(data.get("account_number") or data.get("customer_ref_no") or "N/A").strip()
    result["invoice_number"] = str(data.get("invoice_number") or data.get("bill_ref") or "N/A").strip()

    # Step 1: Extract and calculate line items from raw GMF per rule set
    gmf_items, gmf_calculated_total, gmf_charges_tag = extract_gmf_line_items(data, template_id)
    result["gmf_calculated_total"] = gmf_calculated_total
    result["gmf_charges_tag"] = gmf_charges_tag
    result["gmf_line_items_count"] = len(gmf_items)
    result["details_summary"] = [
        {"desc": it["description"], "amount": float(it["amount"])}
        for it in gmf_items[:15]
    ]

    # Step 2: Render PDF in a temporary folder
    with tempfile.TemporaryDirectory(prefix="super_admin_test_") as tmp_dir:
        temp_pdf = os.path.join(tmp_dir, f"test_{doc_index}.pdf")
        try:
            # Create lightweight copy for fast test rendering:
            # Page 1 charges and totals are fully rendered; usage call-history tables limited to 1
            render_data = dict(data)
            if "usage_sections" in render_data and isinstance(render_data["usage_sections"], list):
                render_data["usage_sections"] = render_data["usage_sections"][:1]

            renderer = RendererClass()
            renderer.render(render_data)
            renderer.save(temp_pdf)
        except Exception as e:
            result["mismatch_details"] = f"PDF rendering failed: {str(e)}"
            return result

        # Step 3: Extract from generated PDF
        pdf_total_charges, pdf_items, pdf_details_total = extract_pdf_data(temp_pdf)
        result["pdf_total_charges"] = pdf_total_charges
        result["pdf_details_total"] = pdf_details_total
        result["pdf_line_items_count"] = len(pdf_items)

    # Step 4: Triple/Quadruple Reconciliation Check
    mismatches = []

    if gmf_charges_tag is None:
        mismatches.append("Missing $CHARGES tag in GMF")
    else:
        # Check 1: GMF calculated items sum == GMF $CHARGES tag
        diff_gmf = (gmf_calculated_total - gmf_charges_tag).quantize(Decimal("0.01"))
        if diff_gmf != Decimal("0.00"):
            mismatches.append(f"GMF Line Total (Rs {gmf_calculated_total:,.2f}) != GMF $CHARGES tag (Rs {gmf_charges_tag:,.2f}) [Diff: Rs {diff_gmf:+,.2f}]")

    if pdf_total_charges is None:
        mismatches.append("Missing 'Total Charges for the Period' in generated PDF")
    elif gmf_charges_tag is not None:
        # Check 2: GMF $CHARGES tag == PDF Total Charges
        diff_pdf = (pdf_total_charges - gmf_charges_tag).quantize(Decimal("0.01"))
        if diff_pdf != Decimal("0.00"):
            mismatches.append(f"PDF Total Charges (Rs {pdf_total_charges:,.2f}) != GMF $CHARGES tag (Rs {gmf_charges_tag:,.2f}) [Diff: Rs {diff_pdf:+,.2f}]")

    # Check 3: If PDF line items were extracted, check if their sum matches the total charges
    if pdf_items and pdf_total_charges is not None:
        diff_items = (pdf_details_total - pdf_total_charges).quantize(Decimal("0.01"))
        if diff_items != Decimal("0.00"):
            mismatches.append(f"PDF Details Line Sum (Rs {pdf_details_total:,.2f}) != PDF Total (Rs {pdf_total_charges:,.2f}) [Diff: Rs {diff_items:+,.2f}]")
            # If line sum differed, identify which GMF line items were missing in the rendered PDF
            if gmf_items:
                gmf_amounts = [it["amount"] for it in gmf_items if it["amount"] != Decimal("0.00")]
                pdf_amounts = [it["amount"] for it in pdf_items if it["amount"] != Decimal("0.00")]
                missing_amounts = []
                for a in gmf_amounts:
                    if a in pdf_amounts:
                        pdf_amounts.remove(a)
                    else:
                        missing_amounts.append(a)
                if missing_amounts:
                    missing_str = ", ".join([f"Rs {m:,.2f}" for m in missing_amounts[:3]])
                    mismatches.append(f"Line items missing in PDF: {missing_str}")

    if not mismatches:
        result["status"] = "PASS"
        result["mismatch_details"] = "All 4 validation checks passed: GMF lines, $CHARGES tag, and PDF totals match exactly."
    else:
        result["status"] = "FAIL"
        result["mismatch_details"] = " | ".join(mismatches)

    return result


def sample_gmf_uploads(db: Session, max_files: int = 100) -> List[Tuple[int, str, str]]:
    """
    Selects up to 100 random invoice GMF files from all uploads in the system.
    Excludes non-invoice templates (LOD, letters, notices).
    Returns list of (upload_id, filename, file_path).
    """
    all_uploads = db.query(GmfUpload).all()
    eligible = []
    seen_paths = set()

    for u in all_uploads:
        if not u.file_path or not os.path.exists(u.file_path):
            continue
        if u.file_path in seen_paths:
            continue
        if is_eligible_invoice_file(u.filename, u.template_detected):
            eligible.append((u.id, u.filename, u.file_path))
            seen_paths.add(u.file_path)

    if len(eligible) <= max_files:
        return eligible

    return random.sample(eligible, max_files)


def render_single_invoice_pdf(db: Session, filename: str, doc_index: int = 1) -> Optional[bytes]:
    """
    Renders and returns the binary PDF bytes of a specific invoice document from a tested GMF.
    Allows Super Admin to view/download the generated PDF directly in the browser.
    """
    upload = db.query(GmfUpload).filter(GmfUpload.filename == filename).first()
    file_path = upload.file_path if upload and upload.file_path and os.path.exists(upload.file_path) else None

    if not file_path:
        # Check standard storage paths
        for base in ["queue/pending", "local_gmf_uploads", "local_gmf_uploads/Test_GMFs", "local_gmf_uploads/Cycle_1"]:
            candidate = os.path.abspath(os.path.join(base, filename))
            if os.path.exists(candidate):
                file_path = candidate
                break

    if not file_path:
        return None

    try:
        doc_paths = split_gmf_documents(file_path, original_filename=filename)
        if not doc_paths:
            doc_paths = [file_path]

        target_path = doc_paths[doc_index - 1] if 0 <= doc_index - 1 < len(doc_paths) else doc_paths[0]
        ident = identify_template(target_path, original_filename=filename)
        if not ident.is_supported:
            return None

        parser = get_parser(ident.template_id)
        RendererClass = get_renderer(ident.template_id)

        data = parser(target_path)
        if isinstance(data, list):
            data = data[0] if data else {}

        with tempfile.TemporaryDirectory(prefix="view_invoice_pdf_") as tmp_dir:
            temp_pdf = os.path.join(tmp_dir, f"{filename}_doc_{doc_index}.pdf")
            renderer = RendererClass()
            renderer.render(data)
            renderer.save(temp_pdf)

            with open(temp_pdf, "rb") as f:
                return f.read()
    except Exception as e:
        logger.error(f"Failed to render single invoice PDF for {filename} (Doc #{doc_index}): {e}", exc_info=True)
        return None


class NumberedCanvas(canvas.Canvas):
    """Canvas that automatically counts total pages and draws running footers."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_footer(num_pages)
            super().showPage()
        super().save()

    def draw_footer(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))
        footer_text = f"SRI LANKA TELECOM PLC  |  CONFIDENTIAL SUPER ADMIN AUDIT REPORT  |  Page {self._pageNumber} of {page_count}"
        self.drawCentredString(A4[1] / 2.0, 20, footer_text)
        self.restoreState()


def generate_validation_pdf_report(
    test_run: GmfTestRun,
    results: List[Dict[str, Any]],
    output_pdf_path: str,
) -> str:
    """
    Generates a publication-grade SLT-MOBITEL enterprise PDF test report.
    Landscape A4 format with clear tables and highlighted red failures.
    """
    os.makedirs(os.path.dirname(output_pdf_path), exist_ok=True)
    doc = SimpleDocTemplate(
        output_pdf_path,
        pagesize=landscape(A4),
        leftMargin=25,
        rightMargin=25,
        topMargin=25,
        bottomMargin=35,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0066b3"),
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#475569"),
    )
    meta_label_style = ParagraphStyle(
        "MetaLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#1e293b"),
    )
    meta_val_style = ParagraphStyle(
        "MetaVal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#334155"),
    )
    cell_style = ParagraphStyle(
        "CellNormal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#0f172a"),
    )
    cell_fail_style = ParagraphStyle(
        "CellFail",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#dc2626"),
    )
    cell_pass_style = ParagraphStyle(
        "CellPass",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#16a34a"),
    )

    story = []

    # Header section
    story.append(Paragraph("SRI LANKA TELECOM PLC", subtitle_style))
    story.append(Paragraph("Super Admin GMF Test & Accuracy Audit Report", title_style))
    story.append(Paragraph("Automated triple-reconciliation of raw GMF line items against $CHARGES tags and rendered PDF invoice output.", subtitle_style))
    story.append(Spacer(1, 10))

    # Metadata & KPI summary box
    pass_rate = (test_run.passed_count / max(test_run.total_invoices_tested, 1)) * 100
    status_text = "PASSED (100%)" if test_run.failed_count == 0 else f"FAILED ({test_run.failed_count} Discrepancies Detected)"
    status_color = "#16a34a" if test_run.failed_count == 0 else "#dc2626"

    kpi_data = [
        [
            Paragraph("<b>Test Run ID:</b>", meta_label_style),
            Paragraph(f"#{test_run.id}", meta_val_style),
            Paragraph("<b>Triggered By:</b>", meta_label_style),
            Paragraph(test_run.triggered_by, meta_val_style),
            Paragraph("<b>Execution Time:</b>", meta_label_style),
            Paragraph(test_run.started_at.strftime("%Y-%m-%d %H:%M:%S") if test_run.started_at else "N/A", meta_val_style),
        ],
        [
            Paragraph("<b>Sampled Files:</b>", meta_label_style),
            Paragraph(str(test_run.total_files_sampled), meta_val_style),
            Paragraph("<b>Tested Invoices:</b>", meta_label_style),
            Paragraph(str(test_run.total_invoices_tested), meta_val_style),
            Paragraph("<b>Overall Status:</b>", meta_label_style),
            Paragraph(f"<font color='{status_color}'><b>{status_text}</b></font> (Pass Rate: {pass_rate:.1f}%)", meta_val_style),
        ]
    ]
    kpi_table = Table(kpi_data, colWidths=[90, 140, 90, 180, 90, 190])
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 12))

    # Main results table
    table_headers = [
        Paragraph("<b>#</b>", meta_label_style),
        Paragraph("<b>GMF Filename</b>", meta_label_style),
        Paragraph("<b>Account No</b>", meta_label_style),
        Paragraph("<b>Invoice No</b>", meta_label_style),
        Paragraph("<b>Template</b>", meta_label_style),
        Paragraph("<b>GMF Lines Total</b>", meta_label_style),
        Paragraph("<b>GMF $CHARGES</b>", meta_label_style),
        Paragraph("<b>PDF Extracted</b>", meta_label_style),
        Paragraph("<b>Status</b>", meta_label_style),
        Paragraph("<b>Reconciliation & Mismatch Details</b>", meta_label_style),
    ]
    table_data = [table_headers]

    for idx, r in enumerate(results, start=1):
        is_pass = r["status"] == "PASS"
        status_para = Paragraph("PASS", cell_pass_style) if is_pass else Paragraph("FAIL", cell_fail_style)
        mismatch_para = Paragraph(r["mismatch_details"], cell_style if is_pass else cell_fail_style)

        row = [
            Paragraph(str(idx), cell_style),
            Paragraph(r["filename"], cell_style),
            Paragraph(r["account_number"], cell_style),
            Paragraph(r["invoice_number"], cell_style),
            Paragraph(r["template_id"], cell_style),
            Paragraph(f"Rs {r['gmf_calculated_total']:,.2f}", cell_style),
            Paragraph(f"Rs {r['gmf_charges_tag']:,.2f}" if r["gmf_charges_tag"] is not None else "N/A", cell_style),
            Paragraph(f"Rs {r['pdf_total_charges']:,.2f}" if r["pdf_total_charges"] is not None else "N/A", cell_style),
            status_para,
            mismatch_para,
        ]
        table_data.append(row)

    # Calculate column widths to fit landscape A4 (approx 790pt printable width)
    # [idx, file, acc, inv, tpl, gmf_calc, gmf_tag, pdf_tot, status, details]
    col_widths = [24, 120, 75, 80, 80, 70, 70, 70, 40, 161]
    res_table = Table(table_data, colWidths=col_widths, repeatRows=1)

    t_style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0066b3")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    # Header text color to white
    for col_idx in range(len(col_widths)):
        t_style.append(("TEXTCOLOR", (col_idx, 0), (col_idx, 0), colors.white))

    # Alternate row colors and highlight failures in red
    for r_idx, r in enumerate(results, start=1):
        if r["status"] == "FAIL":
            t_style.append(("BACKGROUND", (0, r_idx), (-1, r_idx), colors.HexColor("#fef2f2")))
        elif r_idx % 2 == 0:
            t_style.append(("BACKGROUND", (0, r_idx), (-1, r_idx), colors.HexColor("#f8fafc")))

    res_table.setStyle(TableStyle(t_style))
    story.append(res_table)

    # Build document with custom running canvas
    doc.build(story, canvasmaker=NumberedCanvas)
    return output_pdf_path


def run_gmf_validation_test_suite(
    db: Session,
    triggered_by: str,
    max_files: int = 100,
) -> GmfTestRun:
    """
    Orchestrates the entire Super Admin GMF Test execution:
    1. Selects up to 100 random GMF files (excluding non-invoices).
    2. Runs 4-point validation for each document block (handles multi-doc).
    3. Generates the PDF Test Report.
    4. Records results in DB and returns the completed GmfTestRun.
    """
    test_run = GmfTestRun(
        status=GmfTestRunStatus.RUNNING,
        triggered_by=triggered_by,
        started_at=datetime.utcnow(),
    )
    db.add(test_run)
    db.commit()
    db.refresh(test_run)

    sampled = sample_gmf_uploads(db, max_files=max_files)
    test_run.total_files_sampled = len(sampled)
    db.commit()

    all_results = []
    passed = 0
    failed = 0

    for upload_id, filename, file_path in sampled:
        try:
            # Handle multi-doc splitting
            doc_paths = split_gmf_documents(file_path, original_filename=filename)
            if not doc_paths:
                doc_paths = [file_path]

            with tempfile.TemporaryDirectory(prefix="gmf_split_docs_") as split_dir:
                for doc_idx, dpath in enumerate(doc_paths, start=1):
                    doc_res = validate_single_document(
                        doc_path=dpath,
                        source_filename=filename,
                        doc_index=doc_idx,
                    )
                    # Convert Decimals to float/str for JSON serialization
                    doc_res_json = dict(doc_res)
                    doc_res_json["gmf_calculated_total"] = float(doc_res["gmf_calculated_total"])
                    doc_res_json["gmf_charges_tag"] = float(doc_res["gmf_charges_tag"]) if doc_res["gmf_charges_tag"] is not None else None
                    doc_res_json["pdf_total_charges"] = float(doc_res["pdf_total_charges"]) if doc_res["pdf_total_charges"] is not None else None
                    doc_res_json["pdf_details_total"] = float(doc_res["pdf_details_total"])

                    all_results.append(doc_res_json)
                    if doc_res["status"] == "PASS":
                        passed += 1
                    else:
                        failed += 1
        except Exception as e:
            logger.error(f"Error validating file {filename}: {e}", exc_info=True)
            all_results.append({
                "filename": filename,
                "doc_index": 1,
                "template_id": "error",
                "account_number": "N/A",
                "invoice_number": "N/A",
                "gmf_calculated_total": 0.0,
                "gmf_charges_tag": None,
                "pdf_total_charges": None,
                "pdf_details_total": 0.0,
                "gmf_line_items_count": 0,
                "pdf_line_items_count": 0,
                "status": "FAIL",
                "mismatch_details": f"File processing exception: {str(e)}",
                "details_summary": [],
            })
            failed += 1

    test_run.total_invoices_tested = len(all_results)
    test_run.passed_count = passed
    test_run.failed_count = failed
    test_run.results_json = json.dumps(all_results)
    test_run.finished_at = datetime.utcnow()
    test_run.status = GmfTestRunStatus.COMPLETED

    # Generate the official PDF report
    reports_dir = os.path.abspath("./output/super_admin_reports")
    report_filename = f"GMF_Validation_Report_Run_{test_run.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    report_path = os.path.join(reports_dir, report_filename)

    # Convert results back to Decimals for ReportLab formatting
    report_results = []
    for r in all_results:
        rr = dict(r)
        rr["gmf_calculated_total"] = Decimal(str(r["gmf_calculated_total"]))
        rr["gmf_charges_tag"] = Decimal(str(r["gmf_charges_tag"])) if r["gmf_charges_tag"] is not None else None
        rr["pdf_total_charges"] = Decimal(str(r["pdf_total_charges"])) if r["pdf_total_charges"] is not None else None
        report_results.append(rr)

    generate_validation_pdf_report(test_run, report_results, report_path)
    test_run.report_pdf_path = report_path
    db.commit()
    db.refresh(test_run)

    return test_run


def execute_system_reset(db: Session) -> Dict[str, Any]:
    """
    Completely wipes all transaction history, uploaded GMFs, generated PDFs,
    billing runs, and Super Admin test records.
    Retains Users, Base Templates, and System Settings intact.
    """
    from app.db.models import (
        NotificationEvent,
        BillingRunItem,
        BillingRunFailure,
        Invoice,
        GmfUpload,
        BillingRun,
        EnvelopeArtwork,
        EnvelopeHistory,
        TemplateHistory,
        InvoiceTemplate,
        TemplateApprovalStatus,
        GmfTestRun,
    )
    from pathlib import Path
    import time

    def _force_del(path_item: Path) -> int:
        if not path_item.exists():
            return 0
        deleted_count = 0
        for _ in range(5):
            try:
                if path_item.is_file():
                    os.chmod(path_item, 0o777)
                    path_item.unlink()
                    return 1
                elif path_item.is_dir():
                    for root, dirs, files in os.walk(path_item, topdown=False):
                        for name in files:
                            p = Path(root) / name
                            try:
                                os.chmod(p, 0o777)
                                p.unlink()
                                deleted_count += 1
                            except Exception:
                                pass
                        for name in dirs:
                            p = Path(root) / name
                            try:
                                os.chmod(p, 0o777)
                                p.rmdir()
                            except Exception:
                                pass
                    try:
                        os.chmod(path_item, 0o777)
                        path_item.rmdir()
                    except Exception:
                        pass
                    return deleted_count
            except Exception:
                time.sleep(0.2)
        return deleted_count

    counts = {}
    try:
        counts["NotificationEvents"] = db.query(NotificationEvent).delete()
        counts["BillingRunItems"] = db.query(BillingRunItem).delete()
        counts["BillingRunFailures"] = db.query(BillingRunFailure).delete()
        counts["Invoices"] = db.query(Invoice).delete()
        counts["GmfUploads"] = db.query(GmfUpload).delete()
        counts["BillingRuns"] = db.query(BillingRun).delete()
        counts["EnvelopeArtworks"] = db.query(EnvelopeArtwork).delete()
        counts["EnvelopeHistory"] = db.query(EnvelopeHistory).delete()
        counts["TemplateHistory"] = db.query(TemplateHistory).delete()
        counts["GmfTestRuns"] = db.query(GmfTestRun).delete()

        db.query(InvoiceTemplate).update({"approval_status": TemplateApprovalStatus.PENDING})
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database reset error: {e}", exc_info=True)
        raise e

    # Clear physical files
    legacy_gdrive = Path(r"G:\My Drive\SLT_GMF_Uploads")
    paths_to_clean = [
        settings.queue_incoming_dir,
        settings.queue_pending_dir,
        Path("./queue/completed_temp"),
        Path("./output"),
        Path("./output/previews"),
        Path("./output/super_admin_reports"),
        Path("./uploads"),
        Path("./uploads/envelope_artworks"),
        settings.gmf_drive_path / "Test_GMFs",
        settings.gmf_drive_path / "Cycle_1",
        settings.gmf_drive_path / "Cycle_2",
        settings.gmf_drive_path / "Cycle_3",
        settings.gmf_drive_path / "Cycle_4",
        settings.gmf_drive_path / "LOD",
        settings.gmf_drive_path / "VAT_Confirmation",
        settings.gmf_drive_path / "Staged",
        settings.gmf_drive_path / "Processed",
        settings.gmf_drive_path / "Failed",
        settings.gmf_drive_path / "Output",
        Path("./Models/SmartAI_Bill/local_gmf_uploads/Output"),
        Path("./Models/SmartAI_Bill/local_gmf_uploads/Processed"),
        Path("./Models/SmartAI_Bill/local_gmf_uploads/Staged"),
        Path("./Models/SmartAI_Bill/local_gmf_uploads/Failed"),
        Path("./Models/SmartAI_Bill/local_gmf_uploads/Test_GMFs"),
        Path("./Models/SmartAI_Bill/local_gmf_uploads/LOD"),
        Path("./Models/SmartAI_Bill/local_gmf_uploads/VAT_Confirmation"),
    ]
    if legacy_gdrive.exists():
        for sub in ["Test_GMFs", "Cycle_1", "Cycle_2", "Cycle_3", "Cycle_4", "Staged", "Processed", "Failed", "Output"]:
            paths_to_clean.append(legacy_gdrive / sub)

    files_deleted = 0
    for p in paths_to_clean:
        if p.exists():
            for item in list(p.iterdir()):
                files_deleted += _force_del(item)

    return {
        "success": True,
        "message": "System wiped clean of transaction history, GMF test runs, uploaded GMFs, and generated PDFs.",
        "deleted_counts": counts,
        "files_deleted": files_deleted,
    }
