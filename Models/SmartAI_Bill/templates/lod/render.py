import os
import fitz
from playwright.sync_api import sync_playwright
import parser
import config
import templates


def _paragraphs_html(paragraphs, data):
    return "\n".join(f"    <p>{p.format(**data)}</p>" for p in paragraphs)


def build_html(data):
    address_html = "<br>".join(data["client_address_lines"])
    attorney_en = "<br>".join(templates.ATTORNEY_BLOCK_EN)
    body_en = _paragraphs_html(templates.ENGLISH_PARAGRAPHS, data)

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
  <div class="recipient">{data['client_name']}<br>{address_html}</div>
  <div class="attorney">{attorney_en}<br>{data['letter_date']}</div>
</div>

<div class="refno">{data['reference_number']}</div>

<p>Dear Sir/Madam,</p>

<div class="title">LETTER OF DEMAND AND TERMINATION</div>

<div class="fields">
  <div><span class="label">OUTSTANDING BALANCE</span><span>: <b>Rs. {data['outstanding_balance']}</b></span></div>
  <div><span class="label">ACCOUNT NUMBER</span><span>: {data['account_number']}</span></div>
  <div><span class="label">TELEPHONE NUMBER</span><span>: <b>{data['telephone_number']}</b></span></div>
</div>

<div class="company">SRI LANKA TELECOM PLC</div>

{body_en}

<div class="closing">
  Yours faithfully,
  <div class="sig-gap"></div>
  Attorney-at-Law
</div>

</body>
</html>"""


def _render_one(page, data):
    account_number = data['account_number'].strip()
    output_path = os.path.join(config.OUTPUT_DIR, f"Demand_Letter_{account_number}.pdf")
    english_page_path = os.path.join(config.OUTPUT_DIR, f"_english_page_{account_number}.pdf")
    html = build_html(data)

    page.set_content(html, wait_until="load")
    page.pdf(
        path=english_page_path,
        format="A4",
        print_background=True,
        margin={"top": "16mm", "bottom": "16mm", "left": "20mm", "right": "20mm"},
    )

    # Page 2 is the fixed Sinhala/Tamil certified-translation notice, identical
    # across every client letter, appended verbatim from the firm's template.
    final = fitz.open(english_page_path)
    final.insert_pdf(fitz.open(config.TRANSLATION_PAGE))
    final.save(output_path)
    final.close()
    os.remove(english_page_path)

    print(f"PDF generated: {output_path}")


def create_pdfs(limit=None):
    all_data = parser.load_all_data(limit=limit)
    if not os.path.exists(config.OUTPUT_DIR):
        os.makedirs(config.OUTPUT_DIR)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        for data in all_data:
            _render_one(page, data)
        browser.close()


if __name__ == "__main__":
    import sys
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    create_pdfs(limit=limit)
