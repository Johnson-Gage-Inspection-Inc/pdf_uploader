import unittest
from unittest.mock import patch, MagicMock
import httpx


class TestHandleError(unittest.TestCase):
    @patch("app.api.cp")
    def test_handle_error(self, mock_cp):
        from app.api import handle_error

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        handle_error(mock_response)
        self.assertTrue(mock_cp.red.called)


class TestHandleException(unittest.TestCase):
    @patch("app.api.cp")
    def test_handle_exception_with_response(self, mock_cp):
        from app.api import handle_exception

        mock_response = MagicMock(spec=httpx.Response)
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


class TestGetServiceOrders(unittest.TestCase):
    @patch("app.api.get_work_orders.sync")
    @patch("app.api.cp")
    def test_get_service_orders_success(self, mock_cp, mock_sync):
        from app.api import get_service_orders

        mock_so = MagicMock()
        mock_so.service_order_id = "SO1"
        mock_so.po_number = "PO100"
        mock_sync.return_value = [mock_so]

        result = get_service_orders(work_order_number="WO-001")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].service_order_id, "SO1")

    @patch("app.api.get_work_orders.sync")
    @patch("app.api.cp")
    def test_get_service_orders_none_response(self, mock_cp, mock_sync):
        from app.api import get_service_orders

        mock_sync.return_value = None
        result = get_service_orders(work_order_number="WO-999")
        self.assertEqual(result, [])
        mock_cp.red.assert_called()


class TestGetServiceOrderId(unittest.TestCase):
    @patch("app.api.get_service_orders")
    @patch("app.api.cp")
    def test_get_service_order_id_found(self, mock_cp, mock_get_so):
        from app.api import getServiceOrderId

        mock_so = MagicMock()
        mock_so.service_order_id = 12345
        mock_get_so.return_value = [mock_so]
        result = getServiceOrderId("WO-001")
        self.assertEqual(result, 12345)

    @patch("app.api.get_service_orders")
    @patch("app.api.cp")
    def test_get_service_order_id_not_found(self, mock_cp, mock_get_so):
        from app.api import getServiceOrderId

        mock_get_so.return_value = []
        result = getServiceOrderId("WO-999")
        self.assertIsNone(result)


class TestGetServiceOrder(unittest.TestCase):
    @patch("app.api._sdk_get_work_order.sync")
    @patch("app.api.cp")
    def test_get_service_order_success(self, mock_cp, mock_sync):
        from app.api import get_service_order

        mock_so = MagicMock()
        mock_so.custom_order_number = "56561-083002"
        mock_sync.return_value = mock_so

        result = get_service_order(1361263)
        self.assertEqual(result.custom_order_number, "56561-083002")
        mock_sync.assert_called_once()

    @patch("app.api._sdk_get_work_order.sync")
    @patch("app.api.cp")
    def test_get_service_order_not_found(self, mock_cp, mock_sync):
        from app.api import get_service_order

        mock_sync.return_value = None
        result = get_service_order(999999)
        self.assertIsNone(result)

    @patch("app.api._sdk_get_work_order.sync", side_effect=Exception("API error"))
    @patch("app.api.cp")
    def test_get_service_order_exception(self, mock_cp, mock_sync):
        from app.api import get_service_order

        result = get_service_order(123)
        self.assertIsNone(result)


