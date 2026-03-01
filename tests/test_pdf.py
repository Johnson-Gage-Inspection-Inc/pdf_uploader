import unittest
from unittest.mock import patch, MagicMock
import os
import tempfile


class TestPdfNext(unittest.TestCase):
    """Test the next() generator that yields PDF file paths."""

    @patch("os.fsdecode", side_effect=lambda f: f)
    @patch("os.listdir", return_value=["file1.pdf", "file2.txt", "file3.PDF"])
    def test_next_yields_pdf_files(self, mock_listdir, mock_fsdecode):
        from app.pdf import next as pdf_next

        results = list(pdf_next("/test/dir"))
        self.assertEqual(len(results), 2)
        self.assertTrue(results[0].endswith("file1.pdf"))
        self.assertTrue(results[1].endswith("file3.PDF"))

    @patch("os.fsdecode", side_effect=lambda f: f)
    @patch("os.listdir", return_value=["file1.txt", "file2.doc"])
    def test_next_no_pdfs(self, mock_listdir, mock_fsdecode):
        from app.pdf import next as pdf_next

        results = list(pdf_next("/test/dir"))
        self.assertEqual(len(results), 0)

    @patch("os.listdir", return_value=[])
    def test_next_empty_dir(self, mock_listdir):
        from app.pdf import next as pdf_next

        results = list(pdf_next("/test/dir"))
        self.assertEqual(len(results), 0)


class TestIncrementFilename(unittest.TestCase):
    """Test the increment_filename function."""

    @patch("app.pdf.sleep")
    def test_increment_new_file(self, mock_sleep):
        from app.pdf import increment_filename

        result = increment_filename("/path/to/file.pdf")
        self.assertEqual(result, "/path/to/file (1).pdf")

    @patch("app.pdf.sleep")
    def test_increment_already_incremented(self, mock_sleep):
        from app.pdf import increment_filename

        result = increment_filename("/path/to/file (1).pdf")
        self.assertEqual(result, "/path/to/file (2).pdf")

    @patch("app.pdf.sleep")
    def test_increment_high_number(self, mock_sleep):
        from app.pdf import increment_filename

        result = increment_filename("/path/to/file (50).pdf")
        self.assertEqual(result, "/path/to/file (51).pdf")

    @patch("app.pdf.sleep")
    def test_increment_at_99(self, mock_sleep):
        from app.pdf import increment_filename

        result = increment_filename("/path/to/file (99).pdf")
        self.assertEqual(result, "/path/to/file (100).pdf")


class TestTryRename(unittest.TestCase):
    """Test the try_rename function."""

    @patch("os.rename")
    def test_try_rename_success(self, mock_rename):
        from app.pdf import try_rename

        result = try_rename("/src/file.pdf", "/dst/file.pdf")
        self.assertTrue(result)
        mock_rename.assert_called_once_with("/src/file.pdf", "/dst/file.pdf")

    @patch("os.rename", side_effect=FileExistsError)
    def test_try_rename_file_exists(self, mock_rename):
        from app.pdf import try_rename

        result = try_rename("/src/file.pdf", "/dst/file.pdf")
        self.assertFalse(result)

    @patch("app.pdf.cp")
    @patch("os.rename", side_effect=FileNotFoundError)
    def test_try_rename_file_not_found_raises(self, mock_rename, mock_cp):
        from app.pdf import try_rename

        with self.assertRaises(FileNotFoundError):
            try_rename("/src/file.pdf", "/dst/file.pdf", retries=2, delay=0)

    @patch("app.pdf.cp")
    @patch("os.rename", side_effect=PermissionError("access denied"))
    def test_try_rename_other_error(self, mock_rename, mock_cp):
        from app.pdf import try_rename

        # PermissionError now retries and eventually raises after all attempts
        with self.assertRaises(PermissionError):
            try_rename("/src/file.pdf", "/dst/file.pdf", retries=2, delay=0)


class TestWoNumFormat(unittest.TestCase):
    """Test the WO_NUM_FORMAT regex pattern."""

    def test_wo_num_format_matches(self):
        from app.pdf import WO_NUM_FORMAT
        from re import findall

        text = "Work order 56561-123456 is ready"
        matches = findall(WO_NUM_FORMAT, text)
        self.assertEqual(matches, ["56561-123456"])

    def test_wo_num_format_no_match(self):
        from app.pdf import WO_NUM_FORMAT
        from re import findall

        text = "No work order here"
        matches = findall(WO_NUM_FORMAT, text)
        self.assertEqual(matches, [])

    def test_wo_num_format_multiple_matches(self):
        from app.pdf import WO_NUM_FORMAT
        from re import findall

        text = "Orders 56561-111111 and 56561-222222"
        matches = findall(WO_NUM_FORMAT, text)
        self.assertEqual(matches, ["56561-111111", "56561-222222"])

    def test_wo_num_format_wrong_prefix(self):
        from app.pdf import WO_NUM_FORMAT
        from re import findall

        text = "Order 99999-123456 is wrong"
        matches = findall(WO_NUM_FORMAT, text)
        self.assertEqual(matches, [])


