import unittest
from unittest.mock import patch, MagicMock
import gzip
import json
import tempfile
import os


def _make_so(po_number, secondary_po, service_order_id):
    """Create a mock service order object with attribute access."""
    so = MagicMock()
    so.po_number = po_number
    so.secondary_po = secondary_po
    so.service_order_id = service_order_id
    return so


class TestUpdateDict(unittest.TestCase):
    """Test the update_dict function that builds PO lookup."""

    def test_update_dict_basic(self):
        from app.PurchaseOrders import update_dict

        lookup = {}
        response = [
            _make_so("PO100", None, "SO1"),
            _make_so("PO200", "SPO200", "SO2"),
        ]
        result = update_dict(lookup, response)
        self.assertEqual(result["PO100"], ["SO1"])
        self.assertEqual(result["PO200"], ["SO2"])
        self.assertEqual(result["SPO200"], ["SO2"])

    def test_update_dict_appends_to_existing(self):
        from app.PurchaseOrders import update_dict

        lookup = {"PO100": ["SO1"]}
        response = [
            _make_so("PO100", None, "SO2"),
        ]
        result = update_dict(lookup, response)
        self.assertEqual(result["PO100"], ["SO1", "SO2"])

    def test_update_dict_no_duplicate_service_orders(self):
        from app.PurchaseOrders import update_dict

        lookup = {"PO100": ["SO1"]}
        response = [
            _make_so("PO100", None, "SO1"),
        ]
        result = update_dict(lookup, response)
        self.assertEqual(result["PO100"], ["SO1"])

    def test_update_dict_empty_response(self):
        from app.PurchaseOrders import update_dict

        lookup = {"PO100": ["SO1"]}
        result = update_dict(lookup, [])
        self.assertEqual(result, {"PO100": ["SO1"]})

    def test_update_dict_secondary_po_empty_string(self):
        from app.PurchaseOrders import update_dict

        lookup = {}
        response = [
            _make_so("PO100", "", "SO1"),
        ]
        result = update_dict(lookup, response)
        self.assertIn("PO100", result)
        self.assertNotIn("", result)

    def test_update_dict_secondary_po_same_as_primary(self):
        from app.PurchaseOrders import update_dict

        lookup = {}
        response = [
            _make_so("PO100", "PO100", "SO1"),
        ]
        result = update_dict(lookup, response)
        self.assertEqual(result["PO100"], ["SO1"])


class TestExtractPo(unittest.TestCase):
    """Test the extract_po function for PO number extraction."""

    def test_basic_po(self):
        from app.PurchaseOrders import extract_po

        self.assertEqual(extract_po("PO12345.pdf"), "12345")

    def test_po_with_dash(self):
        from app.PurchaseOrders import extract_po

        self.assertEqual(extract_po("PO-12345.pdf"), "12345")

    def test_po_with_hash(self):
        from app.PurchaseOrders import extract_po

        self.assertEqual(extract_po("PO#12345.pdf"), "12345")

    def test_po_with_underscore(self):
        from app.PurchaseOrders import extract_po

        self.assertEqual(extract_po("PO_12345.pdf"), "12345")

    def test_po_with_space(self):
        from app.PurchaseOrders import extract_po

        self.assertEqual(extract_po("PO 12345.pdf"), "12345")

    def test_po_case_insensitive(self):
        from app.PurchaseOrders import extract_po

        self.assertEqual(extract_po("po12345.pdf"), "12345")

    def test_po_no_pdf_extension_raises(self):
        from app.PurchaseOrders import extract_po

        with self.assertRaises(ValueError):
            extract_po("PO12345.txt")

    def test_po_complex_number(self):
        from app.PurchaseOrders import extract_po

        result = extract_po("PO ABC-123.pdf")
        self.assertEqual(result, "ABC-123")


class TestSaveAsZipFile(unittest.TestCase):
    def test_save_and_load_zip(self):
        from app.PurchaseOrders import save_as_zip_file

        test_data = {"PO100": ["SO1", "SO2"], "PO200": ["SO3"]}

        with tempfile.NamedTemporaryFile(suffix=".json.gz", delete=False) as f:
            temp_path = f.name

        try:
            with patch("app.PurchaseOrders.PO_DICT_FILE", temp_path):
                save_as_zip_file(test_data)

            with gzip.open(temp_path, "rb") as f:
                loaded = json.loads(f.read().decode("utf-8"))
            self.assertEqual(loaded, test_data)
        finally:
            os.unlink(temp_path)


class TestUpdatePONumbers(unittest.TestCase):
    @patch("app.PurchaseOrders.save_as_zip_file")
    @patch("app.PurchaseOrders.api.get_service_orders", return_value=[])
    @patch("app.PurchaseOrders.cp")
    def test_file_not_found_rebuilds(self, mock_cp, mock_api, mock_save):
        from app.PurchaseOrders import update_PO_numbers

        with tempfile.TemporaryDirectory() as tmpdir:
            nonexistent = os.path.join(tmpdir, "missing.json.gz")
            with patch("app.PurchaseOrders.PO_DICT_FILE", nonexistent):
                result = update_PO_numbers()
        self.assertIsInstance(result, dict)

    @patch("app.PurchaseOrders.save_as_zip_file")
    @patch("app.PurchaseOrders.api.get_service_orders", return_value=[])
    @patch("app.PurchaseOrders.cp")
    def test_valid_file_no_updates(self, mock_cp, mock_api, mock_save):
        from app.PurchaseOrders import update_PO_numbers

        test_data = {"PO100": ["SO1"]}
        with tempfile.NamedTemporaryFile(suffix=".json.gz", delete=False) as f:
            temp_path = f.name
            f.write(gzip.compress(json.dumps(test_data).encode("utf-8")))

        try:
            with patch("app.PurchaseOrders.PO_DICT_FILE", temp_path):
                result = update_PO_numbers()
            self.assertEqual(result["PO100"], ["SO1"])
        finally:
            os.unlink(temp_path)


if __name__ == "__main__":
    unittest.main()
