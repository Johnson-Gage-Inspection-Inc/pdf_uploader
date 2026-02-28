import unittest
from unittest.mock import patch


class TestColorPrint(unittest.TestCase):
    """Test color_print functions calling through to _color and logging."""

    @patch("app.color_print._color")
    @patch("app.color_print.logging")
    def test_red_logs_error(self, mock_logging, mock_color):
        from app.color_print import red

        red("error message")
        mock_logging.error.assert_called_with("error message")
        mock_color.assert_called_with("error message", "RED")

    @patch("app.color_print._color")
    @patch("app.color_print.logging")
    def test_green_logs_debug(self, mock_logging, mock_color):
        from app.color_print import green

        green("success")
        mock_logging.debug.assert_called_with("success")
        mock_color.assert_called_with("success", "GREEN")

    @patch("app.color_print._color")
    @patch("app.color_print.logging")
    def test_yellow_logs_warning(self, mock_logging, mock_color):
        from app.color_print import yellow

        yellow("warning message")
        mock_logging.warning.assert_called_with("warning message")
        mock_color.assert_called_with("warning message", "YELLOW")

    @patch("app.color_print._color")
    @patch("app.color_print.logging")
    def test_blue_logs_info(self, mock_logging, mock_color):
        from app.color_print import blue

        blue("info message")
        mock_logging.info.assert_called_with("info message")
        mock_color.assert_called_with("info message", "BLUE")

    @patch("app.color_print._color")
    @patch("app.color_print.logging")
    def test_magenta_logs_info(self, mock_logging, mock_color):
        from app.color_print import magenta

        magenta("special info")
        mock_logging.info.assert_called_with("special info")
        mock_color.assert_called_with("special info", "MAGENTA")

    @patch("app.color_print._color")
    @patch("app.color_print.logging")
    def test_white_logs_debug(self, mock_logging, mock_color):
        from app.color_print import white

        white("default text")
        mock_logging.debug.assert_called_with("default text")
        mock_color.assert_called_with("default text", "WHITE")

    @patch("app.color_print._color")
    @patch("app.color_print.logging")
    def test_black_logs_debug(self, mock_logging, mock_color):
        from app.color_print import black

        black("header text")
        mock_logging.debug.assert_called_with("header text")
        mock_color.assert_called_with("header text", "BLACK")

    @patch("app.color_print._color")
    def test_cyan_no_logging(self, mock_color):
        from app.color_print import cyan

        cyan("prompt text")
        mock_color.assert_called_with("prompt text", "CYAN")

    @patch("app.color_print._color")
    @patch("app.color_print.logging")
    def test_default_empty_string(self, mock_logging, mock_color):
        from app.color_print import red

        red()
        mock_color.assert_called_with("", "RED")

    @patch("builtins.print")
    def test_color_formats_exception(self, mock_print):
        from app.color_print import _color

        err = ValueError("test error")
        _color(err, "RED")
        mock_print.assert_called_once()
        call_arg = mock_print.call_args[0][0]
        self.assertIn("ValueError", call_arg)
        self.assertIn("test error", call_arg)

    @patch("builtins.print")
    def test_color_invalid_color_raises(self, mock_print):
        from app.color_print import _color

        with self.assertRaises(AssertionError):
            _color("hello", "NONEXISTENT_COLOR")


if __name__ == "__main__":
    unittest.main()