class TestWorkorders(unittest.TestCase):
    """Test the workorders function."""

    @patch("app.pdf.extract")
    def test_workorders_from_filename(self, mock_extract):
        from app.pdf import workorders

        result = workorders("/path/to/56561-123456.pdf")
        self.assertIsInstance(result, list)
        self.assertEqual(result, ["56561-123456"])
        mock_extract.assert_not_called()

    @patch("app.pdf.extract")
    def test_workorders_from_body_single(self, mock_extract):
        from app.pdf import workorders

        mock_extract.return_value = ["Page with 56561-654321 work order"]
        result = workorders("/path/to/file.pdf")
        self.assertIsInstance(result, dict)
        self.assertIn("56561-654321", result)
        self.assertEqual(result["56561-654321"], {0})

    @patch("app.pdf.extract")
    def test_workorders_from_body_multiple(self, mock_extract):
        from app.pdf import workorders

        mock_extract.return_value = [
            "Page with 56561-111111",
            "Still on 56561-111111",
            "New order 56561-222222",
        ]
        result = workorders("/path/to/file.pdf")
        self.assertIsInstance(result, dict)
        self.assertIn("56561-111111", result)
        self.assertIn("56561-222222", result)
        self.assertEqual(result["56561-111111"], {0, 1})
        self.assertEqual(result["56561-222222"], {2})

    @patch("app.pdf.extract")
    def test_workorders_no_orders_found(self, mock_extract):
        from app.pdf import workorders

        mock_extract.return_value = ["No work orders in this PDF"]
        result = workorders("/path/to/file.pdf")
        self.assertIsInstance(result, dict)
        self.assertEqual(result, {})

    @patch("app.pdf.extract")
    def test_workorders_pages_without_wo_appended_to_previous(self, mock_extract):
        from app.pdf import workorders

        mock_extract.return_value = [
            "Page with 56561-111111",
            "Continuation page no WO",
            "Another page 56561-222222",
        ]
        result = workorders("/path/to/file.pdf")
        self.assertIn("56561-111111", result)
        self.assertIn(0, result["56561-111111"])
        self.assertIn(1, result["56561-111111"])
        self.assertIn("56561-222222", result)


class TestMoveFile(unittest.TestCase):
    """Test the move_file function."""

    @patch("app.pdf.cp")
    @patch("os.rename")
    def test_move_file_success(self, mock_rename, mock_cp):
        from app.pdf import move_file

        result = move_file("/src/file.pdf", "/dst")
        expected_dst = os.path.join("/dst", "file.pdf")
        mock_rename.assert_called_once_with("/src/file.pdf", expected_dst)
        self.assertEqual(result, expected_dst)

    @patch("app.pdf.sleep")
    @patch("app.pdf.cp")
    @patch("os.rename", side_effect=FileNotFoundError("not found"))
    def test_move_file_not_found(self, mock_rename, mock_cp, mock_sleep):
        from app.pdf import move_file

        result = move_file("/src/file.pdf", "/dst")
        self.assertFalse(result)

    @patch("app.pdf.increment_filename", return_value="/dst/file (1).pdf")
    @patch("app.pdf.sleep")
    @patch("app.pdf.cp")
    @patch("builtins.print")
    @patch("os.rename")
    def test_move_file_file_exists_then_succeeds(
        self, mock_rename, mock_print, mock_cp, mock_sleep, mock_increment
    ):
        from app.pdf import move_file

        mock_rename.side_effect = [FileExistsError, None]
        result = move_file("/src/file.pdf", "/dst")
        self.assertEqual(result, "/dst/file (1).pdf")


class TestExtract(unittest.TestCase):
    """Test text extraction from PDF."""

    @patch("app.pdf.cp")
    @patch("app.pdf.PdfReader")
    def test_extract_with_pypdf(self, mock_reader_class, mock_cp):
        from app.pdf import extract

        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Sample text from PDF"
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]
        mock_reader_class.return_value = mock_reader

        result = extract("/path/to/file.pdf")
        self.assertEqual(result, ["Sample text from PDF"])

    @patch("app.pdf.tesseractOcr", return_value=["OCR extracted text"])
    @patch("app.pdf.cp")
    @patch("app.pdf.PdfReader")
    def test_extract_falls_back_to_ocr(self, mock_reader_class, mock_cp, mock_ocr):
        from app.pdf import extract

        mock_page = MagicMock()
        mock_page.extract_text.return_value = ""
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]
        mock_reader_class.return_value = mock_reader

        result = extract("/path/to/file.pdf")
        self.assertEqual(result, ["OCR extracted text"])
        mock_ocr.assert_called_once()


class TestOpenWithDebug(unittest.TestCase):
    """Test the open_with_debug function."""

    def test_open_with_debug_success(self):
        from app.pdf import open_with_debug

        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"test content")
            temp_path = f.name

        try:
            file_obj = open_with_debug(temp_path, "r")
            content = file_obj.read()
            file_obj.close()
            self.assertEqual(content, "test content")
        finally:
            os.unlink(temp_path)

    @patch("sys.exit")
    def test_open_with_debug_failure(self, mock_exit):
        from app.pdf import open_with_debug

        open_with_debug("/nonexistent/path/file.txt", "r")
        mock_exit.assert_called_once_with(1)


if __name__ == "__main__":
    unittest.main()
