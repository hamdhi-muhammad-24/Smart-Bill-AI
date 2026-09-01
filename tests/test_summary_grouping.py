import os
import sys
import json
import tempfile
import pytest

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
smartai_dir = os.path.join(root_dir, "Models", "SmartAI_Bill")
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
if smartai_dir not in sys.path:
    sys.path.insert(0, smartai_dir)

from processing.output_manager import (
    normalize_account_number,
    extract_account_from_filename,
    create_summary_groups,
)
from processing.batch_processor import ProcessingResult


class TestAccountNormalization:
    def test_normalize_clean_number(self):
        assert normalize_account_number("0053416491") == "0053416491"

    def test_normalize_spaced_number(self):
        # As present in summary statement GMF: "005 341 6491"
        assert normalize_account_number("005 341 6491") == "0053416491"

    def test_normalize_multiple_spaces_and_tabs(self):
        assert normalize_account_number("  005   341   6491  ") == "0053416491"
        assert normalize_account_number("005\t341\t6491") == "0053416491"

    def test_normalize_with_alphanumeric_letter(self):
        # As present in summary statement GMF: "005 104 340X"
        assert normalize_account_number("005 104 340X") == "005104340X"
        assert normalize_account_number("005 104 340x") == "005104340X"

    def test_normalize_with_hyphens_or_underscores(self):
        assert normalize_account_number("005-341-6491") == "0053416491"
        assert normalize_account_number("005_341_6491") == "0053416491"

    def test_normalize_empty_or_none(self):
        assert normalize_account_number("") == ""
        assert normalize_account_number(None) == ""


class TestFilenameAccountExtraction:
    def test_extract_standard_templates(self):
        assert extract_account_from_filename("0005842786_NONVAT_HOME.pdf") == "0005842786"
        assert extract_account_from_filename("0053416491_NONVAT_ENTERPRISE.pdf") == "0053416491"
        assert extract_account_from_filename("0053416491_VAT_ENTERPRISE.pdf") == "0053416491"
        assert extract_account_from_filename("0053416491_VAT_HOME.pdf") == "0053416491"
        assert extract_account_from_filename("0053416491_ProductLevel.pdf") == "0053416491"
        assert extract_account_from_filename("0053416491_SubscriptionLevel.pdf") == "0053416491"
        assert extract_account_from_filename("0053416491_InvoiceOfSummary.pdf") == "0053416491"
        assert extract_account_from_filename("0053416491_USD_OPEN_Item.pdf") == "0053416491"
        assert extract_account_from_filename("0053416491_LOD.pdf") == "0053416491"
        assert extract_account_from_filename("0053416491_Vat_confirmation.pdf") == "0053416491"
        assert extract_account_from_filename("0053416491_Final_Notice.pdf") == "0053416491"
        assert extract_account_from_filename("0053416491_Customer_Letter.pdf") == "0053416491"

    def test_extract_letter_in_account(self):
        assert extract_account_from_filename("005104340X_NONVAT_HOME.pdf") == "005104340X"

    def test_extract_bare_account_and_legacy_naming(self):
        assert extract_account_from_filename("0005842786.pdf") == "0005842786"
        assert extract_account_from_filename("SLT20eBill-0005842786.pdf") == "0005842786"

    def test_extract_duplicate_suffix(self):
        assert extract_account_from_filename("0005842786_NONVAT_HOME_dup1.pdf") == "0005842786"

    def test_extract_ignores_summary_prefixed_files(self):
        assert extract_account_from_filename("00_SUMMARY.pdf") == ""
        assert extract_account_from_filename("00_CR002515044_SUMMARY.pdf") == ""


