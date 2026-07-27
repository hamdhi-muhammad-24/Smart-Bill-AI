# VAT Confirmation Letter Generator - Project Spec

## Goal
Generate one standalone PDF per recipient from a CSV list, overlaying text
onto `template.pdf` (a blank SLTMOBITEL letterhead: logo top-right, faint
diagonal watermark, footer disclaimer bar - no body text baked in). Output
is **21+ separate PDF files**, one per recipient, not a combined PDF.

Ground truth for what "correct" looks like is the reference letter shown in
`VAT number confirmation Letter Amendednew ADD.pdf` (page 1 of that 21-page
file = the target). Recreate that exact layout.

## Reference file facts
- 21-page batch PDF, each page = one recipient, sequential page numbers
  visible bottom-right (page 1 -> "65", page 2 -> "66", ...).
- `template.pdf`'s actual page size is `595.5 x 850.08` pt - **not** plain
  A4 (`595 x 842`). Don't let a rebuild silently default to A4.

## Layout - this is the part that's easy to get wrong
There are **two different left-indents on the page**, not one margin and
not a right-aligned block. Confirmed by inspecting the reference: every
line of the recipient block starts at the *same x position* regardless of
line length ("Beliwewa Ihalagama Gemunu Sansa Society" and "Beliwewa-" both
start flush at the same left edge) - so it is a left-aligned block sitting
in an indented column, **not** right-margin-anchored text.

Two columns:
1. **Body margin** (~56-60pt from left edge) - used by `To:`,
   `Our Reference:`, `VAT No.:`, `Subject:`, salutation, all body
   paragraphs, closing, signature.
2. **Indented block** (~310-320pt from left edge, roughly under/near the
   logo) - used ONLY by the `Date:` line and the recipient name/address
   lines directly below it. Left-aligned within that column, not centered
   or right-aligned.

These are rough pixel-derived estimates from a screenshot, not a measured
PDF - **before finalizing, extract the actual embedded coordinates or
re-measure against the reference PDF directly** (e.g. render each candidate
version to PNG at a known DPI and compare pixel offsets against the
reference page, rather than trusting eyeballed numbers).

### Vertical order (top to bottom)
1. Logo (from template.pdf, static)
2. `Date: DD.MM.YYYY` - indented column, today's date at render time, same
   for every letter in one batch run (not a per-row CSV value)
3. Recipient name + address lines - indented column, bold, one line per
   non-empty address field, no blank lines for missing fields
4. Blank gap
5. `To:  <recipient name>` - body margin, bold
6. `Our Reference:  <reference>` - body margin, bold
7. `VAT No.:  <vat number>` - body margin, bold
8. Blank gap
9. `Subject: Verification of VAT Registration Number` - body margin, bold
10. Blank line
11. `Dear Valued Customer,` - body margin, regular
12. Seven body paragraphs (exact text below) - body margin, regular,
    justified-looking but actually just left-aligned wrapped text; one
    paragraph line (`Email address: ...`) is bold
13. `Yours sincerely,` then `Sri Lanka Telecom PLC` (bold) - body margin
14. Footer: horizontal rule, italic centered disclaimer text, page number
    bottom-right - this part comes from template.pdf itself if the
    template already includes it, otherwise must be drawn to match exactly

### Fixed text content (do not paraphrase - reproduce exactly)
```
Subject: Verification of VAT Registration Number

Dear Valued Customer,

We wish to draw your kind attention to an important matter concerning the Value Added Tax (VAT) registration details associated with your SLTMOBITEL account. As part of our commitment to ensuring the accuracy of your billing records and to facilitate your compliance obligations with the Inland Revenue Department (IRD) of Sri Lanka, we are currently undertaking a systematic review of VAT registration numbers maintained in our systems.

Our records indicate that the VAT Registration Number currently reflected against your account, as referenced above. It is essential that this information is accurate and up to date, as any discrepancy may have implications on your VAT input credit claims and compliance standing with the Inland Revenue Department.

We kindly request you to verify the VAT Registration Number indicated in this letter against your official VAT certificate issued by the Inland Revenue Department.

Should you find that the number on record is incorrect or requires an update, please submit the corrected VAT Registration Number along with a copy of your valid VAT Certificate to the following email address on or before {deadline}.

Email address: {email}

Please note that if we do not hear from you by the stipulated date, we will consider the VAT Registration Number on record as confirmed. Sri Lanka Telecom PLC regrets that it cannot be held responsible for any implications arising with the Inland Revenue Department due to unnotified inaccuracies.

We appreciate your prompt attention to this matter and thank you for your continued patronage of Sri Lanka Telecom PLC.

Yours sincerely,
Sri Lanka Telecom PLC
```
Footer disclaimer (italic, centered, above a horizontal rule):
```
***This is a System Generated Letter. No signature is required. ***
```

### Typography
- Body font: serif (Times-family read as closest match to the reference).
- Body size: ~10.5pt, line height ~14-15.5pt.
- Bold used for: recipient block, `To:`/`Our Reference:`/`VAT No.:`,
  `Subject:` line, `Email address:` line, `Sri Lanka Telecom PLC` sign-off.
- Footer disclaimer: italic, smaller (~9pt).

### Fit constraint
All content (worst case: a 4-line recipient address) must stay clear of the
footer bar. Reference shows the letter ending with comfortable whitespace
above the footer rule - don't let paragraph spacing push body text into or
past the footer.

## CSV schema (recipients.csv)
Required columns: `recipient_name, address_line1, reference, vat_no`
Optional: `address_line2, address_line3` - blank cells are dropped entirely
(no empty line rendered), not padded.

## File architecture
- **config.py** - page geometry, fonts, all coordinates for both columns
  (body margin vs. indented column), fixed paragraph text with
  `{deadline}`/`{email}` placeholders, footer text, starting page number
  (`START_PAGE_NUMBER`, currently 65 per the reference), output directory.
- **parser.py** - reads and validates `recipients.csv`, fails loudly with a
  clear message on missing required columns/empty required cells, builds
  each row into a clean dict including a pre-filtered `address_lines` list.
- **render.py** - per row: draws a reportlab overlay canvas with all
  variable + fixed text at the two column positions, merges it onto a
  fresh copy of `template.pdf`'s page (pypdf `merge_page`), writes one PDF
  per row named `VAT_Letter_<reference>.pdf` to `output/`. Date = today's
  date at render time. Page number = running counter starting at
  `START_PAGE_NUMBER`, incremented once per row in CSV order (not a CSV
  column).

## Verification workflow (don't skip this)
1. Render at least one sample row.
2. Convert to PNG at a fixed DPI: `pdftoppm -png -r 100 file.pdf file`
   (poppler-utils; already available in sandboxed environments that have
   `pdftoppm`).
3. Visually compare against the reference screenshot/PDF page before
   declaring layout correct - text position bugs are invisible from code
   alone and only show up in a rendered comparison.

## Explicit non-goals
- Do not produce a single combined multi-page PDF - 21 separate files.
- Do not add CSV columns (e.g. `date`, `page_number`) without checking
  with the user - both are computed at render time, not sourced from data.
- Do not treat the `{deadline}` / `{email}` values as fixed forever - they
  are per-campaign values that should live in config.py as named constants,
  not be hardcoded inline in the paragraph text.
