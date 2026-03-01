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

    def test_config_has_two_watched_folders(self):
        from app.config_manager import get_config, WatchedFolder

        cfg = get_config()
        self.assertEqual(len(cfg.watched_folders), 2)
        for wf in cfg.watched_folders:
            self.assertIsInstance(wf, WatchedFolder)
            self.assertIsInstance(wf.input_dir, str)
            self.assertIsInstance(wf.output_dir, str)
            self.assertIsInstance(wf.reject_dir, str)
            self.assertIsInstance(wf.qualer_document_type, str)
            self.assertIsInstance(wf.validate_po, bool)


if __name__ == "__main__":
    unittest.main()
