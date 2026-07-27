import os
import tempfile
from playwright.sync_api import sync_playwright
try:
    import fitz
except ImportError:
    fitz = None
from pypdf import PdfReader, PdfWriter

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TRANSLATION_PAGE = os.path.join(BASE_DIR, "assets", "translation_page.pdf")

# Fallback translation page location if asset is stored in upper folder
if not os.path.exists(TRANSLATION_PAGE):
    UPPER_ASSET = os.path.join(os.path.dirname(BASE_DIR), "LOD", "assets", "translation_page.pdf")
    if os.path.exists(UPPER_ASSET):
        TRANSLATION_PAGE = UPPER_ASSET

ENGLISH_PARAGRAPHS = [
    "You have defaulted the payment of the outstanding balance due to Sri Lanka Telecom PLC in respect of the above Telephone Number and the Telecommunication Services provided to you.",
    "Sri Lanka Telecom PLC has repeatedly requested you to settle the said outstanding balance. However, you have failed and neglected to settle the same to date.",
    "TAKE NOTICE that you are hereby required to pay the said sum of <b>Rs. {outstanding_balance}</b> to Sri Lanka Telecom PLC within Fourteen (14) days from the date hereof.",
    "PLEASE TAKE FURTHER NOTICE that in the event of your failure to settle the said sum within the stipulated period, Sri Lanka Telecom PLC will be compelled to initiate legal proceedings against you for the recovery of the said sum together with legal interest and costs of suit without any further notice to you.",
]

ATTORNEY_BLOCK = [
    "CHAMANTHI ATHUKORALA",
    "Attorney-at-Law & Notary Public",
    "Legal Division",
    "Sri Lanka Telecom PLC",
    "Lotus Road, Colombo 01.",
]

def build_html(data):
    address_lines = data.get("client_address_lines", [])
    if isinstance(address_lines, str):
        address_lines = [address_lines]
    address_html = "<br>".join(address_lines)
    attorney_html = "<br>".join(ATTORNEY_BLOCK)
    paragraphs_html = "\n".join(f"    <p>{p.format(**data)}</p>" for p in ENGLISH_PARAGRAPHS)

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{
    font-family: 'Book Antiqua', 'Palatino Linotype', Georgia, serif;
    font-size: 9pt;
    color: #000;
    line-height: 1.25;
  }}
  .header {{
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    margin-bottom: 20pt;
  }}
  .recipient {{ flex-shrink: 0; font-size: 9pt; }}
  .attorney {{ text-align: left; white-space: nowrap; margin-left: 40pt; flex-shrink: 0; }}
  .refno {{ text-align: center; margin: 4pt 0 14pt; }}
  .title {{
    font-family: 'Courier New', Courier, monospace;
    font-size: 10pt;
    text-align: center;
    font-weight: bold;
    text-decoration: underline;
    letter-spacing: 1px;
    margin: 10pt 0;
  }}
  .fields {{ margin-bottom: 10pt; }}
  .fields div {{ display: flex; }}
  .fields .label {{ width: 160pt; flex-shrink: 0; }}
  .company {{ font-weight: bold; margin-bottom: 8pt; }}
  p {{ text-align: justify; margin: 0 0 9pt; }}
  .closing {{ margin-top: 14pt; }}
  .sig-gap {{ height: 36pt; }}
</style>
</head>
<body>

<div class="header">
  <div class="recipient">{data.get('client_name', '')}<br>{address_html}</div>
  <div class="attorney">{attorney_html}<br>{data.get('letter_date', '')}</div>
</div>

<div class="refno">{data.get('reference_number', '1')}</div>

<p>Dear Sir/Madam,</p>

<div class="title">LETTER OF DEMAND AND TERMINATION</div>

<div class="fields">
  <div><span class="label">OUTSTANDING BALANCE</span><span>: <b>Rs. {data.get('outstanding_balance', '0.00')}</b></span></div>
  <div><span class="label">ACCOUNT NUMBER</span><span>: {data.get('account_number', '')}</span></div>
  <div><span class="label">TELEPHONE NUMBER</span><span>: <b>{data.get('telephone_number', '')}</b></span></div>
</div>

<div class="company">SRI LANKA TELECOM PLC</div>

{paragraphs_html}

<div class="closing">
  Yours faithfully,
  <div class="sig-gap"></div>
  Attorney-at-Law
</div>

</body>
</html>"""

class LODRenderer:
    def __init__(self, template_dir=None):
        self.template_dir = template_dir or BASE_DIR
        self.data = None

    def render(self, data):
        self.data = data
        return self

    def save(self, output_path):
        if self.data is None:
            raise ValueError("No data passed to LODRenderer.render() before calling save()")
        record = self.data[0] if isinstance(self.data, list) and self.data else self.data
        return self.generate_pdf(record, output_path)

    def generate_pdf(self, record, output_path):
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        html = build_html(record)
        
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            english_pdf_path = tmp.name

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.set_content(html, wait_until="load")
                page.pdf(
                    path=english_pdf_path,
                    format="A4",
                    print_background=True,
                    margin={"top": "16mm", "bottom": "16mm", "left": "20mm", "right": "20mm"},
                )
                browser.close()

            if os.path.exists(TRANSLATION_PAGE):
                writer = PdfWriter()
                for page_item in PdfReader(english_pdf_path).pages:
                    writer.add_page(page_item)
                for page_item in PdfReader(TRANSLATION_PAGE).pages:
                    writer.add_page(page_item)
                with open(output_path, "wb") as f_out:
                    writer.write(f_out)
            else:
                with open(english_pdf_path, "rb") as f_in, open(output_path, "wb") as f_out:
                    f_out.write(f_in.read())

        finally:
            if os.path.exists(english_pdf_path):
                try:
                    os.remove(english_pdf_path)
                except Exception:
                    pass
        return output_path
