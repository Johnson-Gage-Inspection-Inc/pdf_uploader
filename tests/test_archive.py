import unittest
from unittest.mock import patch
import os
import shutil
import tempfile
import time
import zipfile


class TestMoveOldPdfs(unittest.TestCase):
    """Test the move_old_pdfs function from archive.py."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch("app.archive.cp")
    def test_move_old_pdfs_no_files(self, mock_cp):
        from app.archive import move_old_pdfs

        move_old_pdfs(self.test_dir)

    @patch("app.archive.cp")
    def test_move_old_pdfs_today_files_untouched(self, mock_cp):
        from app.archive import move_old_pdfs

        pdf_path = os.path.join(self.test_dir, "today.pdf")
        with open(pdf_path, "w") as f:
            f.write("test")

        move_old_pdfs(self.test_dir)
        self.assertTrue(os.path.exists(pdf_path))

    @patch("app.archive.cp")
    def test_move_old_pdfs_delete_mode(self, mock_cp):
        from app.archive import move_old_pdfs

        pdf_path = os.path.join(self.test_dir, "old.pdf")
        with open(pdf_path, "w") as f:
            f.write("test")

        yesterday = time.time() - 86400 * 2
        with patch("app.archive.os.path.getctime", return_value=yesterday):
            move_old_pdfs(self.test_dir, delete_mode=True)

        self.assertFalse(os.path.exists(pdf_path))

    @patch("app.archive.cp")
    def test_move_old_pdfs_archive_mode(self, mock_cp):
        from app.archive import move_old_pdfs

        pdf_path = os.path.join(self.test_dir, "old.pdf")
        with open(pdf_path, "w") as f:
            f.write("test content")

        yesterday = time.time() - 86400 * 2
        with patch("app.archive.os.path.getctime", return_value=yesterday):
            move_old_pdfs(self.test_dir, delete_mode=False)

        self.assertFalse(os.path.exists(pdf_path))
        zip_path = os.path.join(self.test_dir, "Archive.zip")
        self.assertTrue(os.path.exists(zip_path))
        with zipfile.ZipFile(zip_path, "r") as z:
            self.assertIn("old.pdf", z.namelist())

    @patch("app.archive.cp")
    def test_move_old_pdfs_non_pdf_ignored(self, mock_cp):
        from app.archive import move_old_pdfs

        txt_path = os.path.join(self.test_dir, "old.txt")
        with open(txt_path, "w") as f:
            f.write("test")

        yesterday = time.time() - 86400 * 2
        with patch("app.archive.os.path.getctime", return_value=yesterday):
            move_old_pdfs(self.test_dir, delete_mode=True)

        self.assertTrue(os.path.exists(txt_path))


if __name__ == "__main__":
    unittest.main()
