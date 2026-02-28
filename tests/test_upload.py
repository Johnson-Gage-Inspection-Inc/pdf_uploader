import unittest
from unittest.mock import patch, MagicMock
import os
import sys
from upload import get_credentials
from upload import rename_file
from upload import upload_with_rename
from upload import fetch_SO_and_upload
from upload import upload_by_po
from upload import handle_po_upload

# Mock the app modules before importing upload
sys.modules["app"] = MagicMock()
sys.modules["app.color_print"] = MagicMock()
sys.modules["app.PurchaseOrders"] = MagicMock()
sys.modules["app.api"] = MagicMock()
sys.modules["app.pdf"] = MagicMock()
sys.modules["app.config"] = MagicMock()
sys.modules["app.orientation"] = MagicMock()


class TestGetCredentials(unittest.TestCase):
    @patch.dict(
        os.environ,
        {"QUALER_EMAIL": "test@example.com", "QUALER_PASSWORD": "password123"},
    )
    def test_get_credentials_from_env(self):
        result = get_credentials()
        self.assertEqual(result, ("test@example.com", "password123"))

    @patch.dict(os.environ, {}, clear=True)
    def test_get_credentials_missing(self):
        result = get_credentials()
        self.assertIsNone(result)


class TestRenameFile(unittest.TestCase):
    @patch("upload.pdf.increment_filename")
    @patch("upload.pdf.try_rename")
    def test_rename_file_success(self, mock_try_rename, mock_increment):
        mock_increment.return_value = "/path/to/file_1.pdf"
        mock_try_rename.return_value = True

        result = rename_file("/path/to/file.pdf", ["other_file.pdf"])
        self.assertEqual(result, "/path/to/file_1.pdf")

    @patch("upload.pdf.increment_filename")
    @patch("upload.pdf.try_rename")
    def test_rename_file_already_exists(self, mock_try_rename, mock_increment):
        mock_increment.side_effect = ["/path/to/file_1.pdf", "/path/to/file_2.pdf"]
        mock_try_rename.return_value = True

        result = rename_file("/path/to/file.pdf", ["file_1.pdf"])
        self.assertEqual(result, "/path/to/file_2.pdf")


class TestUploadWithRename(unittest.TestCase):
    @patch("upload.api.upload")
    @patch("upload.api.get_service_order_document_list")
    @patch("upload.rename_file")
    def test_upload_with_rename_no_conflict(
        self, mock_rename, mock_get_docs, mock_upload
    ):
        mock_get_docs.return_value = ["other_file.pdf"]
        mock_upload.return_value = (True, "/path/to/file.pdf")

        result, filepath = upload_with_rename("/path/to/file.pdf", "SO123", "DOC_TYPE")
        self.assertTrue(result)
        self.assertEqual(filepath, "/path/to/file.pdf")
        mock_rename.assert_not_called()

    @patch("upload.api.upload")
    @patch("upload.api.get_service_order_document_list")
    @patch("upload.rename_file")
    def test_upload_with_rename_conflict(self, mock_rename, mock_get_docs, mock_upload):
        mock_get_docs.return_value = ["file.pdf"]
        mock_rename.return_value = "/path/to/file_1.pdf"
        mock_upload.return_value = (True, "/path/to/file_1.pdf")

        result, filepath = upload_with_rename("/path/to/file.pdf", "SO123", "DOC_TYPE")
        self.assertTrue(result)
        mock_rename.assert_called_once()


class TestFetchSOAndUpload(unittest.TestCase):
    @patch("upload.upload_with_rename")
    @patch("upload.api.getServiceOrderId")
    @patch("os.path.isfile")
    def test_fetch_so_and_upload_success(self, mock_isfile, mock_get_so, mock_upload):
        mock_isfile.return_value = True
        mock_get_so.return_value = "SO123"
        mock_upload.return_value = (True, "/path/to/file.pdf")

        result, filepath = fetch_SO_and_upload("WO123", "/path/to/file.pdf", "DOC_TYPE")
        self.assertTrue(result)

    @patch("os.path.isfile")
    def test_fetch_so_and_upload_file_not_found(self, mock_isfile):
        mock_isfile.return_value = False

        result, filepath = fetch_SO_and_upload("WO123", "/path/to/file.pdf", "DOC_TYPE")
        self.assertFalse(result)


class TestUploadByPO(unittest.TestCase):
    @patch("upload.upload_with_rename")
    @patch("os.path.isfile")
    def test_upload_by_po_success(self, mock_isfile, mock_upload):
        mock_isfile.return_value = True
        mock_upload.return_value = (True, "/path/to/file.pdf")

        po_dict = {"PO123": ["SO1", "SO2"]}
        success, failed, filepath = upload_by_po(
            "/path/to/file.pdf", "PO123", po_dict, "DOC_TYPE"
        )
        self.assertEqual(success, ["SO1", "SO2"])
        self.assertEqual(failed, [])

    def test_upload_by_po_not_found(self):
        po_dict = {}
        success, failed, filepath = upload_by_po(
            "/path/to/file.pdf", "PO123", po_dict, "DOC_TYPE"
        )
        self.assertEqual(success, [])
        self.assertEqual(failed, [])


class TestHandlePOUpload(unittest.TestCase):
    @patch("upload.upload_by_po")
    @patch("upload.update_PO_numbers")
    @patch("upload.extract_po")
    def test_handle_po_upload_success(self, mock_extract, mock_update, mock_upload_po):
        mock_extract.return_value = "PO123"
        mock_update.return_value = {"PO123": ["SO1"]}
        mock_upload_po.return_value = (["SO1"], [], "/path/to/file.pdf")

        result = handle_po_upload("/path/to/PO123.pdf", "DOC_TYPE", "PO123.pdf")
        self.assertTrue(result)

    @patch("upload.upload_by_po")
    @patch("upload.update_PO_numbers")
    @patch("upload.extract_po")
    def test_handle_po_upload_failure(self, mock_extract, mock_update, mock_upload_po):
        mock_extract.return_value = "PO123"
        mock_update.return_value = {"PO123": ["SO1"]}
        mock_upload_po.return_value = ([], ["SO1"], "/path/to/file.pdf")

        result = handle_po_upload("/path/to/PO123.pdf", "DOC_TYPE", "PO123.pdf")
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
