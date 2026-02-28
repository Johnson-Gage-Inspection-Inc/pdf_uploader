import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Mock app modules BEFORE importing upload.
# This must happen before any `from upload import ...` statements,
# because upload.py executes module-level code on import.
# upload.py has module-level code (getEnv, api.login, logging.basicConfig)
# that executes on import, so mocks must be in place first.

mock_config = MagicMock()
mock_config.QUALER_STAGING_ENDPOINT = "https://staging.example.com"
mock_config.DEBUG = False
mock_config.LIVEAPI = True
mock_config.QUALER_ENDPOINT = "https://api.example.com"
mock_config.LOG_FILE = None

mock_api = MagicMock()
mock_api.login.return_value = "test-token-123"

sys.modules["app"] = MagicMock()
sys.modules["app.color_print"] = MagicMock()
sys.modules["app.PurchaseOrders"] = MagicMock()
sys.modules["app.api"] = mock_api
sys.modules["app.pdf"] = MagicMock()
sys.modules["app.config"] = mock_config
sys.modules["app.orientation"] = MagicMock()

# Provide test credentials so getEnv() doesn't raise ValueError
os.environ.setdefault("QUALER_EMAIL", "test@example.com")
os.environ.setdefault("QUALER_PASSWORD", "test_password")

# NOW safe to import from upload
from upload import get_credentials  # noqa: E402
from upload import rename_file  # noqa: E402
from upload import upload_with_rename  # noqa: E402
from upload import fetch_SO_and_upload  # noqa: E402
from upload import upload_by_po  # noqa: E402
from upload import handle_po_upload  # noqa: E402


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
        uploadResult, new_filepath = result
        self.assertTrue(uploadResult)
        self.assertEqual(new_filepath, "/path/to/file.pdf")

    @patch("upload.upload_by_po")
    @patch("upload.update_PO_numbers")
    @patch("upload.extract_po")
    def test_handle_po_upload_failure(self, mock_extract, mock_update, mock_upload_po):
        mock_extract.return_value = "PO123"
        mock_update.return_value = {"PO123": ["SO1"]}
        mock_upload_po.return_value = ([], ["SO1"], "/path/to/file.pdf")

        uploadResult, new_filepath = handle_po_upload(
            "/path/to/PO123.pdf", "DOC_TYPE", "PO123.pdf"
        )
        self.assertFalse(uploadResult)
        self.assertEqual(new_filepath, "/path/to/file.pdf")


class TestGetEnv(unittest.TestCase):
    """Test the getEnv function for credential retrieval."""

    @patch.dict(
        os.environ,
        {"QUALER_EMAIL": "env@test.com", "QUALER_PASSWORD": "env_pass"},
    )
    def test_getenv_from_environment(self):
        from upload import getEnv

        result = getEnv()
        self.assertEqual(result, ("env@test.com", "env_pass"))

    @patch("upload.load_dotenv")
    @patch("os.path.exists", return_value=True)
    @patch.dict(os.environ, {}, clear=True)
    def test_getenv_from_dotenv(self, mock_exists, mock_load):
        from upload import getEnv

        def set_env(*args, **kwargs):
            os.environ["QUALER_EMAIL"] = "dotenv@test.com"
            os.environ["QUALER_PASSWORD"] = "dotenv_pass"

        mock_load.side_effect = set_env
        result = getEnv()
        self.assertEqual(result, ("dotenv@test.com", "dotenv_pass"))

    @patch("upload.load_dotenv")
    @patch("os.path.exists", return_value=False)
    @patch.dict(os.environ, {}, clear=True)
    def test_getenv_no_credentials_raises(self, mock_exists, mock_load):
        from upload import getEnv

        with self.assertRaises(ValueError):
            getEnv()


