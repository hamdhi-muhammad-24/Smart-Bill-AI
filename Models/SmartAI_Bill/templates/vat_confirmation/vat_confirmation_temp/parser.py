"""
parser.py
Reads recipients.csv and turns each row into a clean dict that render.py
can consume without worrying about missing columns or blank cells.

Expected CSV columns:
    recipient_name, address_line1, address_line2, address_line3, reference, vat_no

address_line2 / address_line3 may be blank for short addresses.
"""

import csv
import sys

REQUIRED_COLUMNS = [
    "recipient_name",
    "reference",
    "vat_no",
]

OPTIONAL_COLUMNS = ["address_line1", "address_line2", "address_line3", "address_line4"]


def load_recipients(csv_path):
    records = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
        if missing:
            sys.exit(
                f"recipients.csv is missing required column(s): {missing}\n"
                f"Found columns: {reader.fieldnames}"
            )

        for i, row in enumerate(reader, start=2):  # start=2: row 1 is header
            record = {}
            for col in REQUIRED_COLUMNS:
                val = (row.get(col) or "").strip()
                if not val:
                    sys.exit(f"recipients.csv row {i}: '{col}' is empty. Fix and re-run.")
                record[col] = val

            for col in OPTIONAL_COLUMNS:
                val = (row.get(col) or "").strip()
                record[col] = val if val else None

            # Build the address block as a clean list, dropping blanks
            record["address_lines"] = [
                line for line in (
                    record["recipient_name"],
                    record["address_line1"],
                    record["address_line2"],
                    record["address_line3"],
                    record["address_line4"],
                ) if line
            ]

            records.append(record)

    if not records:
        sys.exit("recipients.csv has no data rows.")

    return records


if __name__ == "__main__":
    # quick manual check: python parser.py recipients.csv
    path = sys.argv[1] if len(sys.argv) > 1 else "recipients.csv"
    recs = load_recipients(path)
    print(f"Loaded {len(recs)} recipient(s).")
    for r in recs:
        print(" -", r["recipient_name"], "|", r["reference"], "|", r["vat_no"])
