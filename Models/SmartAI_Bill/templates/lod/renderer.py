"""
LOD (Letter of Demand & Termination) Pure Python Renderer.
Uses ReportLab canvas drawing for Page 1 (matching exact coordinates of Demand_Letter_0041645897.pdf)
and PyMuPDF (fitz) to append Page 2 (Certified Sinhala/Tamil Translation Notice).
No Playwright / Chromium browser required!
"""
import io
import os
import fitz  # PyMuPDF
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TRANSLATION_PAGE = os.path.join(BASE_DIR, 'assets', 'translation_page.pdf')


def draw_justified_line(c, text, font, size, x, y, width):
    words = text.split()
    if len(words) <= 1:
        c.drawString(x, y, text)
        return
    word_width_total = sum(c.stringWidth(w, font, size) for w in words)
    gap = (width - word_width_total) / (len(words) - 1)
    cx = x
    for word in words:
        c.drawString(cx, y, word)
        cx += c.stringWidth(word, font, size) + gap


def build_lod_page1_pdf(data):
    """
    Renders Page 1 of the LOD letter as a PDF in memory (BytesIO) using ReportLab canvas.
    Exact positioning matching Demand_Letter_0041645897.pdf sample.
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    max_w = 534.7 - 62.2  # 472.5 pt printable width

    def y_top(val):
        return 841.89 - val

    # 1. Attorney Block (x=424.1)
    c.setFont("Times-Roman", 9)
    attorney_lines = [
        "Damithri Palliyaguru",
        "Attorney-at-Law- LLB",
        "CTO Ground Floor",
        "Sri Lanka Telecom PLC",
        "Lotus Road",
        "Colombo 01.",
        "T.P No: 011 2341080",
        "Email - damithri@slt.com.lk",
        "(9.00 AM - 4.30PM) on",
        str(data.get("letter_date", "23.03.2026"))
    ]
    att_y = 51.4
    for i, line in enumerate(attorney_lines):
        c.drawString(424.1, y_top(att_y + i * 11.25), line)

    # 2. Recipient Block (x=62.2)
    client_name = str(data.get("client_name", "")).strip()
    address_lines = data.get("client_address_lines", [])
    rec_lines = [client_name] + [str(a).strip() for a in address_lines if str(a).strip()]
    rec_y = 107.6
    for i, line in enumerate(rec_lines):
        c.drawString(62.2, y_top(rec_y + i * 11.25), str(line))

    # 3. Ref No (Centered at x=296.2, y=184.1)
    ref_no = str(data.get("reference_number", "1")).strip()
    c.drawString(296.2, y_top(184.1), ref_no)

    # 4. Salutation (x=62.2, y=208.9)
    c.drawString(62.2, y_top(208.9), "Dear Sir/Madam,")

    # 5. Title (Centered at x=298.1, y=230.2, Courier-Bold size 10)
    c.setFont("Courier-Bold", 10)
    c.drawCentredString(298.1, y_top(230.2), "LETTER OF DEMAND AND TERMINATION")

    # 6. Fields Block (x=62.2 for labels, x=222.2 for values)
    c.setFont("Times-Roman", 9)
    c.drawString(62.2, y_top(253.1), "OUTSTANDING BALANCE")
    c.drawString(222.2, y_top(253.1), ": ")
    c.setFont("Times-Bold", 9)
    bal_str = f"Rs. {data.get('outstanding_balance', '0.00')}"
    c.drawString(226.7, y_top(253.1), bal_str)

    c.setFont("Times-Roman", 9)
    c.drawString(62.2, y_top(265.1), "ACCOUNT NUMBER")
    acc_str = f": {data.get('account_number', '')}"
    c.drawString(222.2, y_top(265.1), acc_str)

    c.drawString(62.2, y_top(276.4), "TELEPHONE NUMBER")
    c.drawString(222.2, y_top(276.4), ": ")
    c.setFont("Times-Bold", 9)
    tel_str = str(data.get('telephone_number', ''))
    c.drawString(226.7, y_top(276.4), tel_str)

    # 7. Company Name (x=62.2, y=297.7, Times-Bold 9)
    c.setFont("Times-Bold", 9)
    c.drawString(62.2, y_top(297.7), "SRI LANKA TELECOM PLC")

    # 8. Paragraphs
    reg_office = str(data.get("regional_office", "MATARA")).strip()

    # Paragraph 1
    c.setFont("Times-Roman", 9)
    c.drawString(62.2, y_top(317.6), "I write on the instructions of my Client Sri Lanka Telecom PLC, which has a Regional Office at ")
    w_prefix = c.stringWidth("I write on the instructions of my Client Sri Lanka Telecom PLC, which has a Regional Office at ", "Times-Roman", 9)
    c.setFont("Times-Bold", 9)
    c.drawString(62.2 + w_prefix, y_top(317.6), reg_office)
    w_reg = c.stringWidth(reg_office, "Times-Bold", 9)
    c.setFont("Times-Roman", 9)
    c.drawString(62.2 + w_prefix + w_reg, y_top(317.6), " and its")

    draw_justified_line(c, "Head Office at Lotus Road, Colombo 01 and which is the Successor to all the assets, liabilities, rights, obligations and", "Times-Roman", 9, 62.2, y_top(329.6), max_w)
    c.drawString(62.2, y_top(340.9), "contracts of the Corporation named Sri Lanka Telecom and of the Department of Telecommunications.")

    # Paragraph 2 (y=361.1)
    draw_justified_line(c, "I am instructed that, you are a Customer of my Client and that, as such, at your request, my Client installed its", "Times-Roman", 9, 62.2, y_top(361.1), max_w)
    draw_justified_line(c, "telephone equipment and provided a telephone service to you at your premises bearing the above stated number,", "Times-Roman", 9, 62.2, y_top(372.4), max_w)
    draw_justified_line(c, "subject to the terms and conditions of the Agreement entered into by and between my client and you, including the", "Times-Roman", 9, 62.2, y_top(383.6), max_w)
    c.drawString(62.2, y_top(394.9), "payment of all subscriptions, charges, fees and other monies.")

    # Paragraph 3 (y=415.1)
    draw_justified_line(c, "I am instructed that, you have benefited from and used the said facilities and services provided by my client, but you", "Times-Roman", 9, 62.2, y_top(415.1), max_w)
    draw_justified_line(c, "have failed and neglected to pay the monies due as aforesaid, though my client has sent you Monthly Statements", "Times-Roman", 9, 62.2, y_top(426.4), max_w)
    c.drawString(62.2, y_top(437.6), "setting out the sums, which are due, and payable.")

    # Paragraph 4 (y=457.9)
    c.setFont("Times-Roman", 9)
    c.drawString(62.2, y_top(457.9), "I am instructed that, presently there is a sum of ")
    w_p4_pre = c.stringWidth("I am instructed that, presently there is a sum of ", "Times-Roman", 9)
    c.setFont("Times-Bold", 9)
    c.drawString(62.2 + w_p4_pre, y_top(457.9), bal_str)
    w_p4_bal = c.stringWidth(bal_str, "Times-Bold", 9)
    c.setFont("Times-Roman", 9)
    c.drawString(62.2 + w_p4_pre + w_p4_bal, y_top(457.9), " owing from you to my Client, on account of the")

    draw_justified_line(c, "subscriptions, charges, fees and other monies due from you to my Client for the installation and provision of the said", "Times-Roman", 9, 62.2, y_top(469.9), max_w)
    c.drawString(62.2, y_top(481.1), "telephone services. You are liable and bound and obliged to pay these monies to my Client.")

    # Paragraph 5 (y=501.4)
    draw_justified_line(c, "However, you have wrongfully and unlawfully failed and neglected to pay these monies to my Client and the said", "Times-Roman", 9, 62.2, y_top(501.4), max_w)
    draw_justified_line(c, "monies payable by you to my Client, are in arrears and in default. Therefore, my Client has instructed me to advise", "Times-Roman", 9, 62.2, y_top(512.6), max_w)
    c.drawString(62.2, y_top(523.9), "that the aforesaid Agreement is hereby terminated and determined.")

    # Paragraph 6 (y=544.1)
    draw_justified_line(c, "I am also instructed to demand and I do hereby demand payment from you to my Client, of the aforesaid monies,", "Times-Roman", 9, 62.2, y_top(544.1), max_w)
    draw_justified_line(c, "within 14 days of the date of receipt of this letter and advise that if you fail to make such payment, legal action will be", "Times-Roman", 9, 62.2, y_top(555.4), max_w)
    c.drawString(62.2, y_top(566.6), "instituted against you, for the recovery of these monies, without any further notice to you.")

    # 9. Closing (y=591.4)
    c.drawString(62.2, y_top(591.4), "Yours faithfully,")

    # 10. Sign-off (y=638.6)
    c.drawString(62.2, y_top(638.6), "Attorney-at-Law")

    c.save()
    buf.seek(0)
    return buf.getvalue()


class LODRenderer:
    """
    Renderer class conforming to SmartAI_Bill BaseRenderer interface.
    """
    def __init__(self):
        self.generated_pdfs = [] # list of (output_filename, pdf_bytes, record)

    def render(self, data):
        """
        Accepts dict containing:
        - "records": list of client dicts (for multi-recipient spreadsheet)
        OR single client record dict.
        """
        records = data.get("records", [])
        if not records and "account_number" in data:
            records = [data]

        self.generated_pdfs = []
        for record in records:
            page1_bytes = build_lod_page1_pdf(record)

            # Combine with Translation Notice (Page 2) via PyMuPDF
            doc = fitz.open(stream=page1_bytes, filetype="pdf")

            if os.path.exists(TRANSLATION_PAGE):
                trans_doc = fitz.open(TRANSLATION_PAGE)
                doc.insert_pdf(trans_doc)
                trans_doc.close()

            pdf_out_bytes = doc.tobytes()
            doc.close()

            acc_no = str(record.get("account_number", "unknown")).strip().replace(" ", "")
            fname = f"{acc_no}_LOD.pdf"
            self.generated_pdfs.append((fname, pdf_out_bytes, record))

    def save(self, output_path):
        """
        Save all generated PDFs in self.generated_pdfs to the directory containing output_path.
        """
        if not self.generated_pdfs:
            raise RuntimeError("No PDFs generated in render()")

        out_dir = os.path.dirname(os.path.abspath(output_path))
        os.makedirs(out_dir, exist_ok=True)

        if len(self.generated_pdfs) == 1:
            fname, pdf_bytes, _ = self.generated_pdfs[0]
            target_file = output_path if output_path.lower().endswith(".pdf") else os.path.join(out_dir, fname)
            with open(target_file, "wb") as f:
                f.write(pdf_bytes)
        else:
            for fname, pdf_bytes, _ in self.generated_pdfs:
                target_file = os.path.join(out_dir, fname)
                with open(target_file, "wb") as f:
                    f.write(pdf_bytes)