class TestRenameFileEdgeCases(unittest.TestCase):
    @patch("upload.pdf.increment_filename")
    @patch("upload.pdf.try_rename")
    def test_rename_file_max_attempts(self, mock_try_rename, mock_increment):
        """Test rename_file when all attempts fail."""
        mock_increment.return_value = "/path/to/file_1.pdf"
        mock_try_rename.return_value = False

        result = rename_file("/path/to/file.pdf", [])
        # Should return original filepath after exhausting attempts
        self.assertEqual(result, "/path/to/file.pdf")

    @patch("upload.pdf.increment_filename")
    @patch("upload.pdf.try_rename", side_effect=FileNotFoundError)
    def test_rename_file_not_found_raises(self, mock_try_rename, mock_increment):
        mock_increment.return_value = "/path/to/file_1.pdf"

        with self.assertRaises(FileNotFoundError):
            rename_file("/path/to/file.pdf", [])


class TestUploadWithRenameEdgeCases(unittest.TestCase):
    @patch("upload.api.upload")
    @patch("upload.api.get_service_order_document_list", return_value=None)
    def test_upload_with_rename_none_doc_list(self, mock_get_docs, mock_upload):
        """When doc list is None, should still proceed."""
        mock_upload.return_value = (True, "/path/to/file.pdf")

        result, filepath = upload_with_rename("/path/to/file.pdf", "SO123", "DOC_TYPE")
        self.assertTrue(result)

    @patch("upload.api.upload", side_effect=FileExistsError)
    @patch("upload.api.get_service_order_document_list", return_value=[])
    def test_upload_with_rename_file_exists_error(self, mock_get_docs, mock_upload):
        """FileExistsError during upload should return False."""
        result, filepath = upload_with_rename("/path/to/file.pdf", "SO123", "DOC_TYPE")
        self.assertFalse(result)


class TestUploadByPoEdgeCases(unittest.TestCase):
    @patch("upload.upload_with_rename")
    @patch("os.path.isfile")
    def test_upload_by_po_partial_failure(self, mock_isfile, mock_upload):
        """Test when some SOs succeed and some fail."""
        mock_isfile.return_value = True
        mock_upload.side_effect = [
            (True, "/path/to/file.pdf"),
            (False, "/path/to/file.pdf"),
        ]

        po_dict = {"PO123": ["SO1", "SO2"]}
        success, failed, filepath = upload_by_po(
            "/path/to/file.pdf", "PO123", po_dict, "DOC_TYPE"
        )
        self.assertEqual(success, ["SO1"])
        self.assertEqual(failed, ["SO2"])

    @patch("upload.upload_with_rename", side_effect=FileNotFoundError)
    @patch("os.path.isfile", return_value=True)
    def test_upload_by_po_file_not_found(self, mock_isfile, mock_upload):
        po_dict = {"PO123": ["SO1"]}
        success, failed, filepath = upload_by_po(
            "/path/to/file.pdf", "PO123", po_dict, "DOC_TYPE"
        )
        self.assertEqual(success, [])

    @patch("os.path.isfile", return_value=False)
    def test_upload_by_po_file_missing(self, mock_isfile):
        po_dict = {"PO123": ["SO1"]}
        success, failed, filepath = upload_by_po(
            "/path/to/file.pdf", "PO123", po_dict, "DOC_TYPE"
        )
        self.assertEqual(success, [])
        self.assertEqual(failed, ["SO1"])


class TestFetchSOAndUploadEdgeCases(unittest.TestCase):
    @patch("upload.api.getServiceOrderId", return_value=None)
    @patch("os.path.isfile", return_value=True)
    def test_fetch_so_no_service_order(self, mock_isfile, mock_get_so):
        """When service order is not found, should return False."""
        result, filepath = fetch_SO_and_upload("WO999", "/path/to/file.pdf", "DOC_TYPE")
        self.assertFalse(result)

    @patch("upload.api.getServiceOrderId", side_effect=FileNotFoundError)
    @patch("os.path.isfile", return_value=True)
    def test_fetch_so_exception(self, mock_isfile, mock_get_so):
        result, filepath = fetch_SO_and_upload("WO123", "/path/to/file.pdf", "DOC_TYPE")
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