class TestUpload(unittest.TestCase):
    @patch("app.api.upload_documents_post_2.sync_detailed")
    @patch("app.api.cp")
    @patch("app.api.path.exists", return_value=True)
    @patch("builtins.open", MagicMock())
    def test_upload_success(self, mock_exists, mock_cp, mock_sync_detailed):
        from app.api import upload

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_sync_detailed.return_value = mock_response

        result, filepath = upload("/path/to/file.pdf", 123, "ordercertificate")
        self.assertTrue(result)
        # default should not mark document private
        mock_sync_detailed.assert_called_once()
        _, kwargs = mock_sync_detailed.call_args
        self.assertEqual(kwargs.get("model_report_type"), "ordercertificate")
        self.assertFalse(kwargs.get("model_is_private"))

    @patch("app.api.cp")
    @patch("app.api.path.exists", return_value=False)
    def test_upload_file_not_exists(self, mock_exists, mock_cp):
        from app.api import upload

        result, filepath = upload("/nonexistent.pdf", 123, "ordercertificate")
        self.assertFalse(result)

    @patch("app.api.upload_documents_post_2.sync_detailed")
    @patch("app.api.pdf.try_rename", return_value=True)
    @patch("app.api.pdf.increment_filename", return_value="/path/to/file (1).pdf")
    @patch("app.api.cp")
    @patch("app.api.path.exists", return_value=True)
    @patch("builtins.open", MagicMock())
    def test_upload_locked_document_retries(
        self,
        mock_exists,
        mock_cp,
        mock_increment,
        mock_rename,
        mock_sync_detailed,
    ):
        from app.api import upload
        import json

        locked_response = MagicMock()
        locked_response.status_code = 400
        locked_response.content = json.dumps(
            {"Message": "This document version is locked and cannot be overwritten."}
        ).encode()

        success_response = MagicMock()
        success_response.status_code = 200

        mock_sync_detailed.side_effect = [locked_response, success_response]

        result, filepath = upload("/path/to/file.pdf", 123, "ordercertificate")
        self.assertTrue(result)

    @patch("app.api.upload_documents_post_2.sync_detailed")
    @patch("app.api.cp")
    @patch("app.api.path.exists", return_value=True)
    @patch("builtins.open", MagicMock())
    def test_upload_private_flag(self, mock_exists, mock_cp, mock_sync_detailed):
        """Explicitly passing ``private=True`` should set the API parameter."""
        from app.api import upload

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_sync_detailed.return_value = mock_response

        result, filepath = upload(
            "/path/to/file.pdf", 123, "ordercertificate", private=True
        )
        self.assertTrue(result)
        mock_sync_detailed.assert_called_once()
        _, kwargs = mock_sync_detailed.call_args
        self.assertTrue(kwargs.get("model_is_private"))


class TestGetServiceOrderDocumentList(unittest.TestCase):
    @patch("app.api.get_documents_list.sync")
    @patch("app.api.cp")
    def test_get_document_list_success(self, mock_cp, mock_sync):
        from app.api import get_service_order_document_list

        doc1 = MagicMock()
        doc1.file_name = "doc1.pdf"
        doc2 = MagicMock()
        doc2.file_name = "doc2.pdf"
        mock_sync.return_value = [doc1, doc2]

        result = get_service_order_document_list(123)
        self.assertEqual(result, ["doc1.pdf", "doc2.pdf"])

    @patch("app.api.cp")
    def test_get_document_list_no_service_order_raises(self, mock_cp):
        from app.api import get_service_order_document_list

        with self.assertRaises(SystemExit):
            get_service_order_document_list(None)

    @patch("app.api.get_documents_list.sync")
    @patch("app.api.cp")
    def test_get_document_list_none_response(self, mock_cp, mock_sync):
        from app.api import get_service_order_document_list

        mock_sync.return_value = None
        result = get_service_order_document_list(123)
        self.assertIsNone(result)


class TestGetWorkItems(unittest.TestCase):
    @patch("app.api._sdk_get_work_items.sync")
    @patch("app.api.cp")
    def test_get_work_items_success(self, mock_cp, mock_sync):
        from app.api import get_work_items

        mock_item = MagicMock()
        mock_sync.return_value = [mock_item]

        result = get_work_items(456)
        self.assertEqual(result, [mock_item])
        mock_sync.assert_called_once()

    @patch("app.api._sdk_get_work_items.sync")
    @patch("app.api.cp")
    def test_get_work_items_none_response(self, mock_cp, mock_sync):
        from app.api import get_work_items

        mock_sync.return_value = None
        result = get_work_items(456)
        self.assertEqual(result, [])

    @patch("app.api._sdk_get_work_items.sync", side_effect=Exception("API error"))
    @patch("app.api.cp")
    def test_get_work_items_exception_returns_empty(self, mock_cp, mock_sync):
        from app.api import get_work_items

        result = get_work_items(456)
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
