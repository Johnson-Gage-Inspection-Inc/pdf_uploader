import unittest
from unittest.mock import patch, MagicMock


class TestGetPdfOrientation(unittest.TestCase):
    @patch("app.orientation.get_visual_orientation", return_value=90)
    @patch("app.orientation.get_text_orientation", return_value=None)
    @patch("app.orientation.convert_to_grayscale")
    @patch("app.orientation.convert_pdf_to_image")
    def test_falls_back_to_visual_when_text_fails(
        self, mock_convert, mock_gray, mock_text, mock_visual
    ):
        from app.orientation import get_pdf_orientation

        self.assertEqual(get_pdf_orientation("/test.pdf"), 90)
        mock_visual.assert_called_once()

    @patch("app.orientation.get_text_orientation", return_value=180)
    @patch("app.orientation.convert_to_grayscale")
    @patch("app.orientation.convert_pdf_to_image")
    def test_uses_text_orientation_when_available(
        self, mock_convert, mock_gray, mock_text
    ):
        from app.orientation import get_pdf_orientation

        self.assertEqual(get_pdf_orientation("/test.pdf"), 180)

    @patch("app.orientation.get_text_orientation", return_value=0)
    @patch("app.orientation.convert_to_grayscale")
    @patch("app.orientation.convert_pdf_to_image")
    def test_zero_orientation(self, mock_convert, mock_gray, mock_text):
        from app.orientation import get_pdf_orientation

        self.assertEqual(get_pdf_orientation("/test.pdf"), 0)


class TestConvertToGrayscale(unittest.TestCase):
    def test_converts_to_grayscale(self):
        from app.orientation import convert_to_grayscale

        mock_image = MagicMock()
        mock_gray = MagicMock()
        mock_image.convert.return_value = mock_gray

        result = convert_to_grayscale(mock_image)
        mock_image.convert.assert_called_with("L")
        self.assertEqual(result, mock_gray)


class TestReorientPdfForWorkorders(unittest.TestCase):
    @patch("app.orientation.cp")
    @patch("app.orientation.move_file")
    @patch("app.orientation.workorders", return_value={"56561-123456": {0}})
    @patch("app.orientation.rotate_pdf")
    @patch("app.orientation.get_pdf_orientation", return_value=180)
    def test_rotated_and_workorders_found(
        self, mock_orient, mock_rotate, mock_wo, mock_move, mock_cp
    ):
        from app.orientation import reorient_pdf_for_workorders

        result = reorient_pdf_for_workorders("/path/to/file.pdf", "/reject")
        self.assertEqual(result, {"56561-123456": {0}})
        mock_rotate.assert_called_once_with("/path/to/file.pdf", 180)

    @patch("app.orientation.cp")
    @patch("app.orientation.move_file")
    @patch("app.orientation.get_pdf_orientation", return_value=0)
    def test_right_side_up_moved_to_reject(self, mock_orient, mock_move, mock_cp):
        from app.orientation import reorient_pdf_for_workorders

        result = reorient_pdf_for_workorders("/path/to/file.pdf", "/reject")
        self.assertFalse(result)
        mock_move.assert_called_once_with("/path/to/file.pdf", "/reject")

    @patch("app.orientation.cp")
    @patch("app.orientation.move_file")
    @patch("app.orientation.workorders", return_value={})
    @patch("app.orientation.rotate_pdf")
    @patch("app.orientation.get_pdf_orientation", return_value=90)
    def test_rotated_but_no_workorders(
        self, mock_orient, mock_rotate, mock_wo, mock_move, mock_cp
    ):
        from app.orientation import reorient_pdf_for_workorders

        result = reorient_pdf_for_workorders("/path/to/file.pdf", "/reject")
        self.assertFalse(result)
        mock_move.assert_called_once_with("/path/to/file.pdf", "/reject")

    @patch("app.orientation.cp")
    @patch("app.orientation.move_file")
    @patch("app.orientation.get_pdf_orientation", return_value=None)
    def test_unknown_orientation(self, mock_orient, mock_move, mock_cp):
        from app.orientation import reorient_pdf_for_workorders

        result = reorient_pdf_for_workorders("/path/to/file.pdf", "/reject")
        self.assertFalse(result)

    @patch("app.orientation.cp")
    @patch(
        "app.orientation.get_pdf_orientation",
        side_effect=FileNotFoundError("not found"),
    )
    def test_file_not_found(self, mock_orient, mock_cp):
        from app.orientation import reorient_pdf_for_workorders

        result = reorient_pdf_for_workorders("/nonexistent.pdf", "/reject")
        self.assertFalse(result)


class TestGetTextOrientation(unittest.TestCase):
    @patch("app.orientation.os.remove")
    @patch("app.orientation.image_to_osd")
    @patch("app.orientation.tempfile.NamedTemporaryFile")
    def test_valid_rotation(self, mock_tmp, mock_osd, mock_remove):
        from app.orientation import get_text_orientation

        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=MagicMock(name="tmp.png"))
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_tmp.return_value = mock_ctx

        mock_osd.return_value = (
            "Page number: 0\n"
            "Orientation in degrees: 0\n"
            "Rotate: 180\n"
            "Orientation confidence: 5.0\n"
            "Script: Latin\n"
        )

        mock_image = MagicMock()
        result = get_text_orientation(mock_image)
        self.assertEqual(result, 180)

    @patch("app.orientation.os.remove")
    @patch("app.orientation.image_to_osd")
    @patch("app.orientation.tempfile.NamedTemporaryFile")
    def test_no_rotation_line(self, mock_tmp, mock_osd, mock_remove):
        from app.orientation import get_text_orientation

        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=MagicMock(name="tmp.png"))
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_tmp.return_value = mock_ctx
        mock_osd.return_value = "Page number: 0\nScript: Latin\n"

        result = get_text_orientation(MagicMock())
        self.assertIsNone(result)

    @patch("app.orientation.cp")
    @patch("app.orientation.os.remove")
    @patch("app.orientation.image_to_osd")
    @patch("app.orientation.tempfile.NamedTemporaryFile")
    def test_tesseract_error(self, mock_tmp, mock_osd, mock_remove, mock_cp):
        from app.orientation import get_text_orientation
        from pytesseract import TesseractError

        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=MagicMock(name="tmp.png"))
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_tmp.return_value = mock_ctx
        mock_osd.side_effect = TesseractError("status", "message")

        result = get_text_orientation(MagicMock())
        self.assertIsNone(result)


class TestRotatePdf(unittest.TestCase):
    @patch("app.orientation.cp")
    def test_invalid_degrees_raises(self, mock_cp):
        from app.orientation import rotate_pdf

        result = rotate_pdf("/path/to/file.pdf", degrees=45)
        self.assertFalse(result)

    @patch("app.orientation.cp")
    @patch("app.orientation.open_with_debug")
    @patch("app.orientation.PdfWriter")
    @patch("app.orientation.PdfReader")
    def test_rotate_pdf_success(self, mock_reader, mock_writer, mock_open, mock_cp):
        from app.orientation import rotate_pdf

        mock_page = MagicMock()
        mock_reader_instance = MagicMock()
        mock_reader_instance.pages = [mock_page]
        mock_reader.return_value = mock_reader_instance

        mock_writer_instance = MagicMock()
        mock_writer.return_value = mock_writer_instance

        mock_file = MagicMock()
        mock_open.return_value.__enter__ = MagicMock(return_value=mock_file)
        mock_open.return_value.__exit__ = MagicMock(return_value=False)

        result = rotate_pdf("/path/to/file.pdf", degrees=180)
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
