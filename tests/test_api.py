import unittest
from unittest.mock import patch, MagicMock
import json


class TestHandleError(unittest.TestCase):
    @patch("app.api.cp")
    def test_handle_error(self, mock_cp):
        from app.api import handle_error

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        handle_error(mock_response)
        self.assertTrue(mock_cp.red.called)


class TestHandleException(unittest.TestCase):
    @patch("app.api.cp")
    def test_handle_exception_with_response(self, mock_cp):
        from app.api import handle_exception
        import requests

        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 400
        mock_response.text = "Bad Request"

        handle_exception(ValueError("test"), mock_response)
        self.assertTrue(mock_cp.red.called)

    @patch("app.api.cp")
    def test_handle_exception_without_response(self, mock_cp):
        from app.api import handle_exception

        handle_exception(ValueError("test"), None)
        self.assertTrue(mock_cp.red.called)

    @patch("app.api.cp")
    def test_handle_exception_with_invalid_response(self, mock_cp):
        from app.api import handle_exception

        handle_exception(ValueError("test"), "not a response")
        self.assertTrue(mock_cp.red.called)


class TestLogin(unittest.TestCase):
    @patch("app.api.requests.post")
    @patch("app.api.cp")
    def test_login_success(self, mock_cp, mock_post):
        from app.api import login

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = json.dumps({"Token": "abc123"})
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_post.return_value = mock_response

        result = login("https://api.example.com", "user@test.com", "pass123")
        self.assertEqual(result, "abc123")

    @patch("app.api.cp")
    def test_login_no_credentials_raises(self, mock_cp):
        from app.api import login

        with self.assertRaises(SystemExit):
            login("https://api.example.com", "", "pass123")

    @patch("app.api.cp")
    def test_login_no_password_raises(self, mock_cp):
        from app.api import login

        with self.assertRaises(SystemExit):
            login("https://api.example.com", "user@test.com", "")

    @patch("app.api.requests.post")
    @patch("app.api.cp")
    def test_login_no_token_in_response(self, mock_cp, mock_post):
        from app.api import login

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = json.dumps({"Message": "No token"})
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_post.return_value = mock_response

        with self.assertRaises(SystemExit):
            login("https://api.example.com", "user@test.com", "pass123")

    @patch("app.api.requests.post")
    @patch("app.api.cp")
    def test_login_bad_status_still_gets_token(self, mock_cp, mock_post):
        from app.api import login

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = json.dumps({"Token": "abc123"})
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_post.return_value = mock_response

        result = login("https://api.example.com", "user@test.com", "pass123")
        self.assertEqual(result, "abc123")
        mock_cp.red.assert_called()


class TestGetServiceOrders(unittest.TestCase):
    @patch("app.api.requests.get")
    @patch("app.api.cp")
    def test_get_service_orders_success(self, mock_cp, mock_get):
        from app.api import get_service_orders

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = json.dumps(
            [{"ServiceOrderId": "SO1", "PoNumber": "PO100"}]
        )
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_get.return_value = mock_response

        result = get_service_orders({"from": "2020-01-01"}, "token123")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["ServiceOrderId"], "SO1")


class TestGetServiceOrderId(unittest.TestCase):
    @patch("app.api.get_service_orders")
    @patch("app.api.cp")
    def test_get_service_order_id_found(self, mock_cp, mock_get_so):
        from app.api import getServiceOrderId

        mock_get_so.return_value = [{"ServiceOrderId": "SO123"}]
        result = getServiceOrderId("token", "WO-001")
        self.assertEqual(result, "SO123")

    @patch("app.api.get_service_orders")
    @patch("app.api.cp")
    def test_get_service_order_id_not_found(self, mock_cp, mock_get_so):
        from app.api import getServiceOrderId

        mock_get_so.return_value = []
        result = getServiceOrderId("token", "WO-999")
        self.assertIsNone(result)


class TestUpload(unittest.TestCase):
    @patch("app.api.requests.post")
    @patch("app.api.cp")
    @patch("app.api.path.exists", return_value=True)
    @patch("app.api.path.getsize", return_value=1024)
    @patch("builtins.open", MagicMock())
    def test_upload_success(self, mock_getsize, mock_exists, mock_cp, mock_post):
        from app.api import upload

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result, filepath = upload(
            "token", "/path/to/file.pdf", "SO123", "ordercertificate"
        )
        self.assertTrue(result)

    @patch("app.api.cp")
    @patch("app.api.path.exists", return_value=False)
    def test_upload_file_not_exists(self, mock_exists, mock_cp):
        from app.api import upload

        result, filepath = upload(
            "token", "/nonexistent.pdf", "SO123", "ordercertificate"
        )
        self.assertFalse(result)

    @patch("app.api.pdf.try_rename", return_value=True)
    @patch("app.api.pdf.increment_filename", return_value="/path/to/file (1).pdf")
    @patch("app.api.requests.post")
    @patch("app.api.cp")
    @patch("app.api.path.exists", return_value=True)
    @patch("app.api.path.getsize", return_value=1024)
    @patch("builtins.open", MagicMock())
    def test_upload_locked_document_retries(
        self,
        mock_getsize,
        mock_exists,
        mock_cp,
        mock_post,
        mock_increment,
        mock_rename,
    ):
        from app.api import upload

        locked_response = MagicMock()
        locked_response.status_code = 400
        locked_response.text = json.dumps(
            {"Message": "This document version is locked and cannot be overwritten."}
        )

        success_response = MagicMock()
        success_response.status_code = 200

        mock_post.side_effect = [locked_response, success_response]

        result, filepath = upload(
            "token", "/path/to/file.pdf", "SO123", "ordercertificate"
        )
        self.assertTrue(result)


class TestGetServiceOrderDocumentList(unittest.TestCase):
    @patch("app.api.requests.get")
    @patch("app.api.cp")
    def test_get_document_list_success(self, mock_cp, mock_get):
        from app.api import get_service_order_document_list

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = json.dumps(
            [{"FileName": "doc1.pdf"}, {"FileName": "doc2.pdf"}]
        )
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_get.return_value = mock_response

        result = get_service_order_document_list(
            "https://api.example.com", "token", "SO123"
        )
        self.assertEqual(result, ["doc1.pdf", "doc2.pdf"])

    @patch("app.api.cp")
    def test_get_document_list_no_service_order_raises(self, mock_cp):
        from app.api import get_service_order_document_list

        with self.assertRaises(SystemExit):
            get_service_order_document_list("https://api.example.com", "token", None)


if __name__ == "__main__":
    unittest.main()