class TestSummaryGroupingEndToEnd:
    def test_create_summary_groups_moves_matching_bills(self):
        with tempfile.TemporaryDirectory() as date_dir:
            # Create mock cycle / batch directories
            cycle1_batch1 = os.path.join(date_dir, "Cycle_1", "Batch_1")
            cycle2_batch1 = os.path.join(date_dir, "Cycle_2", "Batch_1")
            summary_batch1 = os.path.join(date_dir, "Summary_Statement", "Batch_1")
            os.makedirs(cycle1_batch1)
            os.makedirs(cycle2_batch1)
            os.makedirs(summary_batch1)

            # Create mock PDF files
            bill1 = os.path.join(cycle1_batch1, "0005842786_NONVAT_HOME.pdf")
            bill2 = os.path.join(cycle1_batch1, "0053416491_NONVAT_HOME.pdf")
            bill3 = os.path.join(cycle2_batch1, "0052812923_VAT_ENTERPRISE.pdf")
            bill_unrelated = os.path.join(cycle2_batch1, "9999999999_NONVAT_HOME.pdf")
            summary_pdf = os.path.join(summary_batch1, "SUMMARY.pdf")

            for p in [bill1, bill2, bill3, bill_unrelated, summary_pdf]:
                with open(p, "wb") as f:
                    f.write(b"%PDF-1.4 mock content")

            # Processing result for summary statement
            res = ProcessingResult(
                source_file="summary.gmf",
                template_id="summary_statement",
                output_pdf=summary_pdf,
                success=True,
            )
            # Account numbers in summary statement have spaces:
            res.summary_meta = {
                "customer_ref": "CR002515044",
                "account_nos": ["000 584 2786", "005 341 6491", "005 281 2923", "005 104 340X"],
                "pdf_name": "SUMMARY.pdf",
            }

            # Run summary grouping
            create_summary_groups(date_dir, [res])

            cr_dir = os.path.join(date_dir, "summary", "CR002515044")
            assert os.path.exists(cr_dir), "CR folder should be created"

            # Check summary PDF moved with 00_ prefix
            assert os.path.exists(os.path.join(cr_dir, "00_SUMMARY.pdf"))

            # Check matching bills moved into CR folder
            assert os.path.exists(os.path.join(cr_dir, "0005842786_NONVAT_HOME.pdf"))
            assert os.path.exists(os.path.join(cr_dir, "0053416491_NONVAT_HOME.pdf"))
            assert os.path.exists(os.path.join(cr_dir, "0052812923_VAT_ENTERPRISE.pdf"))

            # Check matching bills no longer exist in their source directories
            assert not os.path.exists(bill1)
            assert not os.path.exists(bill2)
            assert not os.path.exists(bill3)

            # Check unrelated bill remained in its source directory
            assert os.path.exists(bill_unrelated)
            assert not os.path.exists(os.path.join(cr_dir, "9999999999_NONVAT_HOME.pdf"))

            # Check manifest was created
            manifest_path = os.path.join(cr_dir, "manifest.json")
            assert os.path.exists(manifest_path)
            with open(manifest_path, "r", encoding="utf-8") as mf:
                manifest_data = json.load(mf)
                assert manifest_data["customer_ref"] == "CR002515044"
                assert "0053416491" in manifest_data["account_nos"]
                assert "005104340X" in manifest_data["account_nos"]

    def test_subsequent_bill_run_routes_to_existing_cr_folder(self):
        with tempfile.TemporaryDirectory() as date_dir:
            # 1. First run: Summary Statement is processed
            summary_batch = os.path.join(date_dir, "Summary_Statement", "Batch_1")
            os.makedirs(summary_batch)
            summary_pdf = os.path.join(summary_batch, "SUMMARY.pdf")
            with open(summary_pdf, "wb") as f:
                f.write(b"%PDF-1.4 mock summary")

            res = ProcessingResult(
                source_file="summary.gmf",
                template_id="summary_statement",
                output_pdf=summary_pdf,
                success=True,
            )
            res.summary_meta = {
                "customer_ref": "CR002515044",
                "account_nos": ["005 104 340X"],
                "pdf_name": "SUMMARY.pdf",
            }
            create_summary_groups(date_dir, [res])

            cr_dir = os.path.join(date_dir, "summary", "CR002515044")
            assert os.path.exists(os.path.join(cr_dir, "00_SUMMARY.pdf"))

            # 2. Later run: Bill for 005104340X is generated in Cycle_3
            cycle3_batch = os.path.join(date_dir, "Cycle_3", "Batch_1")
            os.makedirs(cycle3_batch)
            bill_late = os.path.join(cycle3_batch, "005104340X_NONVAT_HOME.pdf")
            with open(bill_late, "wb") as f:
                f.write(b"%PDF-1.4 mock late bill")

            # Call create_summary_groups without processing_results (or with non-summary results)
            create_summary_groups(date_dir, [])

            # The late bill should be automatically moved to the existing CR folder
            assert os.path.exists(os.path.join(cr_dir, "005104340X_NONVAT_HOME.pdf"))
            assert not os.path.exists(bill_late)

    def test_multiple_summary_statements_distinct_cr_folders(self):
        with tempfile.TemporaryDirectory() as date_dir:
            summary_batch = os.path.join(date_dir, "Summary_Statement", "Batch_1")
            cycle1_batch = os.path.join(date_dir, "Cycle_1", "Batch_1")
            os.makedirs(summary_batch)
            os.makedirs(cycle1_batch)

            # Two summary statements: CR001530388 and CR000127527
            sum1_pdf = os.path.join(summary_batch, "CR001530388_SUMMARY.pdf")
            sum2_pdf = os.path.join(summary_batch, "CR000127527_SUMMARY.pdf")
            with open(sum1_pdf, "wb") as f:
                f.write(b"%PDF-1.4 summary 1")
            with open(sum2_pdf, "wb") as f:
                f.write(b"%PDF-1.4 summary 2")

            # Bills for CR001530388
            bill_cr1_1 = os.path.join(cycle1_batch, "0001372850_VAT_ENTERPRISE.pdf")
            bill_cr1_2 = os.path.join(cycle1_batch, "0001275469_VAT_ENTERPRISE.pdf")
            # Bill for CR000127527
            bill_cr2_1 = os.path.join(cycle1_batch, "0009999999_VAT_ENTERPRISE.pdf")

            for p in [bill_cr1_1, bill_cr1_2, bill_cr2_1]:
                with open(p, "wb") as f:
                    f.write(b"%PDF-1.4 bill")

            res1 = ProcessingResult("sum.gmf", "summary_statement", sum1_pdf, True)
            res1.summary_meta = {
                "customer_ref": "CR001530388",
                "account_nos": ["000 137 2850", "000 127 5469"],
                "pdf_name": "CR001530388_SUMMARY.pdf",
            }

            res2 = ProcessingResult("sum.gmf", "summary_statement", sum2_pdf, True)
            res2.summary_meta = {
                "customer_ref": "CR000127527",
                "account_nos": ["000 999 9999"],
                "pdf_name": "CR000127527_SUMMARY.pdf",
            }

            create_summary_groups(date_dir, [res1, res2])

            cr1_dir = os.path.join(date_dir, "summary", "CR001530388")
            cr2_dir = os.path.join(date_dir, "summary", "CR000127527")

            assert os.path.exists(cr1_dir)
            assert os.path.exists(cr2_dir)

            # CR001530388 folder contains its own summary and bills
            assert os.path.exists(os.path.join(cr1_dir, "00_CR001530388_SUMMARY.pdf"))
            assert os.path.exists(os.path.join(cr1_dir, "0001372850_VAT_ENTERPRISE.pdf"))
            assert os.path.exists(os.path.join(cr1_dir, "0001275469_VAT_ENTERPRISE.pdf"))
            assert not os.path.exists(os.path.join(cr1_dir, "00_CR000127527_SUMMARY.pdf"))
            assert not os.path.exists(os.path.join(cr1_dir, "0009999999_VAT_ENTERPRISE.pdf"))

            # CR000127527 folder contains its own summary and bills
            assert os.path.exists(os.path.join(cr2_dir, "00_CR000127527_SUMMARY.pdf"))
            assert os.path.exists(os.path.join(cr2_dir, "0009999999_VAT_ENTERPRISE.pdf"))
            assert not os.path.exists(os.path.join(cr2_dir, "0001372850_VAT_ENTERPRISE.pdf"))

