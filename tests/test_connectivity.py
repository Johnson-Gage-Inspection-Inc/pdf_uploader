import unittest
from unittest.mock import patch, MagicMock
import os


class TestPingAddress(unittest.TestCase):
    @patch("app.connectivity.subprocess.run")
    def test_ping_success(self, mock_run):
        from app.connectivity import ping_address

        mock_run.return_value = MagicMock(returncode=0)
        self.assertTrue(ping_address("8.8.8.8"))

    @patch("app.connectivity.subprocess.run")
    def test_ping_failure(self, mock_run):
        from app.connectivity import ping_address

        mock_run.return_value = MagicMock(returncode=1)
        self.assertFalse(ping_address("192.0.2.1"))

    @patch("app.connectivity.warn")
    @patch("app.connectivity.subprocess.run", side_effect=Exception("ping failed"))
    def test_ping_exception(self, mock_run, mock_warn):
        from app.connectivity import ping_address

        self.assertFalse(ping_address("bad.host"))

    @patch("app.connectivity.subprocess.run")
    def test_ping_uses_correct_param(self, mock_run):
        from app.connectivity import ping_address

        mock_run.return_value = MagicMock(returncode=0)
        ping_address("8.8.8.8")
        call_args = mock_run.call_args[0][0]
        expected_flag = "-n" if os.name == "nt" else "-c"
        self.assertIn(expected_flag, call_args)


class TestIsInternetConnected(unittest.TestCase):
    @patch("app.connectivity.ping_address", return_value=True)
    def test_internet_connected(self, mock_ping):
        from app.connectivity import is_internet_connected

        self.assertTrue(is_internet_connected())
        mock_ping.assert_called_with("8.8.8.8")

    @patch("app.connectivity.ping_address", return_value=False)
    def test_internet_not_connected(self, mock_ping):
        from app.connectivity import is_internet_connected

        self.assertFalse(is_internet_connected())


class TestIsSharepointAccessible(unittest.TestCase):
    @patch("app.connectivity.exists", return_value=True)
    def test_sharepoint_accessible(self, mock_exists):
        from app.connectivity import is_sharepoint_accessible

        self.assertTrue(is_sharepoint_accessible())

    @patch("app.connectivity.exists", return_value=False)
    def test_sharepoint_not_accessible(self, mock_exists):
        from app.connectivity import is_sharepoint_accessible

        self.assertFalse(is_sharepoint_accessible())


class TestIsQualerAccessible(unittest.TestCase):
    @patch("app.connectivity.sleep")
    @patch("app.connectivity.warn")
    @patch("app.connectivity.ping_address", return_value=True)
    def test_qualer_accessible_first_try(self, mock_ping, mock_warn, mock_sleep):
        from app.connectivity import is_qualer_accessible

        self.assertTrue(is_qualer_accessible())

    @patch("app.connectivity.sleep")
    @patch("app.connectivity.warn")
    @patch("app.connectivity.ping_address", return_value=False)
    def test_qualer_not_accessible_after_retries(
        self, mock_ping, mock_warn, mock_sleep
    ):
        from app.connectivity import is_qualer_accessible

        self.assertFalse(is_qualer_accessible(max_retries=2))
        self.assertEqual(mock_ping.call_count, 2)

    @patch("app.connectivity.sleep")
    @patch("app.connectivity.warn")
    @patch("app.connectivity.ping_address", side_effect=[False, True])
    def test_qualer_accessible_after_retry(self, mock_ping, mock_warn, mock_sleep):
        from app.connectivity import is_qualer_accessible

        self.assertTrue(is_qualer_accessible(max_retries=3))
        self.assertEqual(mock_ping.call_count, 2)


class TestCheckConnectivity(unittest.TestCase):
    @patch("app.connectivity.is_qualer_accessible", return_value=True)
    @patch("app.connectivity.is_sharepoint_accessible", return_value=True)
    @patch("app.connectivity.is_internet_connected", return_value=True)
    def test_all_connected(self, mock_internet, mock_sp, mock_qualer):
        from app.connectivity import check_connectivity

        self.assertTrue(check_connectivity())

    @patch("app.connectivity.warn")
    @patch("app.connectivity.is_internet_connected", return_value=False)
    def test_no_internet(self, mock_internet, mock_warn):
        from app.connectivity import check_connectivity

        self.assertFalse(check_connectivity())

    @patch("app.connectivity.warn")
    @patch("app.connectivity.is_sharepoint_accessible", return_value=False)
    @patch("app.connectivity.is_internet_connected", return_value=True)
    def test_no_sharepoint(self, mock_internet, mock_sp, mock_warn):
        from app.connectivity import check_connectivity

        self.assertFalse(check_connectivity())

    @patch("app.connectivity.warn")
    @patch("app.connectivity.is_qualer_accessible", return_value=False)
    @patch("app.connectivity.is_sharepoint_accessible", return_value=True)
    @patch("app.connectivity.is_internet_connected", return_value=True)
    def test_no_qualer(self, mock_internet, mock_sp, mock_qualer, mock_warn):
        from app.connectivity import check_connectivity

        self.assertFalse(check_connectivity())


if __name__ == "__main__":
    unittest.main()
