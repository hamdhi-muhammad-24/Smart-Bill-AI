from templates.nonvat_home.renderer import NonVATHomeRenderer
from templates.nonvat_home.parser import parse_nonvat_home

from templates.nonvat_enterprise.renderer import NonVATEnterpriseRenderer
from templates.nonvat_enterprise.parser import parse_nonvat_enterprise

from templates.product_label_grouping.renderer import ProductLabelGroupingRenderer
from templates.product_label_grouping.parser import parse_product_label_grouping

from templates.subscription_ref_grouping.renderer import SubscriptionRefGroupingRenderer
from templates.subscription_ref_grouping.parser import parse_subscription_ref_grouping

from templates.summary_statement.renderer import SummaryStatementRenderer
from templates.summary_statement.parser import parse_summary_statement

from templates.invoice_of_summary.renderer import InvoiceOfSummaryRenderer
from templates.invoice_of_summary.parser import parse_invoice_of_summary

from templates.vat_creditnote.renderer import VATCreditNoteRenderer
from templates.vat_creditnote.parser import parse_vat_creditnote

from templates.nonvat_creditnote.renderer import NonVATCreditNoteRenderer
from templates.nonvat_creditnote.parser import parse_nonvat_creditnote

from templates.usd_open_item.renderer import USDOpenItemRenderer
from templates.usd_open_item.parser import parse_usd_open_item

# New imports for VAT Enterprise
from templates.vat_enterprise.renderer import VATEnterpriseRenderer
from templates.vat_enterprise.parser import parse_vat_enterprise

# New imports for VAT Home
from templates.vat_home.renderer import VATHomeRenderer
from templates.vat_home.parser import parse_vat_home

# New imports for LOD
from .lod.renderer import LODRenderer
from .lod.parser import parse_lod

# New imports for VAT Confirmation
from .vat_confirmation.renderer import VATConfirmationRenderer
from .vat_confirmation.parser import parse_vat_confirmation

# New imports for Final Notice
from .final_notice.render import FinalNoticeRenderer
from .final_notice.parser import parse_final_notice

# New imports for Customer Letter Logo V1Print
from .customer_letter_logo_v1print.render import CustomerLetterRenderer
from .customer_letter_logo_v1print.parser import parse_customer_letter

TEMPLATE_REGISTRY = {
    "final_notice": {
        "name": "Final Notice",
        "description": "LTE Final Notice Demand Letter",
        "renderer": FinalNoticeRenderer,
        "parser": parse_final_notice,
        "ready": True,
    },
    "customer_letter_logo_v1print": {
        "name": "Customer Migration Letter",
        "description": "Customer Migration Notice (MSAN Copper to Fibre / 4G LTE)",
        "renderer": CustomerLetterRenderer,
        "parser": parse_customer_letter,
        "ready": True,
    },
    "customer_migration_letter": {
        "name": "Customer Migration Letter",
        "description": "Customer Migration Notice (MSAN Copper to Fibre / 4G LTE)",
        "renderer": CustomerLetterRenderer,
        "parser": parse_customer_letter,
        "ready": True,
    },
    "customer_letter": {
        "name": "Customer Migration Letter",
        "description": "Customer Migration Notice (MSAN Copper to Fibre / 4G LTE)",
        "renderer": CustomerLetterRenderer,
        "parser": parse_customer_letter,
        "ready": True,
    },
    "lod": {
        "name": "Letter of Demand & Termination",
        "description": "LOD Template with Certified Sinhala/Tamil Translation Notice",
        "renderer": LODRenderer,
        "parser": parse_lod,
        "ready": True,
    },
    "vat_confirmation": {
        "name": "VAT Number Confirmation",
        "description": "VAT Registration Verification Letter",
        "renderer": VATConfirmationRenderer,
        "parser": parse_vat_confirmation,
        "ready": True,
    },
    "nonvat_home": {
        "name": "NonVAT Home Invoice",
        "description": "Sheet 19 - Non-VAT, Home customer",
        "renderer": NonVATHomeRenderer,
        "parser": parse_nonvat_home,
        "ready": True,
    },
    "nonvat_enterprise": {
        "name": "NonVAT Enterprise Invoice",
        "description": "Sheet 19 - Non-VAT, Enterprise customer",
        "renderer": NonVATEnterpriseRenderer,
        "parser": parse_nonvat_enterprise,
        "ready": True,
    },
    "vat_enterprise": {
        "name": "VAT Enterprise Invoice",
        "description": "Sheet 18 - BILLSTYLE=1, BILLTYPE=1",
        "renderer": VATEnterpriseRenderer,
        "parser": parse_vat_enterprise,
        "ready": True,
    },
    "vat_home": {
        "name": "VAT Home Invoice",
        "description": "Sheet 18 - BILLSTYLE=1, BILLTYPE=1, Home customer",
        "renderer": VATHomeRenderer,
        "parser": parse_vat_home,
        "ready": True,
    },
    "product_label_grouping": {
        "name": "Product Label Level Grouping",
        "description": "Sheet 22 - BILLSTYLE=19",
        "renderer": ProductLabelGroupingRenderer,
        "parser": parse_product_label_grouping,
        "ready": True,
    },
    "subscription_ref_grouping": {
        "name": "Subscription Ref Level Grouping",
        "description": "Sheet 23 - BILLSTYLE=20",
        "renderer": SubscriptionRefGroupingRenderer,
        "parser": parse_subscription_ref_grouping,
        "ready": True,
    },
    "summary_statement": {
        "name": "Summary Statement",
        "description": "Sheet 7 - DOCTYPE=SUMMARYSTATEMENT",
        "renderer": SummaryStatementRenderer,
        "parser": parse_summary_statement,
        "ready": True,
    },
    "invoice_of_summary": {
        "name": "Invoice of Summary",
        "description": "BILLSTYLE=18 - PLACEHOLDER (GMF labels TBD)",
        "renderer": InvoiceOfSummaryRenderer,
        "parser": parse_invoice_of_summary,
        "ready": True,
    },
    "vat_creditnote": {
        "name": "VAT Credit Note",
        "description": "BILLSTYLE=6",
        "renderer": VATCreditNoteRenderer,
        "parser": parse_vat_creditnote,
        "ready": True,
    },
    "nonvat_creditnote": {
        "name": "NonVAT Credit Note",
        "description": "BILLSTYLE=16",
        "renderer": NonVATCreditNoteRenderer,
        "parser": parse_nonvat_creditnote,
        "ready": True,
    },
    "usd_open_item": {
        "name": "USD Open Item",
        "description": "BILLSTYLE=21",
        "renderer": USDOpenItemRenderer,
        "parser": parse_usd_open_item,
        "ready": True,
    },
}


def get_template_info(template_id):
    return TEMPLATE_REGISTRY.get(template_id)


def get_renderer(template_id):
    info = TEMPLATE_REGISTRY.get(template_id)
    if not info:
        raise ValueError(f"Unknown template: {template_id}")
    return info["renderer"]


def get_parser(template_id):
    info = TEMPLATE_REGISTRY.get(template_id)
    if not info:
        raise ValueError(f"Unknown template: {template_id}")
    return info["parser"]


def list_templates(only_ready=False):
    templates = []
    for tid, info in TEMPLATE_REGISTRY.items():
        if only_ready and not info.get("ready", False):
            continue
        templates.append({
            "id": tid,
            "name": info["name"],
            "description": info["description"],
            "ready": info.get("ready", False),
        })
    return templates