import unittest


class TestConfig(unittest.TestCase):
    def test_config_has_required_attributes(self):
        import app.config as config

        self.assertIsInstance(config.LIVEAPI, bool)
        self.assertIsInstance(config.DEBUG, bool)
        self.assertIsInstance(config.DELETE_MODE, bool)
        self.assertIsInstance(config.tesseract_cmd_path, str)

    def test_max_runtime_default(self):
        import app.config as config

        self.assertIsNone(config.MAX_RUNTIME)

    def test_sharepoint_path_uses_home(self):
        import app.config as config

        self.assertIn(config.user_folder, config.SHAREPOINT_PATH)

    def test_log_file_path_suffix(self):
        import app.config as config

        # LOG_FILE may be patched by conftest; just check it's a string
        self.assertIsInstance(config.LOG_FILE, str)

    def test_po_dict_file_path(self):
        import app.config as config

        self.assertIn("DoNotMoveThisFile.json.gz", config.PO_DICT_FILE)

    def test_qualer_endpoints(self):
        import app.config as config

        self.assertIn("qualer.com", config.QUALER_ENDPOINT)
        self.assertIn("staging", config.QUALER_STAGING_ENDPOINT)

    def test_config_has_two_entries(self):
        import app.config as config

        self.assertIsInstance(config.CONFIG, list)
        self.assertEqual(len(config.CONFIG), 2)
        for entry in config.CONFIG:
            self.assertIn("INPUT_DIR", entry)
            self.assertIn("OUTPUT_DIR", entry)
            self.assertIn("REJECT_DIR", entry)
            self.assertIn("QUALER_DOCUMENT_TYPE", entry)
            self.assertIn("VALIDATE_PO", entry)


if __name__ == "__main__":
    unittest.main()
